"""Service charge and PBJT on bills, receipts and online prices."""

import datetime as dt
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.services.calendar_dates import property_today
from tests.pg.conftest import make_booking, make_rate_plan, make_room_type, start_workspace

pytestmark = pytest.mark.integration

TAXES = "/api/settings/taxes"
BILLS = "/api/bills"
D = Decimal


async def _setup(client, mode: str | None = "plus_plus", **rates) -> dict:
    workspace = await start_workspace(client)
    room = await make_room_type(client, units=3, max_guests=2)
    plan = await make_rate_plan(client, [room], amount=500000)
    today = property_today(workspace["property"]["timezone"])
    ctx = {"workspace": workspace, "room": room, "plan": plan, "today": today}
    if mode:
        await _set_taxes(client, ctx, mode, **rates)
    return ctx


async def _set_taxes(client, ctx, mode, start=0, **rates) -> None:
    body = {
        "region_code": "51.03",
        "pbjt_pct": "10",
        "service_pct": "10",
        "pbjt_on_service": True,
        "price_mode": mode,
        "untaxed_categories": ["transport"],
        "effective_from": (ctx["today"] + dt.timedelta(days=start)).isoformat(),
        "confirmed": True,
        **rates,
    }
    saved = await client.put(TAXES, json=body)
    assert saved.status_code == 200, saved.text


def _on(ctx, offset: int) -> str:
    return (ctx["today"] + dt.timedelta(days=offset)).isoformat()


async def _booking(client, ctx, start=0, end=2) -> dict:
    return await make_booking(client, ctx["room"], ctx["plan"], _on(ctx, start), _on(ctx, end))


async def _bill(client, booking) -> dict:
    return (await client.get(f"{BILLS}/{booking['id']}")).json()


async def test_plus_plus_adds_service_and_tax_to_what_is_owed(pg_client) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx)

    bill = await _bill(pg_client, booking)
    detail = (await pg_client.get(f"/api/bookings/{booking['id']}")).json()

    assert (D(bill["taxes"]["service"]), D(bill["taxes"]["pbjt"])) == (D("100000"), D("110000"))
    assert bill["taxes"]["included"] is False
    assert D(bill["balance"]) == D("1210000") == D(detail["balance_due"])


async def test_nett_shows_what_the_price_includes(pg_client) -> None:
    ctx = await _setup(pg_client, mode="nett")
    booking = await _booking(pg_client, ctx)

    bill = await _bill(pg_client, booking)

    assert bill["taxes"]["included"] is True
    assert D(bill["taxes"]["service"]) + D(bill["taxes"]["pbjt"]) == D("173554")
    assert D(bill["balance"]) == D("1000000")


async def test_no_tax_before_the_owner_confirms(pg_client) -> None:
    ctx = await _setup(pg_client, mode=None)
    booking = await _booking(pg_client, ctx)

    bill = await _bill(pg_client, booking)

    assert (D(bill["taxes"]["service"]), D(bill["taxes"]["pbjt"])) == (0, 0)
    assert D(bill["balance"]) == D("1000000")


async def test_extras_discounts_and_untaxed_categories(pg_client) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx, 0, 1)
    url = f"{BILLS}/{booking['id']}"
    await pg_client.post(
        f"{url}/charges",
        json={"category": "laundry", "description": "Cuci", "quantity": 1, "unit_price": 100000},
    )
    await pg_client.post(
        f"{url}/charges",
        json={
            "category": "transport",
            "description": "Bandara",
            "quantity": 1,
            "unit_price": 200000,
        },
    )
    await pg_client.post(f"{url}/discounts", json={"amount": "100000", "reason": "Langganan"})

    bill = await _bill(pg_client, booking)

    # taxed base: room 500,000 + laundry 100,000 - discount 100,000 = 500,000
    assert (D(bill["taxes"]["service"]), D(bill["taxes"]["pbjt"])) == (D("50000"), D("55000"))
    assert D(bill["balance"]) == D("500000") + D("100000") + D("200000") - D("100000") + D("105000")


