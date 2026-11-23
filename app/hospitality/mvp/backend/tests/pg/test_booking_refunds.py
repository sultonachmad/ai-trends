"""Refund flags: visible to staff, and cleared once the refund has been sent."""

import datetime as dt
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlmodel import select

from app.models.tenant import Payment
from app.services.calendar_dates import property_today
from app.services.gateway_events import PAID_EVENT, GatewayEvent, handle_gateway_event
from app.tenancy.session import bind_tenant
from tests.pg.conftest import (
    add_staff_member,
    make_rate_plan,
    make_room_type,
    pay,
    start_workspace,
)

pytestmark = pytest.mark.integration


async def _paid_then_cancelled(client, guest) -> dict:
    workspace = await start_workspace(client)
    room = await make_room_type(client, units=2, max_guests=2)
    plan = await make_rate_plan(client, [room], amount=500000, free_cancellation_days=3)
    slug = f"refund-{uuid.uuid4().hex[:8]}"
    await client.put(
        "/api/booking-page",
        json={"slug": slug, "is_published": True, "sold_plan_ids": [plan["id"]]},
    )
    today = property_today(workspace["property"]["timezone"])
    result = await guest.post(
        f"/api/book/{slug}/checkout",
        json={
            "idempotency_key": uuid.uuid4().hex,
            "arrival": (today + dt.timedelta(days=10)).isoformat(),
            "departure": (today + dt.timedelta(days=12)).isoformat(),
            "room_type_id": room["id"],
            "rate_plan_id": plan["id"],
            "adults": 2,
            "guest_name": "Tamu Refund",
            "guest_phone": "+6281234567077",
            "pay_choice": "deposit",
            "expected_total": "1000000",
            "accepted_terms": True,
        },
    )
    assert result.status_code == 201, result.text
    body = result.json()
    await pay(guest, body["pay_url"].rsplit("/", 1)[1])
    token = body["booking_path"].rsplit("/", 1)[1]
    cancelled = await guest.post(f"/api/guest-booking/{token}/cancel", json={})
    assert cancelled.json()["refund_due"] is True
    [booking] = (await client.get("/api/bookings", params={"tab": "cancelled"})).json()["items"]
    return {
        "workspace": workspace,
        "booking": booking,
        "today": today,
        "result": body,
        "guest_view": cancelled.json(),
    }


def _done(ctx: dict, **over) -> dict:
    return {"amount": "500000", "refunded_on": ctx["today"].isoformat(), "note": "BCA", **over}


async def test_marking_a_refund_done_clears_it_with_a_record(pg_client, guest, pg_session) -> None:
    ctx = await _paid_then_cancelled(pg_client, guest)
    url = f"/api/bookings/{ctx['booking']['id']}/refund-done"

    done = await pg_client.post(url, json=_done(ctx))

    assert done.status_code == 200, done.text
    body = done.json()
    assert body["refund_due"] is False
    assert (body["refund_done"]["amount"], body["refund_done"]["note"]) == ("500000", "BCA")
    assert (await pg_client.post(url, json=_done(ctx))).status_code == 409
    logged = (
        await pg_session.execute(
            text(
                "SELECT count(*) FROM tenantauditentry WHERE tenant_id = :t "
                "AND event_id = 'booking.refund_done'"
            ),
            {"t": ctx["workspace"]["tenant"]["id"]},
        )
    ).scalar_one()
    assert logged == 1


async def test_a_refund_cannot_be_dated_in_the_future(pg_client, guest) -> None:
    ctx = await _paid_then_cancelled(pg_client, guest)
    tomorrow = (ctx["today"] + dt.timedelta(days=1)).isoformat()
    response = await pg_client.post(
        f"/api/bookings/{ctx['booking']['id']}/refund-done",
        json=_done(ctx, refunded_on=tomorrow),
    )
    assert response.status_code == 422


async def test_marking_a_refund_needs_permission(
    pg_client, guest, other_client, pg_session
) -> None:
    ctx = await _paid_then_cancelled(pg_client, guest)
    await add_staff_member(pg_session, other_client, ctx["workspace"], role=None)
    response = await other_client.post(
        f"/api/bookings/{ctx['booking']['id']}/refund-done", json=_done(ctx)
    )
    assert response.status_code == 403


