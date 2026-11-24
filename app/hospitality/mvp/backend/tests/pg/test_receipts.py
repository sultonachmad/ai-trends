"""Check-out settles the bill and issues a numbered receipt that never changes."""

import asyncio
import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.services.calendar_dates import property_today
from tests.pg.conftest import make_booking, make_rate_plan, make_room_type, start_workspace

pytestmark = pytest.mark.integration

DESK = "/api/front-desk"
BILLS = "/api/bills"


async def _setup(client, units: int = 3) -> dict:
    workspace = await start_workspace(client)
    room = await make_room_type(client, units=units, max_guests=2)
    plan = await make_rate_plan(client, [room], amount=500000)
    today = property_today(workspace["property"]["timezone"])
    return {"workspace": workspace, "room": room, "plan": plan, "today": today}


async def _in_house(client, session, ctx, index: int = 0) -> dict:
    """A one-night stay that arrived yesterday and leaves today, checked in."""
    today = ctx["today"]
    booking = await make_booking(
        client,
        ctx["room"],
        ctx["plan"],
        (today - dt.timedelta(days=1)).isoformat(),
        today.isoformat(),
    )
    await session.execute(
        text(
            "UPDATE reservationunit SET unit_id = :u, status = 'in_house', "
            "checked_in_at = now() - interval '1 day' WHERE reservation_id = :b"
        ),
        {"u": ctx["room"]["units"][index]["id"], "b": booking["id"]},
    )
    await session.execute(
        text("UPDATE reservation SET status = 'in_house' WHERE id = :b"), {"b": booking["id"]}
    )
    await session.execute(
        text("UPDATE unit SET fo_status = 'occupied' WHERE id = :u"),
        {"u": ctx["room"]["units"][index]["id"]},
    )
    await session.commit()
    return booking


async def _pay(client, ctx, booking, amount="500000"):
    return await client.post(
        f"{BILLS}/{booking['id']}/payments",
        json={"amount": amount, "method": "cash", "received_on": ctx["today"].isoformat()},
    )


def _code(response) -> str:
    return response.json()["detail"]["code"]


