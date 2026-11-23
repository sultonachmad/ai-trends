"""The direct booking page: search, hold, pay, confirm, lapse, cancel."""

import asyncio
import datetime as dt
import uuid

import pytest
from sqlalchemy import text

from app.services import booking_confirmation as confirmation
from app.services import booking_holds as holds
from app.services.calendar_dates import property_today
from app.services.channel_push import _context
from app.tenancy.session import bind_tenant
from tests.pg.conftest import (
    add_staff_member,
    guest_uploads,
    image,
    make_link,
    make_rate_plan,
    make_room_type,
    pay,
    set_bank_account,
    set_business_settings,
    sold_matches_bookings,
    start_workspace,
)

pytestmark = pytest.mark.integration

SETUP = "/api/booking-page"
PHONE = "+6281234567001"


async def _page(client, *, units: int = 2, amount: int = 500000, **plan) -> dict:
    workspace = await start_workspace(client)
    room = await make_room_type(client, units=units, max_guests=2)
    rate = await make_rate_plan(client, [room], amount=amount, **plan)
    slug = f"villa-{uuid.uuid4().hex[:8]}"
    saved = await client.put(
        SETUP, json={"slug": slug, "is_published": True, "sold_plan_ids": [rate["id"]]}
    )
    assert saved.status_code == 200, saved.text
    return {"workspace": workspace, "room": room, "plan": rate, "slug": slug, "amount": amount}


def _day(ctx: dict, offset: int) -> str:
    today = property_today(ctx["workspace"]["property"]["timezone"])
    return (today + dt.timedelta(days=offset)).isoformat()


def _order(ctx: dict, **over) -> dict:
    nights = (
        dt.date.fromisoformat(over.get("departure", _day(ctx, 12)))
        - dt.date.fromisoformat(over.get("arrival", _day(ctx, 10)))
    ).days
    return {
        "idempotency_key": uuid.uuid4().hex,
        "arrival": _day(ctx, 10),
        "departure": _day(ctx, 12),
        "room_type_id": ctx["room"]["id"],
        "rate_plan_id": ctx["plan"]["id"],
        "adults": 2,
        "children": 0,
        "guest_name": "Ayu Tamu",
        "guest_phone": PHONE,
        "pay_choice": "deposit",
        "expected_total": str(ctx["amount"] * nights),
        "accepted_terms": True,
        "language": "id",
        **over,
    }


async def _book(client, ctx, **over) -> dict:
    response = await client.post(f"/api/book/{ctx['slug']}/checkout", json=_order(ctx, **over))
    assert response.status_code == 201, response.text
    return response.json()


def _pay_token(result: dict) -> str:
    return result["pay_url"].rsplit("/", 1)[1]


def _guest_api(result: dict) -> str:
    return "/api/guest-booking/" + result["booking_path"].rsplit("/", 1)[1]


async def _staff_booking(client) -> dict:
    items = (await client.get("/api/bookings", params={"tab": "upcoming"})).json()["items"]
    assert len(items) == 1
    return items[0]


async def _available(client, ctx, offset: int) -> int:
    day = _day(ctx, offset)
    data = (await client.get("/api/calendar", params={"from": day, "to": day})).json()
    return data["room_types"][0]["days"][0]["available"]


async def _expire(session, ctx) -> None:
    await session.execute(
        text(
            "UPDATE reservation SET option_expires_at = now() - interval '1 minute' "
            "WHERE tenant_id = :t AND status = 'tentative'"
        ),
        {"t": ctx["workspace"]["tenant"]["id"]},
    )
    await session.execute(
        text(
            "UPDATE paymentlink SET expires_at = now() - interval '1 minute' "
            "WHERE tenant_id = :t AND status = 'active'"
        ),
        {"t": ctx["workspace"]["tenant"]["id"]},
    )
    await session.commit()


async def _lapse(factory, ctx) -> int:
    tenant_id = ctx["workspace"]["tenant"]["id"]
    async with factory() as session:
        await bind_tenant(session, tenant_id)
        return await holds.lapse_due(session, _context(uuid.UUID(tenant_id), session))