async def test_a_rate_change_applies_from_its_date(pg_client) -> None:
    ctx = await _setup(pg_client, service_pct="0")
    await _set_taxes(pg_client, ctx, "plus_plus", start=1, pbjt_pct="5", service_pct="0")
    booking = await _booking(pg_client, ctx, 0, 2)

    bill = await _bill(pg_client, booking)

    assert D(bill["taxes"]["pbjt"]) == D("50000") + D("25000")


async def test_switching_mode_never_changes_existing_bookings(pg_client) -> None:
    ctx = await _setup(pg_client, mode="nett")
    before = await _booking(pg_client, ctx)
    await _set_taxes(pg_client, ctx, "plus_plus")
    after = await _booking(pg_client, ctx)
    await pg_client.patch(f"/api/bookings/{before['id']}", json={"notes": "diubah"})

    assert D((await _bill(pg_client, before))["balance"]) == D("1000000")
    assert D((await _bill(pg_client, after))["balance"]) == D("1210000")


async def test_the_receipt_freezes_the_taxes(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await pg_session.execute(  # rates set yesterday, so last night's stay is taxed
        text("UPDATE taxrule SET effective_from = effective_from - 1 WHERE tenant_id = :t"),
        {"t": ctx["workspace"]["tenant"]["id"]},
    )
    await pg_session.commit()
    booking = await make_booking(pg_client, ctx["room"], ctx["plan"], _on(ctx, -1), _on(ctx, 0))
    await pg_session.execute(
        text(
            "UPDATE reservationunit SET unit_id = :u, status = 'in_house', "
            "checked_in_at = now() - interval '1 day' WHERE reservation_id = :b"
        ),
        {"u": ctx["room"]["units"][0]["id"], "b": booking["id"]},
    )
    await pg_session.execute(
        text("UPDATE reservation SET status = 'in_house' WHERE id = :b"), {"b": booking["id"]}
    )
    await pg_session.execute(
        text("UPDATE unit SET fo_status = 'occupied' WHERE id = :u"),
        {"u": ctx["room"]["units"][0]["id"]},
    )
    await pg_session.commit()
    await pg_client.post(
        f"{BILLS}/{booking['id']}/payments",
        json={"amount": "605000", "method": "cash", "received_on": _on(ctx, 0)},
    )

    out = await pg_client.post(f"/api/front-desk/bookings/{booking['id']}/check-out", json={})
    assert out.status_code == 200, out.text
    [summary] = (await _bill(pg_client, booking))["receipts"]
    receipt = (await pg_client.get(f"{BILLS}/receipts/{summary['id']}")).json()

    assert (D(receipt["subtotal"]), D(receipt["service"]), D(receipt["pbjt"])) == (
        D("500000"),
        D("50000"),
        D("55000"),
    )
    assert (D(receipt["total"]), D(receipt["balance"])) == (D("605000"), 0)
    await _set_taxes(pg_client, ctx, "plus_plus", pbjt_pct="5")
    again = (await pg_client.get(f"{BILLS}/receipts/{summary['id']}")).json()
    assert D(again["pbjt"]) == D("55000")


async def test_the_booking_page_charges_the_final_price(pg_client, guest) -> None:
    ctx = await _setup(pg_client)
    slug = f"pajak-{uuid.uuid4().hex[:8]}"
    await pg_client.put(
        "/api/booking-page",
        json={"slug": slug, "is_published": True, "sold_plan_ids": [ctx["plan"]["id"]]},
    )
    search = await guest.get(
        f"/api/book/{slug}/availability",
        params={"arrival": _on(ctx, 10), "departure": _on(ctx, 11), "adults": 2},
    )
    assert search.status_code == 200, search.text
    [option] = search.json()["rooms"][0]["options"]
    assert (D(option["total"]), D(option["tax"])) == (D("605000"), D("105000"))

    made = await guest.post(
        f"/api/book/{slug}/checkout",
        json={
            "idempotency_key": uuid.uuid4().hex,
            "arrival": _on(ctx, 10),
            "departure": _on(ctx, 11),
            "room_type_id": ctx["room"]["id"],
            "rate_plan_id": ctx["plan"]["id"],
            "adults": 2,
            "guest_name": "Tamu Pajak",
            "guest_phone": "+6281234567099",
            "pay_choice": "full",
            "expected_total": "605000",
            "accepted_terms": True,
        },
    )
    assert made.status_code == 201, made.text
    assert D(made.json()["amount_due"]) == D("605000")


async def test_checkout_reports_the_total_it_charges(pg_client, guest) -> None:
    ctx = await _setup(pg_client)
    slug = f"total-{uuid.uuid4().hex[:8]}"
    await pg_client.put(
        "/api/booking-page",
        json={"slug": slug, "is_published": True, "sold_plan_ids": [ctx["plan"]["id"]]},
    )
    made = await guest.post(
        f"/api/book/{slug}/checkout",
        json={
            "idempotency_key": uuid.uuid4().hex,
            "arrival": _on(ctx, 10),
            "departure": _on(ctx, 11),
            "room_type_id": ctx["room"]["id"],
            "rate_plan_id": ctx["plan"]["id"],
            "adults": 2,
            "guest_name": "Tamu Total",
            "guest_phone": "+6281234567098",
            "pay_choice": "full",
            "expected_total": "605000",
            "accepted_terms": True,
        },
    )

    assert made.status_code == 201, made.text
    assert D(made.json()["total"]) == D(made.json()["amount_due"]) == D("605000")


async def test_lists_show_the_total_with_tax(pg_client) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx, 0, 1)
    await pg_client.post(
        f"{BILLS}/{booking['id']}/charges",
        json={"category": "laundry", "description": "Cuci", "quantity": 1, "unit_price": 100000},
    )

    detail = (await pg_client.get(f"/api/bookings/{booking['id']}")).json()
    [entry] = (await pg_client.get("/api/front-desk/today")).json()["arrivals"]

    assert D(detail["total_with_tax"]) == D(entry["total_with_tax"]) == D("605000")


