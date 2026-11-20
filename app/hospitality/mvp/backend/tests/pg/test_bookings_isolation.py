"""One property can never read or change another property's bookings."""

import datetime as dt

import pytest

from app.services.calendar_dates import property_today
from tests.pg.conftest import (
    guest_says,
    make_booking,
    make_rate_plan,
    make_room_type,
    sold_matches_bookings,
    start_workspace,
)

pytestmark = pytest.mark.integration

BOOKINGS = "/api/bookings"


async def _property(client, guest_name: str) -> dict:
    workspace = await start_workspace(client)
    room = await make_room_type(client, units=1)
    plan = await make_rate_plan(client, [room])
    today = property_today(workspace["property"]["timezone"])
    days = [(today + dt.timedelta(days=n)).isoformat() for n in range(10)]
    booking = await make_booking(client, room, plan, days[1], days[3], guest_name=guest_name)
    return {"workspace": workspace, "room": room, "plan": plan, "days": days, "booking": booking}


async def test_each_property_lists_only_its_own_bookings(pg_client, other_client) -> None:
    await _property(pg_client, "Tamu Saya")
    await _property(other_client, "Tamu Mereka")

    mine = (await pg_client.get(BOOKINGS, params={"tab": "upcoming"})).json()["items"]
    found = (await pg_client.get(BOOKINGS, params={"tab": "upcoming", "q": "Mereka"})).json()

    assert [b["guest"]["name"] for b in mine] == ["Tamu Saya"]
    assert found["items"] == []


async def test_another_propertys_booking_cannot_be_read_or_touched(
    pg_client, other_client, pg_session
) -> None:
    mine = await _property(pg_client, "Tamu Saya")
    theirs = await _property(other_client, "Tamu Mereka")
    target = f"{BOOKINGS}/{theirs['booking']['id']}"
    paid = (
        await other_client.post(
            f"{target}/payments",
            json={"amount": 1000, "method": "cash", "received_on": theirs["days"][0]},
        )
    ).json()

    statuses = [
        (await pg_client.get(target)).status_code,
        (await pg_client.patch(target, json={"notes": "dicuri"})).status_code,
        (await pg_client.post(f"{target}/cancel", json={})).status_code,
        (
            await pg_client.post(
                f"{target}/payments",
                json={"amount": 1000, "method": "cash", "received_on": mine["days"][0]},
            )
        ).status_code,
        (await pg_client.delete(f"{target}/payments/{paid['payments'][0]['id']}")).status_code,
    ]

    assert statuses == [404] * 5
    after = (await other_client.get(target)).json()
    assert (after["status"], after["notes"], after["paid_amount"]) == ("confirmed", None, "1000.00")
    assert await sold_matches_bookings(pg_session, theirs["workspace"]["tenant"]["id"])


async def test_a_booking_cannot_borrow_another_propertys_rooms_chat_or_payment(
    pg_client, other_client
) -> None:
    mine = await _property(pg_client, "Tamu Saya")
    theirs = await _property(other_client, "Tamu Mereka")
    their_chat = (await guest_says(other_client, "Halo", phone="+6281200000077"))["conversation_id"]
    base = {
        "arrival": mine["days"][5],
        "departure": mine["days"][6],
        "room_type_id": mine["room"]["id"],
        "rate_plan_id": mine["plan"]["id"],
        "guest_name": "X",
    }

    statuses = [
        (await pg_client.post(BOOKINGS, json={**base, **change})).status_code
        for change in (
            {"room_type_id": theirs["room"]["id"]},
            {"rate_plan_id": theirs["plan"]["id"]},
            {"conversation_id": their_chat},
        )
    ]
    quote = await pg_client.post(
        f"{BOOKINGS}/quote",
        json={
            **{k: base[k] for k in ("arrival", "departure", "room_type_id", "rate_plan_id")},
            "exclude_booking_id": theirs["booking"]["id"],
        },
    )
    move = await pg_client.patch(
        f"{BOOKINGS}/{mine['booking']['id']}", json={"room_type_id": theirs["room"]["id"]}
    )

    assert statuses == [422, 422, 404]
    assert quote.status_code == 200  # the foreign id is simply not found, nothing is revealed
    assert move.status_code == 422


async def test_a_guest_number_is_matched_within_the_property_only(pg_client, other_client) -> None:
    mine = await _property(pg_client, "Tamu Saya")
    theirs = await _property(other_client, "Tamu Mereka")
    await make_booking(
        other_client,
        theirs["room"],
        theirs["plan"],
        theirs["days"][5],
        theirs["days"][6],
        guest_name="Nama Rahasia",
        guest_phone="081299999999",
    )

    booking = await make_booking(
        pg_client,
        mine["room"],
        mine["plan"],
        mine["days"][5],
        mine["days"][6],
        guest_name="Nama Saya",
        guest_phone="081299999999",
    )

    assert booking["guest"]["name"] == "Nama Saya"