async def _send(factory, ctx) -> int:
    tenant_id = ctx["workspace"]["tenant"]["id"]
    async with factory() as session:
        await bind_tenant(session, tenant_id)
        return await confirmation.send_pending(session, _context(uuid.UUID(tenant_id), session))


# ---- the page ------------------------------------------------------------------------


async def test_an_unpublished_page_is_a_404(pg_client, guest) -> None:
    await start_workspace(pg_client)
    room = await make_room_type(pg_client)
    rate = await make_rate_plan(pg_client, [room])
    await pg_client.put(
        SETUP, json={"slug": "villa-draft-x", "is_published": False, "sold_plan_ids": [rate["id"]]}
    )
    assert (await guest.get("/api/book/villa-draft-x")).status_code == 404


async def test_page_names_are_unique_and_reserved_names_refused(pg_client, other_client) -> None:
    ctx = await _page(pg_client)
    await start_workspace(other_client)
    taken = await other_client.put(
        SETUP, json={"slug": ctx["slug"], "is_published": False, "sold_plan_ids": []}
    )
    reserved = await other_client.put(
        SETUP, json={"slug": "admin", "is_published": False, "sold_plan_ids": []}
    )
    assert (taken.status_code, reserved.status_code) == (409, 409)


async def test_publishing_needs_a_plan_on_sale(pg_client) -> None:
    await start_workspace(pg_client)
    response = await pg_client.put(
        SETUP, json={"slug": "villa-empty", "is_published": True, "sold_plan_ids": []}
    )
    assert response.status_code == 409


async def test_setup_needs_its_permission(pg_client, other_client, pg_session) -> None:
    ctx = await _page(pg_client)
    await add_staff_member(pg_session, other_client, ctx["workspace"], role=None)
    assert (await other_client.get(SETUP)).status_code == 403
    denied = await other_client.put(
        SETUP, json={"slug": "villa-hijack", "is_published": False, "sold_plan_ids": []}
    )
    assert denied.status_code == 403


async def test_search_shows_price_terms_and_no_unit_counts(pg_client, guest) -> None:
    ctx = await _page(pg_client, units=3)
    found = await guest.get(
        f"/api/book/{ctx['slug']}/availability",
        params={"arrival": _day(ctx, 10), "departure": _day(ctx, 12), "adults": 2},
    )
    assert found.status_code == 200, found.text
    [room] = found.json()["rooms"]
    [option] = room["options"]
    assert (option["total"], option["deposit"]) == ("1000000.00", "500000")
    assert "units" not in room and "available" not in room


async def test_a_plan_not_for_sale_is_hidden_and_refused(pg_client, guest) -> None:
    ctx = await _page(pg_client)
    hidden = await make_rate_plan(pg_client, [ctx["room"]], name="Rahasia")
    await pg_client.put(
        SETUP,
        json={"slug": ctx["slug"], "is_published": True, "sold_plan_ids": [ctx["plan"]["id"]]},
    )
    found = await guest.get(
        f"/api/book/{ctx['slug']}/availability",
        params={"arrival": _day(ctx, 10), "departure": _day(ctx, 12)},
    )
    assert [o["name"] for o in found.json()["rooms"][0]["options"]] == [ctx["plan"]["name"]]
    refused = await guest.post(
        f"/api/book/{ctx['slug']}/checkout", json=_order(ctx, rate_plan_id=hidden["id"])
    )
    assert refused.json()["detail"]["code"] == "not_for_sale"


async def test_closed_dates_and_minimum_stay_are_honoured(pg_client, guest) -> None:
    ctx = await _page(pg_client)
    for change, offset in (({"kind": "close"}, 10), ({"kind": "set_min_stay", "nights": 3}, 20)):
        made = await pg_client.post(
            "/api/calendar/changes",
            json={
                "start": _day(ctx, offset),
                "end": _day(ctx, offset),
                "room_type_ids": [ctx["room"]["id"]],
                "change": change,
            },
        )
        assert made.status_code == 200, made.text
    params = {"arrival": _day(ctx, 10), "departure": _day(ctx, 11)}
    closed = await guest.get(f"/api/book/{ctx['slug']}/availability", params=params)
    assert closed.json()["unavailable_reason"] == "closed"
    params = {"arrival": _day(ctx, 20), "departure": _day(ctx, 21)}
    short = (await guest.get(f"/api/book/{ctx['slug']}/availability", params=params)).json()
    assert (short["unavailable_reason"], short["min_stay"]) == ("min_stay", 3)


