"""One property can never read or change another property's calendar."""

import datetime as dt

import pytest
from sqlalchemy import text

from app.services.calendar_dates import property_today
from tests.pg.conftest import make_rate_plan, make_room_type, start_workspace

pytestmark = pytest.mark.integration

CALENDAR = "/api/calendar"
CHANGES = "/api/calendar/changes"


async def _property(client, name: str) -> dict:
    workspace = await start_workspace(client)
    room = await make_room_type(client, name=name)
    plan = await make_rate_plan(client, [room])
    today = property_today(workspace["property"]["timezone"])
    return {"workspace": workspace, "room": room, "plan": plan, "today": today}


def _window(today: dt.date) -> dict[str, str]:
    return {"from": today.isoformat(), "to": (today + dt.timedelta(days=2)).isoformat()}


async def test_each_property_sees_only_its_own_calendar(pg_client, other_client) -> None:
    mine = await _property(pg_client, "Milik Saya")
    theirs = await _property(other_client, "Milik Mereka")

    my_view = (await pg_client.get(CALENDAR, params=_window(mine["today"]))).json()
    their_view = (await other_client.get(CALENDAR, params=_window(theirs["today"]))).json()

    assert [room["name"] for room in my_view["room_types"]] == ["Milik Saya"]
    assert [room["name"] for room in their_view["room_types"]] == ["Milik Mereka"]


async def test_changes_cannot_name_another_propertys_rooms_or_plans(
    pg_client, other_client, pg_session
) -> None:
    mine = await _property(pg_client, "Milik Saya")
    theirs = await _property(other_client, "Milik Mereka")
    day = mine["today"].isoformat()

    their_room = await pg_client.post(
        CHANGES,
        json={
            "start": day,
            "end": day,
            "room_type_ids": [theirs["room"]["id"]],
            "change": {"kind": "close"},
        },
    )
    their_plan = await pg_client.post(
        CHANGES,
        json={
            "start": day,
            "end": day,
            "room_type_ids": [mine["room"]["id"]],
            "change": {"kind": "set_price", "rate_plan_id": theirs["plan"]["id"], "amount": 1},
        },
    )
    mixed = await pg_client.post(
        CHANGES,
        json={
            "start": day,
            "end": day,
            "room_type_ids": [mine["room"]["id"], theirs["room"]["id"]],
            "change": {"kind": "close"},
        },
    )

    assert (their_room.status_code, their_plan.status_code, mixed.status_code) == (422, 422, 422)
    their_view = (await other_client.get(CALENDAR, params=_window(theirs["today"]))).json()
    assert not any(d["closed"] for d in their_view["room_types"][0]["days"])
    my_view = (await pg_client.get(CALENDAR, params=_window(mine["today"]))).json()
    assert not any(d["closed"] for d in my_view["room_types"][0]["days"])  # mixed did nothing
    rows = (
        await pg_session.execute(
            text("SELECT count(*) FROM restriction WHERE tenant_id IN (:a, :b)"),
            {"a": mine["workspace"]["tenant"]["id"], "b": theirs["workspace"]["tenant"]["id"]},
        )
    ).scalar_one()
    assert rows == 0


async def test_my_changes_do_not_touch_the_other_calendar(pg_client, other_client) -> None:
    mine = await _property(pg_client, "Milik Saya")
    theirs = await _property(other_client, "Milik Mereka")
    day = mine["today"].isoformat()

    await pg_client.post(
        CHANGES,
        json={
            "start": day,
            "end": day,
            "room_type_ids": [mine["room"]["id"]],
            "change": {"kind": "set_price", "rate_plan_id": mine["plan"]["id"], "amount": 990000},
        },
    )

    their_view = (await other_client.get(CALENDAR, params=_window(theirs["today"]))).json()
    assert their_view["room_types"][0]["days"][0]["prices"][0]["amount"] == "500000.00"