async def test_an_extra_payment_shows_for_review_until_refunded(
    pg_client, guest, pg_session_factory
) -> None:
    """The flag on the payment reaches the payment links page and clears with the refund."""
    workspace = await start_workspace(pg_client)
    room = await make_room_type(pg_client, units=2, max_guests=2)
    plan = await make_rate_plan(pg_client, [room], amount=500000)
    slug = f"extra-{uuid.uuid4().hex[:8]}"
    await pg_client.put(
        "/api/booking-page",
        json={"slug": slug, "is_published": True, "sold_plan_ids": [plan["id"]]},
    )
    today = property_today(workspace["property"]["timezone"])
    made = await guest.post(
        f"/api/book/{slug}/checkout",
        json={
            "idempotency_key": uuid.uuid4().hex,
            "arrival": (today + dt.timedelta(days=10)).isoformat(),
            "departure": (today + dt.timedelta(days=11)).isoformat(),
            "room_type_id": room["id"],
            "rate_plan_id": plan["id"],
            "adults": 1,
            "guest_name": "Tamu Dobel",
            "guest_phone": "+6281234567066",
            "pay_choice": "full",
            "expected_total": "500000",
            "accepted_terms": True,
        },
    )
    token = made.json()["pay_url"].rsplit("/", 1)[1]
    await guest.post(f"/api/pay/{token}/payments", json={"method": "qris"})
    await guest.post(
        f"/api/pay/{token}/payments", json={"method": "virtual_account", "bank": "BCA"}
    )
    await guest.post(f"/api/simulator/payments/{token}/pay")

    tenant_id = uuid.UUID(workspace["tenant"]["id"])
    async with pg_session_factory() as own:
        await bind_tenant(own, tenant_id)
        extra = (
            await own.exec(
                select(Payment).where(Payment.tenant_id == tenant_id, Payment.status != "captured")
            )
        ).first()
        event = GatewayEvent(
            gateway_event_id=f"extra-{uuid.uuid4().hex}",
            event_type=PAID_EVENT,
            gateway_reference=extra.gateway_reference,
            amount=extra.amount,
            signature_valid=True,
        )
        await handle_gateway_event(own, tenant_id, extra.gateway_account_id, event)

    [link] = (await pg_client.get("/api/payment-links")).json()["items"]
    assert link["needs_refund_review"] is True
    [booking] = (await pg_client.get("/api/bookings", params={"tab": "upcoming"})).json()["items"]
    assert (booking["paid_amount"], booking["refund_due"]) == ("500000.00", True)

    done = await pg_client.post(
        f"/api/bookings/{booking['id']}/refund-done",
        json={"amount": "500000", "refunded_on": today.isoformat()},
    )
    assert done.status_code == 200, done.text
    [link] = (await pg_client.get("/api/payment-links")).json()["items"]
    assert link["needs_refund_review"] is False
    assert done.json()["paid_amount"] == "500000.00"


async def test_a_refund_cannot_exceed_the_money_received(pg_client, guest) -> None:
    ctx = await _paid_then_cancelled(pg_client, guest)
    url = f"/api/bookings/{ctx['booking']['id']}/refund-done"

    too_much = await pg_client.post(url, json=_done(ctx, amount="500001"))

    assert too_much.status_code == 422
    still_due = await pg_client.get(f"/api/bookings/{ctx['booking']['id']}")
    assert still_due.json()["refund_due"] is True


async def test_a_later_refund_keeps_the_earlier_record(pg_client, guest, pg_session) -> None:
    ctx = await _paid_then_cancelled(pg_client, guest)
    booking_id = ctx["booking"]["id"]
    url = f"/api/bookings/{booking_id}/refund-done"
    assert (await pg_client.post(url, json=_done(ctx, amount="200000"))).status_code == 200
    await pg_session.execute(
        text(
            "UPDATE reservation SET source_detail = "
            "jsonb_set(source_detail::jsonb, '{refund_due}', 'true') WHERE id = :id"
        ),
        {"id": booking_id},
    )
    await pg_session.commit()

    over = await pg_client.post(url, json=_done(ctx, amount="300001"))
    second = await pg_client.post(url, json=_done(ctx, amount="300000", note="Kedua"))

    assert over.status_code == 422
    assert second.status_code == 200, second.text
    assert second.json()["refund_done"]["note"] == "Kedua"
    stored = (
        await pg_session.execute(
            text("SELECT source_detail FROM reservation WHERE id = :id"), {"id": booking_id}
        )
    ).scalar_one()
    assert [entry["amount"] for entry in stored["refund_history"]] == ["200000"]


async def test_a_cancelled_booking_shows_nothing_left_to_pay(pg_client, guest) -> None:
    ctx = await _paid_then_cancelled(pg_client, guest)

    detail = (await pg_client.get(f"/api/bookings/{ctx['booking']['id']}")).json()

    assert Decimal(ctx["booking"]["balance_due"]) == 0
    assert Decimal(detail["balance_due"]) == 0
    assert Decimal(detail["paid_amount"]) == 500000
    assert Decimal(ctx["guest_view"]["balance"]) == 0