async def test_the_calendar_marks_days_and_lowest_price(pg_client, guest) -> None:
    ctx = await _page(pg_client, units=1)
    await _book(guest, ctx)
    days = (
        await guest.get(
            f"/api/book/{ctx['slug']}/calendar",
            params={"from": _day(ctx, 9), "to": _day(ctx, 10)},
        )
    ).json()["days"]
    assert [d["available"] for d in days] == [True, False]
    assert days[0]["lowest_price"] == "500000.00"


# ---- holding ------------------------------------------------------------------------


async def test_checkout_holds_the_room_and_shows_for_staff(pg_client, guest) -> None:
    ctx = await _page(pg_client)
    result = await _book(guest, ctx)

    assert result["amount_due"] == "500000.00" and result["total"] == "1000000.00"
    assert await _available(pg_client, ctx, 10) == 1
    booking = await _staff_booking(pg_client)
    assert booking["status"] == "tentative"
    assert booking["hold_expires_at"] is not None
    assert booking["source"]["code"] == "direct_web"


async def test_staff_cannot_edit_or_take_money_on_a_hold(pg_client, guest) -> None:
    ctx = await _page(pg_client)
    await _book(guest, ctx)
    booking = await _staff_booking(pg_client)
    edited = await pg_client.patch(f"/api/bookings/{booking['id']}", json={"notes": "x"})
    paid = await pg_client.post(
        f"/api/bookings/{booking['id']}/payments",
        json={"amount": "1000", "method": "cash", "received_on": _day(ctx, 0)},
    )
    assert (edited.status_code, paid.status_code) == (409, 409)


async def test_the_last_unit_goes_to_one_guest(pg_client, guest, third_client) -> None:
    ctx = await _page(pg_client, units=1)
    first, second = await asyncio.gather(
        guest.post(f"/api/book/{ctx['slug']}/checkout", json=_order(ctx)),
        third_client.post(
            f"/api/book/{ctx['slug']}/checkout", json=_order(ctx, guest_phone="+6281234567002")
        ),
    )
    assert sorted((first.status_code, second.status_code)) == [201, 409]


async def test_a_changed_price_books_nothing(pg_client, guest) -> None:
    ctx = await _page(pg_client)
    response = await guest.post(
        f"/api/book/{ctx['slug']}/checkout", json=_order(ctx, expected_total="900000")
    )
    assert response.status_code == 409
    assert response.json()["detail"] == {"code": "price_changed", "total": "1000000.00"}
    assert (await pg_client.get("/api/bookings", params={"tab": "upcoming"})).json()["items"] == []


async def test_a_retried_submission_is_one_booking(pg_client, guest) -> None:
    ctx = await _page(pg_client)
    order = _order(ctx)
    url = f"/api/book/{ctx['slug']}/checkout"
    first = await guest.post(url, json=order)
    second = await guest.post(url, json=order)
    other = await guest.post(url, json={**order, "guest_name": "Lain"})

    assert first.json() == second.json()
    assert other.status_code == 422
    await _staff_booking(pg_client)  # exactly one


@pytest.mark.parametrize(
    ("over", "code"),
    [
        ({"accepted_terms": False}, "terms_required"),
        ({"guest_phone": "nomor-salah"}, "invalid_phone"),
        ({"adults": 9}, "too_many_guests"),
    ],
)
async def test_bad_orders_are_refused(pg_client, guest, over, code) -> None:
    ctx = await _page(pg_client)
    response = await guest.post(f"/api/book/{ctx['slug']}/checkout", json=_order(ctx, **over))
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == code


