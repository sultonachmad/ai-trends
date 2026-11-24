"""One rule for what a guest owes: room nights unless the channel was paid, plus extras."""

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.services.calendar_dates import property_today
from tests.pg.conftest import make_booking, make_rate_plan, make_room_type, start_workspace

pytestmark = pytest.mark.integration

BOOKINGS = "/api/bookings"
BILLS = "/api/bills"


async def _setup(client) -> dict:
    workspace = await start_workspace(client)
    room = await make_room_type(client, units=3, max_guests=2)
    plan = await make_rate_plan(client, [room], amount=500000)
    today = property_today(workspace["property"]["timezone"])
    return {"workspace": workspace, "room": room, "plan": plan, "today": today}


def _on(ctx: dict, offset: int) -> str:
    return (ctx["today"] + dt.timedelta(days=offset)).isoformat()


async def _booking(client, ctx, start=1, end=3) -> dict:
    return await make_booking(client, ctx["room"], ctx["plan"], _on(ctx, start), _on(ctx, end))


async def _collected_by(session, booking_id: str, model: str) -> None:
    await session.execute(
        text("UPDATE reservation SET payment_collect_model = :m WHERE id = :b"),
        {"m": model, "b": booking_id},
    )
    await session.commit()


async def _detail(client, booking_id: str) -> dict:
    return (await client.get(f"{BOOKINGS}/{booking_id}")).json()


async def test_a_channel_paid_booking_owes_nothing_for_the_room(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx)
    await _collected_by(pg_session, booking["id"], "channel")
    await pg_client.patch(f"{BOOKINGS}/{booking['id']}", json={"notes": "dibayar di kanal"})

    detail = await _detail(pg_client, booking["id"])

    assert (Decimal(detail["balance_due"]), detail["payment_state"]) == (0, "paid")
    bill = (await pg_client.get(f"{BILLS}/{booking['id']}")).json()
    assert bill["paid_to_channel"] is True
    assert Decimal(bill["balance"]) == 0


async def test_a_mixed_booking_still_owes_the_room(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx)
    await _collected_by(pg_session, booking["id"], "mixed")
    await pg_client.patch(f"{BOOKINGS}/{booking['id']}", json={"notes": "campuran"})

    assert Decimal((await _detail(pg_client, booking["id"]))["balance_due"]) == 1000000


async def test_extras_and_payments_move_the_balance(pg_client) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx)
    url = f"{BILLS}/{booking['id']}"

    charged = await pg_client.post(
        f"{url}/charges",
        json={
            "category": "laundry",
            "description": "Cuci 2 kg",
            "quantity": 2,
            "unit_price": 25000,
        },
    )
    assert charged.status_code == 200, charged.text
    assert Decimal((await _detail(pg_client, booking["id"]))["balance_due"]) == 1050000

    paid = await pg_client.post(
        f"{url}/payments",
        json={"amount": "300000", "method": "card", "received_on": _on(ctx, 0)},
    )
    assert paid.status_code == 200, paid.text
    detail = await _detail(pg_client, booking["id"])
    assert (Decimal(detail["balance_due"]), detail["payment_state"]) == (750000, "partly_paid")

    changed = await pg_client.patch(f"{BOOKINGS}/{booking['id']}", json={"departure": _on(ctx, 4)})
    assert changed.status_code == 200, changed.text
    assert Decimal(changed.json()["balance_due"]) == 1250000


async def test_removing_a_payment_keeps_extras_in_the_balance(pg_client) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx)
    url = f"{BILLS}/{booking['id']}"
    await pg_client.post(
        f"{url}/charges",
        json={
            "category": "other",
            "description": "Sewa motor",
            "quantity": 1,
            "unit_price": 100000,
        },
    )
    paid = await pg_client.post(
        f"{url}/payments", json={"amount": "100000", "method": "cash", "received_on": _on(ctx, 0)}
    )
    [payment] = (await pg_client.get(url)).json()["payments"]

    removed = await pg_client.delete(f"{BOOKINGS}/{booking['id']}/payments/{payment['id']}")

    assert paid.status_code == 200 and removed.status_code == 200, removed.text
    assert Decimal(removed.json()["balance_due"]) == 1100000
