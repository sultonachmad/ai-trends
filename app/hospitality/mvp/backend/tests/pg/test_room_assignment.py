"""Giving bookings real rooms: one room never holds two overlapping stays."""

import asyncio
import datetime as dt

import pytest
from sqlalchemy import text

from app.services.calendar_dates import property_today
from tests.pg.conftest import make_booking, make_rate_plan, make_room_type, start_workspace

pytestmark = pytest.mark.integration

DESK = "/api/front-desk"


async def _setup(client, units: int = 3) -> dict:
    workspace = await start_workspace(client)
    room = await make_room_type(client, units=units, max_guests=2)
    plan = await make_rate_plan(client, [room], amount=500000)
    today = property_today(workspace["property"]["timezone"])
    return {"workspace": workspace, "room": room, "plan": plan, "today": today}


def _on(ctx: dict, offset: int) -> str:
    return (ctx["today"] + dt.timedelta(days=offset)).isoformat()


async def _book(client, ctx, start: int, end: int, **overrides) -> dict:
    return await make_booking(
        client, ctx["room"], ctx["plan"], _on(ctx, start), _on(ctx, end), **overrides
    )


async def _lines(session, booking_id: str) -> list[str]:
    rows = await session.execute(
        text("SELECT id FROM reservationunit WHERE reservation_id = :b ORDER BY created_at, id"),
        {"b": booking_id},
    )
    return [str(row[0]) for row in rows.all()]


async def _assign(client, line_id: str, unit_id: str | None, **extra):
    return await client.put(f"{DESK}/lines/{line_id}/room", json={"unit_id": unit_id, **extra})


def _unit(ctx: dict, index: int = 0) -> str:
    return ctx["room"]["units"][index]["id"]


async def test_free_rooms_leave_out_a_clash_and_allow_back_to_back(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    first = await _book(pg_client, ctx, 2, 4)
    [line] = await _lines(pg_session, first["id"])
    assert (await _assign(pg_client, line, _unit(ctx))).status_code == 200

    clash = await _book(pg_client, ctx, 3, 5)
    after = await _book(pg_client, ctx, 4, 6)

    clashing = (await pg_client.get(f"{DESK}/bookings/{clash['id']}/free-rooms")).json()
    following = (await pg_client.get(f"{DESK}/bookings/{after['id']}/free-rooms")).json()
    assert _unit(ctx) not in [room["id"] for room in clashing]
    assert _unit(ctx) in [room["id"] for room in following]


async def test_a_clash_is_refused_clearly(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    first, second = await _book(pg_client, ctx, 2, 4), await _book(pg_client, ctx, 3, 5)
    [line_one], [line_two] = (
        await _lines(pg_session, first["id"]),
        await _lines(pg_session, second["id"]),
    )
    await _assign(pg_client, line_one, _unit(ctx))

    response = await _assign(pg_client, line_two, _unit(ctx))

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "room_taken"


async def test_two_staff_assigning_at_once_get_one_winner(
    pg_client, other_client, pg_session
) -> None:
    ctx = await _setup(pg_client)
    first, second = await _book(pg_client, ctx, 2, 4), await _book(pg_client, ctx, 2, 4)
    [line_one], [line_two] = (
        await _lines(pg_session, first["id"]),
        await _lines(pg_session, second["id"]),
    )

    answers = await asyncio.gather(
        _assign(pg_client, line_one, _unit(ctx)), _assign(pg_client, line_two, _unit(ctx))
    )

    assert sorted(answer.status_code for answer in answers) == [200, 409]


async def test_a_room_of_another_type_is_refused(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    other = await make_room_type(pg_client, name="Suite", units=1)
    booking = await _book(pg_client, ctx, 2, 4)
    [line] = await _lines(pg_session, booking["id"])

    response = await _assign(pg_client, line, other["units"][0]["id"])

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "wrong_room"


async def test_an_out_of_order_room_is_refused(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await pg_session.execute(
        text("UPDATE unit SET service_status = 'out_of_order' WHERE id = :u"), {"u": _unit(ctx)}
    )
    await pg_session.commit()
    booking = await _book(pg_client, ctx, 2, 4)
    [line] = await _lines(pg_session, booking["id"])

    response = await _assign(pg_client, line, _unit(ctx))

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "room_out_of_order"
    free = (await pg_client.get(f"{DESK}/bookings/{booking['id']}/free-rooms")).json()
    assert _unit(ctx) not in [room["id"] for room in free]


async def test_a_locked_room_is_not_moved_until_unlocked(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _book(pg_client, ctx, 2, 4)
    [line] = await _lines(pg_session, booking["id"])
    await _assign(pg_client, line, _unit(ctx, 0))
    locked = await pg_client.put(f"{DESK}/lines/{line}/lock", json={"locked": True})
    assert locked.status_code == 200, locked.text

    refused = await _assign(pg_client, line, _unit(ctx, 1))
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "room_locked"

    await pg_client.put(f"{DESK}/lines/{line}/lock", json={"locked": False})
    assert (await _assign(pg_client, line, _unit(ctx, 1))).status_code == 200


async def test_moving_an_in_house_guest_updates_both_rooms(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _book(pg_client, ctx, 0, 2)
    [line] = await _lines(pg_session, booking["id"])
    await _assign(pg_client, line, _unit(ctx, 0))
    assert (
        await pg_client.post(f"{DESK}/bookings/{booking['id']}/check-in", json={})
    ).status_code == 200

    moved = await _assign(pg_client, line, _unit(ctx, 1))

    assert moved.status_code == 200, moved.text
    rooms = {room["id"]: room for room in (await pg_client.get(f"{DESK}/today")).json()["rooms"]}
    assert (rooms[_unit(ctx, 0)]["fo_status"], rooms[_unit(ctx, 0)]["hk_status"]) == (
        "vacant",
        "dirty",
    )
    assert rooms[_unit(ctx, 1)]["fo_status"] == "occupied"
    assert rooms[_unit(ctx, 1)]["booking_id"] == booking["id"]
    logged = await pg_session.execute(
        text("SELECT count(*) FROM unitstatuslog WHERE unit_id = :u"), {"u": _unit(ctx, 0)}
    )
    assert logged.scalar_one() >= 3


async def test_an_in_house_guest_must_keep_a_room(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _book(pg_client, ctx, 0, 2)
    [line] = await _lines(pg_session, booking["id"])
    await _assign(pg_client, line, _unit(ctx))
    await pg_client.post(f"{DESK}/bookings/{booking['id']}/check-in", json={})

    response = await _assign(pg_client, line, None)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "room_required"


async def test_other_tenants_cannot_touch_a_line(pg_client, other_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await start_workspace(other_client)
    booking = await _book(pg_client, ctx, 2, 4)
    [line] = await _lines(pg_session, booking["id"])

    assert (await _assign(other_client, line, _unit(ctx))).status_code == 404
    assert (
        await other_client.get(f"{DESK}/bookings/{booking['id']}/free-rooms")
    ).status_code == 404