async def test_hold_limits_stop_fake_bookings(pg_client, guest, pg_session) -> None:
    ctx = await _page(pg_client, units=10)
    url = f"/api/book/{ctx['slug']}/checkout"
    await _book(guest, ctx)
    await _book(guest, ctx)
    by_phone = await guest.post(url, json=_order(ctx))
    assert by_phone.status_code == 429

    await _book(guest, ctx, guest_phone="+6281234567009")
    by_visitor = await guest.post(url, json=_order(ctx, guest_phone="+6281234567010"))
    assert by_visitor.status_code == 429
    assert by_visitor.json()["detail"]["code"] == "too_many_holds"


async def test_deposits_do_not_use_the_monthly_link_limit(pg_client, guest) -> None:
    ctx = await _page(pg_client)
    await _book(guest, ctx)
    used = (await pg_client.get("/api/workspace")).json()["usage"]["payment_links_used"]
    assert used == 0


# ---- paying -------------------------------------------------------------------------


async def test_paying_confirms_and_sends_whatsapp(pg_client, guest, pg_session_factory) -> None:
    ctx = await _page(pg_client)
    result = await _book(guest, ctx)
    await pay(guest, _pay_token(result))

    booking = await _staff_booking(pg_client)
    assert booking["status"] == "confirmed"
    assert (booking["paid_amount"], booking["balance_due"]) == ("500000.00", "500000.00")
    assert booking["confirmation_status"] == "pending"

    assert await _send(pg_session_factory, ctx) == 1
    assert await _send(pg_session_factory, ctx) == 0  # never twice
    assert (await _staff_booking(pg_client))["confirmation_status"] == "sent"
    [chat] = (await pg_client.get("/api/conversations")).json()["items"]
    messages = (await pg_client.get(f"/api/conversations/{chat['id']}/messages")).json()
    body = messages[-1]["body"]
    assert result["number"] in body and "Rp" in body and "/booking/" in body


async def test_a_failed_whatsapp_never_undoes_the_booking(
    pg_client, guest, pg_session, pg_session_factory, monkeypatch
) -> None:
    from app.messaging.provider import SendResult
    from app.messaging.simulator import SimulatedWhatsAppProvider

    async def refused(self, **_kwargs) -> SendResult:
        return SendResult(accepted=False, error="template_not_approved")

    monkeypatch.setattr(SimulatedWhatsAppProvider, "send_template", refused)
    ctx = await _page(pg_client)
    result = await _book(guest, ctx)
    await pay(guest, _pay_token(result))
    for _ in range(confirmation.MAX_ATTEMPTS):
        await _send(pg_session_factory, ctx)
        await pg_session.execute(
            text(
                "UPDATE reservation SET source_detail = source_detail #- "
                "'{confirmation,next_at}' WHERE tenant_id = :t"
            ),
            {"t": ctx["workspace"]["tenant"]["id"]},
        )
        await pg_session.commit()

    booking = await _staff_booking(pg_client)
    assert (booking["status"], booking["confirmation_status"]) == ("confirmed", "failed")


async def test_a_screenshot_extends_the_hold_and_approval_confirms(
    pg_client, guest, pg_session_factory
) -> None:
    ctx = await _page(pg_client)
    await set_bank_account(pg_client)
    result = await _book(guest, ctx)
    before = (await _staff_booking(pg_client))["hold_expires_at"]
    uploaded = await guest_uploads(guest, _pay_token(result))
    assert uploaded.status_code == 201, uploaded.text

    held = await _staff_booking(pg_client)
    assert held["status"] == "tentative" and held["hold_expires_at"] > before
    [proof] = (await pg_client.get("/api/transfer-proofs")).json()["items"]
    approved = await pg_client.post(f"/api/transfer-proofs/{proof['id']}/approve")
    assert approved.status_code == 200, approved.text

    booking = await _staff_booking(pg_client)
    assert (booking["status"], booking["paid_amount"]) == ("confirmed", "500000.00")


async def test_a_staff_payment_link_is_untouched(pg_client, guest) -> None:
    await start_workspace(pg_client)
    link = await make_link(pg_client)
    token = link["url"].rsplit("/", 1)[1]
    await pay(guest, token)
    assert (await guest.get(f"/api/pay/{token}")).json()["state"] == "paid"