async def test_check_out_is_blocked_while_money_is_owed(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _in_house(pg_client, pg_session, ctx)
    url = f"{DESK}/bookings/{booking['id']}/check-out"

    blocked = await pg_client.post(url, json={})
    await _pay(pg_client, ctx, booking)
    done = await pg_client.post(url, json={})

    assert (blocked.status_code, _code(blocked)) == (409, "balance_owed")
    assert done.status_code == 200, done.text


async def test_a_permitted_person_can_let_a_guest_leave_unpaid(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _in_house(pg_client, pg_session, ctx)

    response = await pg_client.post(
        f"{DESK}/bookings/{booking['id']}/check-out",
        json={"leave_unpaid_reason": "Dibayar besok lewat transfer"},
    )

    assert response.status_code == 200, response.text
    bill = (await pg_client.get(f"{BILLS}/{booking['id']}")).json()
    assert bill["left_unpaid"] is True
    assert Decimal(bill["balance"]) == 500000


async def test_check_out_issues_a_frozen_receipt(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _in_house(pg_client, pg_session, ctx)
    await pg_client.post(
        f"{BILLS}/{booking['id']}/charges",
        json={
            "category": "minibar",
            "description": "Air mineral",
            "quantity": 2,
            "unit_price": 10000,
        },
    )
    await _pay(pg_client, ctx, booking, "520000")
    await pg_client.post(f"{DESK}/bookings/{booking['id']}/check-out", json={})

    [summary] = (await pg_client.get(f"{BILLS}/{booking['id']}")).json()["receipts"]
    receipt = (await pg_client.get(f"{BILLS}/receipts/{summary['id']}")).json()
    year = ctx["today"].year

    assert receipt["number"] == f"KW-{year}-000001"
    assert [(line["description"], Decimal(line["amount"])) for line in receipt["lines"]] == [
        ("Deluxe", 500000),
        ("Air mineral", 20000),
    ]
    assert (Decimal(receipt["total"]), Decimal(receipt["paid"])) == (520000, 520000)
    await pg_session.execute(
        text(
            "UPDATE guest SET full_name = 'Nama Baru' WHERE id = "
            "(SELECT booker_guest_id FROM reservation WHERE id = :b)"
        ),
        {"b": booking["id"]},
    )
    await pg_session.commit()
    again = (await pg_client.get(f"{BILLS}/receipts/{summary['id']}")).json()
    assert again["guest_name"] == receipt["guest_name"] != "Nama Baru"


async def test_numbers_never_repeat_or_skip(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    first = await _in_house(pg_client, pg_session, ctx, 0)
    second = await _in_house(pg_client, pg_session, ctx, 1)
    for booking in (first, second):
        await _pay(pg_client, ctx, booking)

    await asyncio.gather(
        pg_client.post(f"{DESK}/bookings/{first['id']}/check-out", json={}),
        pg_client.post(f"{DESK}/bookings/{second['id']}/check-out", json={}),
    )

    numbers = sorted(
        [
            (await pg_client.get(f"{BILLS}/{b['id']}")).json()["receipts"][0]["number"]
            for b in (first, second)
        ]
    )
    year = ctx["today"].year
    assert numbers == [f"KW-{year}-000001", f"KW-{year}-000002"]


async def test_undo_keeps_the_receipt_and_a_new_check_out_issues_another(
    pg_client, pg_session
) -> None:
    ctx = await _setup(pg_client)
    booking = await _in_house(pg_client, pg_session, ctx)
    await _pay(pg_client, ctx, booking)
    url = f"{DESK}/bookings/{booking['id']}"
    await pg_client.post(f"{url}/check-out", json={})
    await pg_client.post(f"{url}/undo", json={"reason": "Belum pergi"})
    await pg_client.post(f"{url}/check-out", json={})

    receipts = (await pg_client.get(f"{BILLS}/{booking['id']}")).json()["receipts"]

    assert [r["number"][-6:] for r in receipts] == ["000001", "000002"]


async def test_overpaying_flags_a_refund(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _in_house(pg_client, pg_session, ctx)
    await _pay(pg_client, ctx, booking, "600000")

    await pg_client.post(f"{DESK}/bookings/{booking['id']}/check-out", json={})

    assert (await pg_client.get(f"/api/bookings/{booking['id']}")).json()["refund_due"] is True


async def test_an_issued_receipt_cannot_be_altered(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _in_house(pg_client, pg_session, ctx)
    await _pay(pg_client, ctx, booking)
    await pg_client.post(f"{DESK}/bookings/{booking['id']}/check-out", json={})
    [summary] = (await pg_client.get(f"{BILLS}/{booking['id']}")).json()["receipts"]

    for statement in (
        "UPDATE invoiceline SET amount = 1 WHERE invoice_id = :r",
        "UPDATE invoice SET paid_amount = 1 WHERE id = :r",
    ):
        with pytest.raises(Exception, match="immutable"):
            await pg_session.execute(text(statement), {"r": summary["id"]})
        await pg_session.rollback()


async def test_undo_clears_the_refund_flag_check_out_set(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _in_house(pg_client, pg_session, ctx)
    await _pay(pg_client, ctx, booking, "600000")
    url = f"{DESK}/bookings/{booking['id']}"
    await pg_client.post(f"{url}/check-out", json={})

    await pg_client.post(f"{url}/undo", json={"reason": "Salah hitung"})

    detail = (await pg_client.get(f"/api/bookings/{booking['id']}")).json()
    assert detail["refund_due"] is False


async def test_an_earlier_receipt_is_marked_replaced(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _in_house(pg_client, pg_session, ctx)
    await _pay(pg_client, ctx, booking)
    url = f"{DESK}/bookings/{booking['id']}"
    await pg_client.post(f"{url}/check-out", json={})
    await pg_client.post(f"{url}/undo", json={"reason": "Belum pergi"})
    await pg_client.post(f"{url}/check-out", json={})

    receipts = (await pg_client.get(f"{BILLS}/{booking['id']}")).json()["receipts"]

    assert [r["replaced"] for r in receipts] == [True, False]
