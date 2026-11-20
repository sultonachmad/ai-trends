"""The calendar: what is sellable, at what price, on which dates — and changing it."""

import asyncio
import datetime as dt
import time

import pytest
from sqlalchemy import text

from app.services.calendar_dates import property_today
from tests.pg.conftest import (
    make_rate_plan,
    make_room_type,
    set_business_settings,
    start_workspace,
)

pytestmark = pytest.mark.integration

CALENDAR = "/api/calendar"
CHANGES = "/api/calendar/changes"
MISSING = "00000000-0000-0000-0000-000000000000"


def _day(today: dt.date, offset: int) -> str:
    return (today + dt.timedelta(days=offset)).isoformat()


async def _setup(client, *, units: int = 3, amount: int = 500000) -> dict:
    """A workspace with one room type sold on one rate plan."""
    workspace = await start_workspace(client)
    room = await make_room_type(client, units=units)
    plan = await make_rate_plan(client, [room], amount=amount)
    today = property_today(workspace["property"]["timezone"])
    return {"workspace": workspace, "room": room, "plan": plan, "today": today}


async def _read(client, today: dt.date, first: int = 0, last: int = 6) -> dict:
    response = await client.get(
        CALENDAR, params={"from": _day(today, first), "to": _day(today, last)}
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _change(client, ctx: dict, change: dict, first: int = 0, last: int = 0, **more):
    body = {
        "start": _day(ctx["today"], first),
        "end": _day(ctx["today"], last),
        "room_type_ids": [ctx["room"]["id"]],
        "change": change,
        **more,
    }
    return await client.post(CHANGES, json=body)


def _days(calendar: dict, room_index: int = 0) -> list[dict]:
    return calendar["room_types"][room_index]["days"]


def _amounts(calendar: dict) -> list[str]:
    return [day["prices"][0]["amount"] for day in _days(calendar)]


# ---- reading ----------------------------------------------------------------------------


async def test_requires_sign_in(pg_client) -> None:
    assert (
        await pg_client.get(CALENDAR, params={"from": "2026-01-01", "to": "2026-01-02"})
    ).status_code == 401


async def test_empty_property_has_an_empty_calendar(pg_client) -> None:
    workspace = await start_workspace(pg_client)
    today = property_today(workspace["property"]["timezone"])

    calendar = await _read(pg_client, today)

    assert calendar["room_types"] == []
    assert calendar["today"] == today.isoformat()
    assert calendar["last_editable_date"] == _day(today, 364)


async def test_defaults_come_from_units_and_base_prices(pg_client) -> None:
    ctx = await _setup(pg_client, units=3, amount=750000)

    calendar = await _read(pg_client, ctx["today"], 0, 2)

    [room] = calendar["room_types"]
    assert (room["id"], room["name"], room["units"]) == (ctx["room"]["id"], "Deluxe", 3)
    assert room["rate_plans"] == [{"id": ctx["plan"]["id"], "name": "Harga Normal"}]
    assert [day["date"] for day in room["days"]] == [_day(ctx["today"], n) for n in range(3)]
    assert room["days"][0] == {
        "date": ctx["today"].isoformat(),
        "available": 3,
        "closed": False,
        "min_stay": None,
        "prices": [
            {"rate_plan_id": ctx["plan"]["id"], "amount": "750000.00", "is_override": False}
        ],
    }


async def test_only_things_in_use_are_shown(pg_client) -> None:
    ctx = await _setup(pg_client)
    old_room = await make_room_type(pg_client, name="Lama")
    old_plan = await make_rate_plan(pg_client, [ctx["room"]], name="Promo Lama")
    unsold = await make_room_type(pg_client, name="Belum Dijual")
    await pg_client.patch(f"/api/room-types/{old_room['id']}", json={"is_active": False})
    await pg_client.patch(f"/api/rate-plans/{old_plan['id']}", json={"is_active": False})
    await pg_client.patch(f"/api/room-types/{ctx['room']['id']}", json={"units": 1})

    calendar = await _read(pg_client, ctx["today"], 0, 0)

    assert [room["name"] for room in calendar["room_types"]] == ["Deluxe", "Belum Dijual"]
    deluxe, not_sold = calendar["room_types"]
    assert [plan["name"] for plan in deluxe["rate_plans"]] == ["Harga Normal"]
    assert deluxe["days"][0]["available"] == 1
    assert (not_sold["id"], not_sold["rate_plans"], not_sold["days"][0]["prices"]) == (
        unsold["id"],
        [],
        [],
    )


@pytest.mark.parametrize(
    "params",
    [
        {"from": "2026-05-02", "to": "2026-05-01"},
        {"from": "2026-01-01", "to": "2026-06-30"},
        {"from": "not-a-date", "to": "2026-05-01"},
        {"from": "2026-05-01"},
    ],
)
async def test_bad_read_windows_are_refused(pg_client, params) -> None:
    await start_workspace(pg_client)

    assert (await pg_client.get(CALENDAR, params=params)).status_code == 422


async def test_the_past_can_be_read(pg_client) -> None:
    ctx = await _setup(pg_client)

    calendar = await _read(pg_client, ctx["today"], -3, -1)

    assert len(_days(calendar)) == 3


# ---- prices -----------------------------------------------------------------------------


async def test_set_price_for_a_range(pg_client) -> None:
    ctx = await _setup(pg_client, amount=500000)

    response = await _change(
        pg_client,
        ctx,
        {"kind": "set_price", "rate_plan_id": ctx["plan"]["id"], "amount": 800000},
        1,
        2,
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"dates": 2, "room_types": 1}
    calendar = await _read(pg_client, ctx["today"], 0, 3)
    assert _amounts(calendar) == ["500000.00", "800000.00", "800000.00", "500000.00"]
    assert [day["prices"][0]["is_override"] for day in _days(calendar)] == [
        False,
        True,
        True,
        False,
    ]


async def test_only_chosen_weekdays_change(pg_client) -> None:
    ctx = await _setup(pg_client)
    weekend = [4, 5]  # Friday, Saturday

    response = await _change(
        pg_client,
        ctx,
        {"kind": "set_price", "rate_plan_id": ctx["plan"]["id"], "amount": 900000},
        0,
        13,
        weekdays=weekend,
    )

    assert response.json()["dates"] == 4
    calendar = await _read(pg_client, ctx["today"], 0, 13)
    for day in _days(calendar):
        is_weekend = dt.date.fromisoformat(day["date"]).weekday() in weekend
        assert day["prices"][0]["amount"] == ("900000.00" if is_weekend else "500000.00")


async def test_the_last_change_wins_and_clearing_returns_to_base(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    plan_id = ctx["plan"]["id"]
    await _change(
        pg_client, ctx, {"kind": "set_price", "rate_plan_id": plan_id, "amount": 800000}, 0, 4
    )
    await _change(
        pg_client, ctx, {"kind": "set_price", "rate_plan_id": plan_id, "amount": 950000}, 2, 3
    )

    cleared = await _change(pg_client, ctx, {"kind": "clear_price", "rate_plan_id": plan_id}, 4, 6)

    assert cleared.status_code == 200
    calendar = await _read(pg_client, ctx["today"], 0, 5)
    assert _amounts(calendar) == [
        "800000.00",
        "800000.00",
        "950000.00",
        "950000.00",
        "500000.00",
        "500000.00",
    ]
    rows = (
        await pg_session.execute(
            text("SELECT count(*) FROM ratedaily WHERE tenant_id = :t"),
            {"t": ctx["workspace"]["tenant"]["id"]},
        )
    ).scalar_one()
    assert rows == 4  # one row per overridden date, nothing left behind


async def test_setting_the_base_price_stores_no_override(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client, amount=500000)
    plan_id = ctx["plan"]["id"]
    await _change(pg_client, ctx, {"kind": "set_price", "rate_plan_id": plan_id, "amount": 700000})

    await _change(pg_client, ctx, {"kind": "set_price", "rate_plan_id": plan_id, "amount": 500000})

    calendar = await _read(pg_client, ctx["today"], 0, 0)
    assert _days(calendar)[0]["prices"][0] == {
        "rate_plan_id": plan_id,
        "amount": "500000.00",
        "is_override": False,
    }


async def test_base_price_change_moves_only_dates_without_an_override(pg_client) -> None:
    ctx = await _setup(pg_client, amount=500000)
    plan_id = ctx["plan"]["id"]
    await _change(
        pg_client, ctx, {"kind": "set_price", "rate_plan_id": plan_id, "amount": 900000}, 1, 1
    )

    await pg_client.patch(
        f"/api/rate-plans/{plan_id}",
        json={"prices": [{"room_type_id": ctx["room"]["id"], "amount": 600000}]},
    )

    assert _amounts(await _read(pg_client, ctx["today"], 0, 2)) == [
        "600000.00",
        "900000.00",
        "600000.00",
    ]


async def test_an_override_equal_to_a_new_base_price_stops_being_one(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client, amount=500000)
    plan_id = ctx["plan"]["id"]
    await _change(pg_client, ctx, {"kind": "set_price", "rate_plan_id": plan_id, "amount": 600000})
    await _change(
        pg_client, ctx, {"kind": "set_price", "rate_plan_id": plan_id, "amount": 900000}, 1, 1
    )

    await pg_client.patch(
        f"/api/rate-plans/{plan_id}",
        json={"prices": [{"room_type_id": ctx["room"]["id"], "amount": 600000}]},
    )

    calendar = await _read(pg_client, ctx["today"], 0, 2)
    assert [(d["prices"][0]["amount"], d["prices"][0]["is_override"]) for d in _days(calendar)] == [
        ("600000.00", False),
        ("900000.00", True),
        ("600000.00", False),
    ]
    rows = (
        await pg_session.execute(
            text("SELECT count(*) FROM ratedaily WHERE tenant_id = :t"),
            {"t": ctx["workspace"]["tenant"]["id"]},
        )
    ).scalar_one()
    assert rows == 1


async def test_weekday_filter_across_several_room_types(pg_client) -> None:
    ctx = await _setup(pg_client)
    suite = await make_room_type(pg_client, name="Suite")
    await _change(pg_client, ctx, {"kind": "set_min_stay", "nights": 2}, 0, 13)

    response = await _change(
        pg_client,
        ctx,
        {"kind": "close"},
        0,
        13,
        weekdays=[5, 6],
        room_type_ids=[ctx["room"]["id"], suite["id"]],
    )

    assert response.json() == {"dates": 4, "room_types": 2}
    calendar = await _read(pg_client, ctx["today"], 0, 13)
    for room in calendar["room_types"]:
        for day in room["days"]:
            weekend = dt.date.fromisoformat(day["date"]).weekday() in (5, 6)
            assert day["closed"] is weekend
            assert day["min_stay"] == (2 if room["name"] == "Deluxe" else None)


async def test_price_must_be_in_range_and_the_plan_must_sell_the_room(pg_client) -> None:
    ctx = await _setup(pg_client)
    other_room = await make_room_type(pg_client, name="Suite")
    plan_id = ctx["plan"]["id"]

    too_low = await _change(
        pg_client, ctx, {"kind": "set_price", "rate_plan_id": plan_id, "amount": 9999}
    )
    not_sold = await _change(
        pg_client,
        ctx,
        {"kind": "set_price", "rate_plan_id": plan_id, "amount": 700000},
        room_type_ids=[ctx["room"]["id"], other_room["id"]],
    )
    unknown_plan = await _change(
        pg_client, ctx, {"kind": "set_price", "rate_plan_id": MISSING, "amount": 700000}
    )

    assert (too_low.status_code, not_sold.status_code, unknown_plan.status_code) == (422, 422, 422)
    assert "Rp 10.000" in too_low.json()["detail"]
    assert "does not sell" in not_sold.json()["detail"]
    assert _amounts(await _read(pg_client, ctx["today"], 0, 0)) == ["500000.00"]  # all or nothing


# ---- closing dates and minimum stay -----------------------------------------------------


async def test_close_and_open(pg_client) -> None:
    ctx = await _setup(pg_client)

    closed = await _change(pg_client, ctx, {"kind": "close"}, 1, 3)
    await _change(pg_client, ctx, {"kind": "open"}, 2, 2)

    assert closed.status_code == 200
    calendar = await _read(pg_client, ctx["today"], 0, 4)
    assert [day["closed"] for day in _days(calendar)] == [False, True, False, True, False]
    assert [day["available"] for day in _days(calendar)] == [3, 3, 3, 3, 3]


async def test_minimum_stay_set_and_clear(pg_client) -> None:
    ctx = await _setup(pg_client)

    await _change(pg_client, ctx, {"kind": "set_min_stay", "nights": 3}, 0, 2)
    await _change(pg_client, ctx, {"kind": "clear_min_stay"}, 1, 1)
    one_night = await _change(pg_client, ctx, {"kind": "set_min_stay", "nights": 1}, 2, 2)

    assert one_night.status_code == 200  # one night is the same as no rule
    calendar = await _read(pg_client, ctx["today"], 0, 2)
    assert [day["min_stay"] for day in _days(calendar)] == [3, None, None]


async def test_closing_keeps_the_minimum_stay_and_empty_rows_are_removed(
    pg_client, pg_session
) -> None:
    ctx = await _setup(pg_client)
    await _change(pg_client, ctx, {"kind": "set_min_stay", "nights": 2}, 0, 1)
    await _change(pg_client, ctx, {"kind": "close"}, 0, 2)

    await _change(pg_client, ctx, {"kind": "open"}, 0, 2)
    await _change(pg_client, ctx, {"kind": "clear_min_stay"}, 0, 0)

    calendar = await _read(pg_client, ctx["today"], 0, 2)
    assert [(day["closed"], day["min_stay"]) for day in _days(calendar)] == [
        (False, None),
        (False, 2),
        (False, None),
    ]
    rows = (
        await pg_session.execute(
            text("SELECT count(*) FROM restriction WHERE tenant_id = :t"),
            {"t": ctx["workspace"]["tenant"]["id"]},
        )
    ).scalar_one()
    assert rows == 1


async def test_a_change_applies_to_every_chosen_room_type(pg_client) -> None:
    ctx = await _setup(pg_client)
    suite = await make_room_type(pg_client, name="Suite")
    villa = await make_room_type(pg_client, name="Villa")

    response = await _change(
        pg_client, ctx, {"kind": "close"}, 0, 1, room_type_ids=[ctx["room"]["id"], suite["id"]]
    )

    assert response.json() == {"dates": 2, "room_types": 2}
    calendar = await _read(pg_client, ctx["today"], 0, 0)
    closed = {room["name"]: room["days"][0]["closed"] for room in calendar["room_types"]}
    assert closed == {"Deluxe": True, "Suite": True, "Villa": False}
    assert villa["id"] in [room["id"] for room in calendar["room_types"]]


# ---- what cannot be changed -------------------------------------------------------------


async def test_the_past_and_beyond_the_horizon_cannot_be_changed(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await set_business_settings(
        pg_session, ctx["workspace"]["property"]["id"], calendar_horizon_days=30
    )

    past = await _change(pg_client, ctx, {"kind": "close"}, -1, 0)
    last_day = await _change(pg_client, ctx, {"kind": "close"}, 29, 29)
    beyond = await _change(pg_client, ctx, {"kind": "close"}, 29, 30)
    reversed_range = await _change(pg_client, ctx, {"kind": "close"}, 3, 2)

    assert (past.status_code, last_day.status_code) == (422, 200)
    assert (beyond.status_code, reversed_range.status_code) == (422, 422)
    assert "Past dates" in past.json()["detail"]
    assert _day(ctx["today"], 29) in beyond.json()["detail"]


async def test_a_change_may_not_cover_more_days_than_the_setting(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await set_business_settings(
        pg_session, ctx["workspace"]["property"]["id"], calendar_max_change_days=7
    )

    assert (await _change(pg_client, ctx, {"kind": "close"}, 0, 6)).status_code == 200
    too_long = await _change(pg_client, ctx, {"kind": "close"}, 0, 7)

    assert too_long.status_code == 422
    assert "at most 7 days" in too_long.json()["detail"]


async def test_one_change_cannot_touch_an_unbounded_number_of_cells(pg_client, monkeypatch) -> None:
    ctx = await _setup(pg_client)
    monkeypatch.setattr("app.services.calendar.MAX_CELLS_PER_CHANGE", 5)

    fits = await _change(pg_client, ctx, {"kind": "close"}, 0, 4)
    too_large = await _change(pg_client, ctx, {"kind": "close"}, 0, 5)

    assert (fits.status_code, too_large.status_code) == (200, 422)
    assert "Split it" in too_large.json()["detail"]


async def test_weekdays_that_match_no_date_change_nothing(pg_client) -> None:
    ctx = await _setup(pg_client)
    not_today = [(ctx["today"].weekday() + 3) % 7]

    response = await _change(pg_client, ctx, {"kind": "close"}, 0, 0, weekdays=not_today)

    assert response.status_code == 422
    assert "No dates" in response.json()["detail"]


@pytest.mark.parametrize(
    "broken",
    [
        {"change": {"kind": "explode"}},
        {"change": {"kind": "set_price", "amount": 700000}},
        {"change": {"kind": "set_min_stay", "nights": 0}},
        {"change": {"kind": "set_min_stay", "nights": 400}},
        {"change": {"kind": "close", "extra": 1}},
        {"room_type_ids": []},
        {"room_type_ids": "TWICE"},
        {"weekdays": []},
        {"weekdays": [7]},
        {"weekdays": [1, 1]},
        {"unknown": True},
    ],
)
async def test_validation(pg_client, broken) -> None:
    ctx = await _setup(pg_client)
    if broken.get("room_type_ids") == "TWICE":
        broken = {"room_type_ids": [ctx["room"]["id"], ctx["room"]["id"]]}

    response = await _change(pg_client, ctx, broken.pop("change", {"kind": "close"}), **broken)

    assert response.status_code == 422


async def test_room_type_must_be_in_use(pg_client) -> None:
    ctx = await _setup(pg_client)
    off = await make_room_type(pg_client, name="Lama")
    await pg_client.patch(f"/api/room-types/{off['id']}", json={"is_active": False})

    statuses = [
        (await _change(pg_client, ctx, {"kind": "close"}, room_type_ids=[room_id])).status_code
        for room_id in (off["id"], MISSING)
    ]

    assert statuses == [422, 422]


# ---- size and concurrency ---------------------------------------------------------------


async def test_a_full_year_change_is_quick_and_reads_back(pg_client) -> None:
    ctx = await _setup(pg_client)
    rooms = [ctx["room"]["id"]] + [
        (await make_room_type(pg_client, name=f"Tipe {n}"))["id"] for n in range(4)
    ]

    started = time.monotonic()
    response = await _change(pg_client, ctx, {"kind": "close"}, 0, 364, room_type_ids=rooms)
    elapsed = time.monotonic() - started

    assert response.status_code == 200, response.text
    assert response.json() == {"dates": 365, "room_types": 5}
    assert elapsed < 5
    calendar = await _read(pg_client, ctx["today"], 300, 361)
    assert all(day["closed"] for room in calendar["room_types"] for day in room["days"])


async def test_simultaneous_changes_leave_one_consistent_result(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    plan_id = ctx["plan"]["id"]
    amounts = [600000, 700000, 800000, 900000]

    responses = await asyncio.gather(
        *(
            _change(
                pg_client, ctx, {"kind": "set_price", "rate_plan_id": plan_id, "amount": a}, 0, 9
            )
            for a in amounts
        ),
        _change(pg_client, ctx, {"kind": "close"}, 0, 9),
        _change(pg_client, ctx, {"kind": "set_min_stay", "nights": 2}, 0, 9),
    )

    assert [r.status_code for r in responses] == [200] * 6
    calendar = await _read(pg_client, ctx["today"], 0, 9)
    assert len(set(_amounts(calendar))) == 1  # every date ended on the same price
    assert _amounts(calendar)[0] in {f"{a}.00" for a in amounts}
    assert all(day["closed"] and day["min_stay"] == 2 for day in _days(calendar))
    counts = (
        await pg_session.execute(
            text(
                "SELECT (SELECT count(*) FROM ratedaily WHERE tenant_id = :t), "
                "(SELECT count(*) FROM restriction WHERE tenant_id = :t)"
            ),
            {"t": ctx["workspace"]["tenant"]["id"]},
        )
    ).one()
    assert tuple(counts) == (10, 10)