# ---- lapsing ------------------------------------------------------------------------


async def test_an_unpaid_hold_lapses_and_gives_the_room_back(
    pg_client, guest, pg_session, pg_session_factory
) -> None:
    ctx = await _page(pg_client, units=1)
    await _book(guest, ctx)
    assert await _lapse(pg_session_factory, ctx) == 0  # not due yet

    await _expire(pg_session, ctx)
    assert await _lapse(pg_session_factory, ctx) == 1
    assert await _available(pg_client, ctx, 10) == 1
    assert await sold_matches_bookings(pg_session, ctx["workspace"]["tenant"]["id"])
    [gone] = (await pg_client.get("/api/bookings", params={"tab": "cancelled"})).json()["items"]
    assert gone["cancel_note"] == holds.LAPSED_NOTE


async def _late_payment(session, factory, ctx, result) -> None:
    """A QRIS charge started in time; the gateway's event lands after the hold lapsed."""
    from sqlmodel import select

    from app.models.tenant import Payment
    from app.services.gateway_events import PAID_EVENT, GatewayEvent, handle_gateway_event

    tenant_id = uuid.UUID(ctx["workspace"]["tenant"]["id"])
    async with factory() as own:
        await bind_tenant(own, tenant_id)
        payment = (await own.exec(select(Payment).where(Payment.tenant_id == tenant_id))).first()
        event = GatewayEvent(
            gateway_event_id=f"late-{uuid.uuid4().hex}",
            event_type=PAID_EVENT,
            gateway_reference=payment.gateway_reference,
            amount=payment.amount,
            signature_valid=True,
        )
        await handle_gateway_event(own, tenant_id, payment.gateway_account_id, event)


async def _start_charge(guest, token: str) -> None:
    started = await guest.post(f"/api/pay/{token}/payments", json={"method": "qris"})
    assert started.status_code == 201, started.text


async def test_a_late_payment_confirms_when_the_room_is_free(
    pg_client, guest, pg_session, pg_session_factory
) -> None:
    ctx = await _page(pg_client, units=1)
    result = await _book(guest, ctx)
    await _start_charge(guest, _pay_token(result))
    await _expire(pg_session, ctx)
    await _lapse(pg_session_factory, ctx)

    await _late_payment(pg_session, pg_session_factory, ctx, result)

    booking = await _staff_booking(pg_client)
    assert (booking["status"], booking["refund_due"]) == ("confirmed", False)
    assert await _available(pg_client, ctx, 10) == 0
    assert await sold_matches_bookings(pg_session, ctx["workspace"]["tenant"]["id"])


async def test_a_late_payment_never_overbooks(
    pg_client, guest, third_client, pg_session, pg_session_factory
) -> None:
    ctx = await _page(pg_client, units=1)
    result = await _book(guest, ctx)
    await _start_charge(guest, _pay_token(result))
    await _expire(pg_session, ctx)
    await _lapse(pg_session_factory, ctx)
    await _book(third_client, ctx, guest_phone="+6281234567003")  # the room went to someone else

    await _late_payment(pg_session, pg_session_factory, ctx, result)

    [late] = (await pg_client.get("/api/bookings", params={"tab": "cancelled"})).json()["items"]
    assert (late["status"], late["refund_due"]) == ("cancelled", True)
    assert await _available(pg_client, ctx, 10) == 0
    assert await sold_matches_bookings(pg_session, ctx["workspace"]["tenant"]["id"])


# ---- the guest's link ---------------------------------------------------------------


async def test_the_guest_sees_their_booking_with_a_masked_phone(pg_client, guest) -> None:
    ctx = await _page(pg_client)
    result = await _book(guest, ctx)
    response = await guest.get(_guest_api(result))
    view = response.json()

    assert response.headers["cache-control"] == "no-store"
    assert (view["status"], view["guest_name"]) == ("awaiting_payment", "Ayu Tamu")
    assert PHONE not in response.text and view["phone_hint"].endswith("7001")
    assert view["pay_url"] == result["pay_url"]