async def test_the_public_calendar_shows_final_prices(pg_client, guest) -> None:
    ctx = await _setup(pg_client)
    slug = f"kal-{uuid.uuid4().hex[:8]}"
    await pg_client.put(
        "/api/booking-page",
        json={"slug": slug, "is_published": True, "sold_plan_ids": [ctx["plan"]["id"]]},
    )
    calendar = await guest.get(
        f"/api/book/{slug}/calendar", params={"from": _on(ctx, 5), "to": _on(ctx, 6)}
    )

    assert calendar.status_code == 200, calendar.text
    assert D(calendar.json()["days"][0]["lowest_price"]) == D("605000")


async def test_a_rate_change_updates_open_bookings(pg_client) -> None:
    ctx = await _setup(pg_client, service_pct="0")
    booking = await _booking(pg_client, ctx, 0, 2)

    await _set_taxes(pg_client, ctx, "plus_plus", start=1, pbjt_pct="5", service_pct="0")

    detail = (await pg_client.get(f"/api/bookings/{booking['id']}")).json()
    assert D(detail["balance_due"]) == D("1000000") + D("50000") + D("25000")


async def test_nett_receipts_still_record_their_tax(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client, mode="nett")
    await pg_session.execute(
        text("UPDATE taxrule SET effective_from = effective_from - 1 WHERE tenant_id = :t"),
        {"t": ctx["workspace"]["tenant"]["id"]},
    )
    await pg_session.commit()
    booking = await make_booking(pg_client, ctx["room"], ctx["plan"], _on(ctx, -1), _on(ctx, 0))
    for sql in (
        "UPDATE reservationunit SET unit_id = :u, status = 'in_house' WHERE reservation_id = :b",
        "UPDATE reservation SET status = 'in_house' WHERE id = :b",
    ):
        await pg_session.execute(
            text(sql), {"u": ctx["room"]["units"][0]["id"], "b": booking["id"]}
        )
    await pg_session.commit()
    await pg_client.post(
        f"{BILLS}/{booking['id']}/payments",
        json={"amount": "500000", "method": "cash", "received_on": _on(ctx, 0)},
    )
    await pg_client.post(f"/api/front-desk/bookings/{booking['id']}/check-out", json={})

    [summary] = (await _bill(pg_client, booking))["receipts"]
    stored = await pg_session.execute(
        text("SELECT tax_total, total FROM invoice WHERE id = :r"), {"r": summary["id"]}
    )
    tax_total, total = stored.one()
    assert (D(tax_total), D(total)) == (D("86777"), D("500000"))