@pytest.mark.parametrize("token", ["nope", "A" * 43])
async def test_bad_guest_tokens_are_a_404(pg_client, guest, token: str) -> None:
    assert (await guest.get(f"/api/guest-booking/{token}")).status_code == 404


async def test_cancelling_an_unpaid_hold_closes_the_payment(pg_client, guest) -> None:
    ctx = await _page(pg_client, units=1)
    result = await _book(guest, ctx)
    cancelled = await guest.post(f"{_guest_api(result)}/cancel", json={})

    assert cancelled.json()["status"] == "cancelled"
    assert await _available(pg_client, ctx, 10) == 1
    assert (await guest.get(f"/api/pay/{_pay_token(result)}")).json()["state"] == "cancelled"


async def test_cancelling_in_the_free_period_flags_a_refund(pg_client, guest) -> None:
    ctx = await _page(pg_client, free_cancellation_days=3)
    result = await _book(guest, ctx)
    await pay(guest, _pay_token(result))
    view = (await guest.get(_guest_api(result))).json()
    assert view["refund_if_cancelled"] is True

    cancelled = await guest.post(f"{_guest_api(result)}/cancel", json={})

    assert (cancelled.json()["status"], cancelled.json()["refund_due"]) == ("cancelled", True)
    assert await _available(pg_client, ctx, 10) == 2
    again = await guest.post(f"{_guest_api(result)}/cancel", json={})
    assert again.status_code == 409


async def test_non_refundable_needs_explicit_acceptance(pg_client, guest) -> None:
    ctx = await _page(pg_client, non_refundable=True)
    result = await _book(guest, ctx)
    await pay(guest, _pay_token(result))
    url = f"{_guest_api(result)}/cancel"

    refused = await guest.post(url, json={})
    assert refused.json()["detail"]["code"] == "accept_no_refund"
    accepted = await guest.post(url, json={"accept_no_refund": True})
    assert (accepted.json()["status"], accepted.json()["refund_due"]) == ("cancelled", False)


async def test_staff_cancelling_a_hold_closes_its_payment(pg_client, guest) -> None:
    ctx = await _page(pg_client)
    result = await _book(guest, ctx)
    booking = await _staff_booking(pg_client)
    response = await pg_client.post(f"/api/bookings/{booking['id']}/cancel", json={})
    assert response.status_code == 200, response.text
    assert (await guest.get(f"/api/pay/{_pay_token(result)}")).json()["state"] == "cancelled"


async def test_another_tenant_cannot_see_a_direct_booking(pg_client, guest, other_client) -> None:
    ctx = await _page(pg_client)
    await _book(guest, ctx)
    await start_workspace(other_client)
    assert (await other_client.get("/api/bookings", params={"tab": "upcoming"})).json()[
        "items"
    ] == []
    assert (await other_client.get(SETUP)).json()["slug"] is None


async def test_settings_change_the_deposit(pg_client, guest, pg_session) -> None:
    ctx = await _page(pg_client)
    await set_business_settings(
        pg_session, ctx["workspace"]["property"]["id"], direct_deposit_percent=30
    )
    result = await _book(guest, ctx)
    assert result["amount_due"] == "300000.00"


async def test_a_second_payment_is_not_counted_and_flags_a_refund(
    pg_client, guest, pg_session_factory
) -> None:
    from sqlmodel import select

    from app.models.tenant import Payment
    from app.services.gateway_events import PAID_EVENT, GatewayEvent, handle_gateway_event

    ctx = await _page(pg_client)
    await set_bank_account(pg_client)
    result = await _book(guest, ctx)
    token = _pay_token(result)
    await _start_charge(guest, token)
    await guest_uploads(guest, token)
    [proof] = (await pg_client.get("/api/transfer-proofs")).json()["items"]
    await pg_client.post(f"/api/transfer-proofs/{proof['id']}/approve")

    tenant_id = uuid.UUID(ctx["workspace"]["tenant"]["id"])
    async with pg_session_factory() as own:
        await bind_tenant(own, tenant_id)
        charge = (
            await own.exec(
                select(Payment).where(Payment.tenant_id == tenant_id, Payment.method == "qris")
            )
        ).one()
        event = GatewayEvent(
            gateway_event_id=f"extra-{uuid.uuid4().hex}",
            event_type=PAID_EVENT,
            gateway_reference=charge.gateway_reference,
            amount=charge.amount,
            signature_valid=True,
        )
        await handle_gateway_event(own, tenant_id, charge.gateway_account_id, event)

    booking = await _staff_booking(pg_client)
    assert (booking["paid_amount"], booking["refund_due"]) == ("500000.00", True)


async def test_a_screenshot_extends_the_hold_only_once(pg_client, guest, pg_session) -> None:
    ctx = await _page(pg_client)
    await set_bank_account(pg_client)
    result = await _book(guest, ctx)
    token = _pay_token(result)
    await guest_uploads(guest, token, image("one"))
    await pg_session.execute(
        text(
            "UPDATE reservation SET option_expires_at = now() + interval '5 minutes' "
            "WHERE tenant_id = :t"
        ),
        {"t": ctx["workspace"]["tenant"]["id"]},
    )
    await pg_session.commit()
    before = (await _staff_booking(pg_client))["hold_expires_at"]

    await guest_uploads(guest, token, image("two"))

    assert (await _staff_booking(pg_client))["hold_expires_at"] == before


async def test_approving_a_proof_after_the_hold_lapsed_rescues_it(
    pg_client, guest, pg_session, pg_session_factory
) -> None:
    ctx = await _page(pg_client, units=1)
    await set_bank_account(pg_client)
    result = await _book(guest, ctx)
    await guest_uploads(guest, _pay_token(result))
    await _expire(pg_session, ctx)
    await _lapse(pg_session_factory, ctx)

    [proof] = (await pg_client.get("/api/transfer-proofs")).json()["items"]
    approved = await pg_client.post(f"/api/transfer-proofs/{proof['id']}/approve")

    assert approved.status_code == 200, approved.text
    assert (await _staff_booking(pg_client))["status"] == "confirmed"
    assert await sold_matches_bookings(pg_session, ctx["workspace"]["tenant"]["id"])


async def test_a_guest_cancel_racing_a_payment_is_a_clean_409(
    pg_client, guest, monkeypatch
) -> None:
    from app.services import guest_booking

    ctx = await _page(pg_client)
    result = await _book(guest, ctx)
    real = holds.cancel_hold

    async def paid_first(*args):
        await pay(guest, _pay_token(result))
        return await real(*args)

    monkeypatch.setattr(guest_booking.holds, "cancel_hold", paid_first)
    response = await guest.post(f"{_guest_api(result)}/cancel", json={})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "cannot_cancel"
    assert (await _staff_booking(pg_client))["status"] == "confirmed"


async def test_a_broken_send_stops_retrying(
    pg_client, guest, pg_session, pg_session_factory, monkeypatch
) -> None:
    async def broken(*_args):
        raise RuntimeError("boom")

    monkeypatch.setattr(confirmation, "_claim", broken)
    ctx = await _page(pg_client)
    result = await _book(guest, ctx)
    await pay(guest, _pay_token(result))
    for _ in range(confirmation.MAX_ATTEMPTS):
        await _send(pg_session_factory, ctx)
        await pg_session.execute(
            text(
                "UPDATE reservation SET source_detail = source_detail #- "
                "'{confirmation,next_at}' WHERE tenant_id = :t"
            ),
            {"t": ctx["workspace"]["tenant"]["id"]},
        )
        await pg_session.commit()
    assert (await _staff_booking(pg_client))["confirmation_status"] == "failed"


def test_ipv6_visitors_count_per_network() -> None:
    from app.services.direct_checkout import visitor_key

    assert visitor_key("2001:db8:1:2::a") == visitor_key("2001:db8:1:2::b")
    assert visitor_key("2001:db8:1:2::a") != visitor_key("2001:db8:1:3::a")
    assert visitor_key("::ffff:1.2.3.4") == visitor_key("1.2.3.4")
