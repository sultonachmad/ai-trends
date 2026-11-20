"""Bookings entered by staff: creating, reading, listing, quoting — and availability."""

import asyncio
import datetime as dt

import pytest

from app.services.calendar_dates import property_today
from tests.pg.conftest import (
    guest_says,
    make_booking,
    make_rate_plan,
    make_room_type,
    set_business_settings,
    sold_matches_bookings,
    start_workspace,
)

pytestmark = pytest.mark.integration

BOOKINGS = "/api/bookings"
MISSING = "00000000-0000-0000-0000-000000000000"


async def _setup(client, *, units: int = 2, amount: int = 500000) -> dict:
    workspace = await start_workspace(client)
    room = await make_room_type(client, units=units, max_guests=2)
    plan = await make_rate_plan(client, [room], amount=amount)
    today = property_today(workspace["property"]["timezone"])
    return {"workspace": workspace, "room": room, "plan": plan, "today": today}


def _day(ctx: dict, offset: int) -> str:
    return (ctx["today"] + dt.timedelta(days=offset)).isoformat()


async def _book(client, ctx: dict, first: int, last: int, **overrides) -> dict:
    return await make_booking(
        client, ctx["room"], ctx["plan"], _day(ctx, first), _day(ctx, last), **overrides
    )


async def _try(client, ctx: dict, first: int, last: int, **overrides):
    return await client.post(
        BOOKINGS,
        json={
            "arrival": _day(ctx, first),
            "departure": _day(ctx, last),
            "room_type_id": ctx["room"]["id"],
            "rate_plan_id": ctx["plan"]["id"],
            "guest_name": "Budi Santoso",
            **overrides,
        },
    )


async def _available(client, ctx: dict, first: int, last: int) -> list[int]:
    response = await client.get(
        "/api/calendar", params={"from": _day(ctx, first), "to": _day(ctx, last)}
    )
    return [day["available"] for day in response.json()["room_types"][0]["days"]]


async def _list(client, tab: str, **params) -> dict:
    response = await client.get(BOOKINGS, params={"tab": tab, **params})
    assert response.status_code == 200, response.text
    return response.json()


# ---- creating ---------------------------------------------------------------------------


async def test_requires_sign_in(pg_client) -> None:
    assert (await pg_client.get(BOOKINGS)).status_code == 401


async def test_create_a_booking(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client, amount=500000)

    booking = await _book(
        pg_client, ctx, 3, 6, guest_phone="0812-3456-7890", source="walk_in", notes="Lantai atas"
    )

    assert booking["number"].startswith("VS-") and len(booking["number"]) == 9
    assert (booking["status"], booking["nights"], booking["units"]) == ("confirmed", 3, 1)
    assert (booking["arrival"], booking["departure"]) == (_day(ctx, 3), _day(ctx, 6))
    assert booking["room_type"] == {"id": ctx["room"]["id"], "name": "Deluxe"}
    assert booking["rate_plan"]["name"] == "Harga Normal"
    assert booking["guest"]["name"] == "Budi Santoso"
    assert booking["guest"]["phone"] == "+6281234567890"
    assert booking["source"] == {"code": "walk_in", "name": "Walk-in", "is_direct": True}
    assert (booking["total_amount"], booking["paid_amount"], booking["balance_due"]) == (
        "1500000.00",
        "0.00",
        "1500000.00",
    )
    assert (booking["payment_state"], booking["price_edited"]) == ("unpaid", False)
    assert booking["overbooking_risk"] is False
    assert booking["notes"] == "Lantai atas"
    assert booking["nightly"] == [{"date": _day(ctx, n), "amount": "500000.00"} for n in (3, 4, 5)]
    assert booking["terms"] == {"non_refundable": False, "free_cancellation_days": 7}
    assert booking["payments"] == []
    assert (await pg_client.get(f"{BOOKINGS}/{booking['id']}")).json() == booking
    assert await sold_matches_bookings(pg_session, ctx["workspace"]["tenant"]["id"])


async def test_a_booking_takes_units_off_the_calendar_for_its_nights_only(pg_client) -> None:
    ctx = await _setup(pg_client, units=2)

    await _book(pg_client, ctx, 1, 3)
    await _book(pg_client, ctx, 2, 4, units=1)

    assert await _available(pg_client, ctx, 0, 4) == [2, 1, 0, 1, 2]


async def test_price_follows_the_calendar_and_several_units(pg_client) -> None:
    ctx = await _setup(pg_client, units=3, amount=500000)
    await pg_client.post(
        "/api/calendar/changes",
        json={
            "start": _day(ctx, 2),
            "end": _day(ctx, 2),
            "room_type_ids": [ctx["room"]["id"]],
            "change": {"kind": "set_price", "rate_plan_id": ctx["plan"]["id"], "amount": 800000},
        },
    )

    booking = await _book(pg_client, ctx, 1, 3, units=2, adults=4)

    assert booking["total_amount"] == "2600000.00"
    assert booking["nightly"] == [
        {"date": _day(ctx, 1), "amount": "1000000.00"},
        {"date": _day(ctx, 2), "amount": "1600000.00"},
    ]


async def test_staff_can_set_the_total_by_hand(pg_client) -> None:
    ctx = await _setup(pg_client, amount=500000)

    booking = await _book(pg_client, ctx, 1, 4, total_amount=1000000)

    assert (booking["total_amount"], booking["price_edited"]) == ("1000000.00", True)
    assert [night["amount"] for night in booking["nightly"]] == [
        "333334.00",
        "333333.00",
        "333333.00",
    ]


async def test_a_number_known_to_the_inbox_links_to_that_guest(pg_client) -> None:
    ctx = await _setup(pg_client)
    said = await guest_says(pg_client, "Halo", phone="+6281200000001", name="Wayan Inbox")

    by_phone = await _book(pg_client, ctx, 1, 2, guest_name="Pak Wayan", guest_phone="081200000001")
    from_chat = await _book(
        pg_client, ctx, 3, 4, guest_name="ignored", conversation_id=said["conversation_id"]
    )
    no_phone = await _book(pg_client, ctx, 5, 6, guest_name="Tamu Lewat")

    assert by_phone["guest"]["name"] == "Wayan Inbox"  # the inbox's name is kept
    assert from_chat["guest"]["id"] == by_phone["guest"]["id"]
    assert (no_phone["guest"]["name"], no_phone["guest"]["phone"]) == ("Tamu Lewat", None)
    assert no_phone["guest"]["id"] != by_phone["guest"]["id"]


@pytest.mark.parametrize("source", ["whatsapp", "walk_in", "phone", "instagram", "other"])
async def test_every_source_staff_can_pick(pg_client, source) -> None:
    ctx = await _setup(pg_client)

    first = await _book(pg_client, ctx, 1, 2, source=source)
    second = await _book(pg_client, ctx, 3, 4, source=source)

    assert first["source"]["code"] == second["source"]["code"] == source
    assert first["source"]["is_direct"] is True


# ---- what cannot be booked --------------------------------------------------------------


async def test_dates_must_make_sense(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await set_business_settings(
        pg_session,
        ctx["workspace"]["property"]["id"],
        booking_backdate_days=2,
        booking_max_nights=5,
        calendar_horizon_days=30,
    )

    statuses = {
        "same day": (await _try(pg_client, ctx, 1, 1)).status_code,
        "reversed": (await _try(pg_client, ctx, 3, 1)).status_code,
        "back-entry allowed": (await _try(pg_client, ctx, -2, -1)).status_code,
        "too far back": (await _try(pg_client, ctx, -3, -1)).status_code,
        "longest stay": (await _try(pg_client, ctx, 5, 10)).status_code,
        "too long": (await _try(pg_client, ctx, 11, 17)).status_code,
        "last arrival": (await _try(pg_client, ctx, 29, 30)).status_code,
        "beyond the calendar": (await _try(pg_client, ctx, 30, 31)).status_code,
    }

    assert statuses == {
        "same day": 422,
        "reversed": 422,
        "back-entry allowed": 201,
        "too far back": 422,
        "longest stay": 201,
        "too long": 422,
        "last arrival": 201,
        "beyond the calendar": 422,
    }


async def test_guests_must_fit(pg_client) -> None:
    ctx = await _setup(pg_client, units=3)  # 2 guests per unit

    too_many = await _try(pg_client, ctx, 1, 2, adults=2, children=1)
    with_two_units = await _try(pg_client, ctx, 1, 2, adults=2, children=1, units=2)

    assert too_many.status_code == 422
    assert "At most 2 guests" in too_many.json()["detail"]
    assert with_two_units.status_code == 201


async def test_room_and_plan_must_be_ours_and_in_use(pg_client, other_client) -> None:
    ctx = await _setup(pg_client)
    theirs = await _setup(other_client)
    unsold = await make_room_type(pg_client, name="Belum Dijual")
    off = await make_rate_plan(pg_client, [ctx["room"]], name="Lama")
    await pg_client.patch(f"/api/rate-plans/{off['id']}", json={"is_active": False})

    statuses = [
        (await _try(pg_client, ctx, 1, 2, **change)).status_code
        for change in (
            {"room_type_id": theirs["room"]["id"]},
            {"rate_plan_id": theirs["plan"]["id"]},
            {"room_type_id": MISSING},
            {"room_type_id": unsold["id"]},
            {"rate_plan_id": off["id"]},
            {"conversation_id": MISSING},
        )
    ]

    assert statuses == [422, 422, 422, 422, 422, 404]


@pytest.mark.parametrize(
    "change",
    [
        {"guest_name": ""},
        {"guest_name": "Budi‮iduB"},
        {"guest_phone": "12345"},
        {"units": 0},
        {"adults": 0},
        {"children": -1},
        {"source": "traveloka"},
        {"total_amount": 0},
        {"total_amount": "1500000.50"},
        {"notes": "x" * 1001},
        {"notes": "bel\x07"},
        {"status": "cancelled"},
    ],
)
async def test_validation(pg_client, change) -> None:
    ctx = await _setup(pg_client)

    assert (await _try(pg_client, ctx, 1, 2, **change)).status_code == 422


async def test_units_per_booking_limit_is_a_setting(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client, units=5)
    await set_business_settings(pg_session, ctx["workspace"]["property"]["id"], booking_max_units=2)

    response = await _try(pg_client, ctx, 1, 2, units=3, adults=2)

    assert response.status_code == 422
    assert "at most 2 units" in response.json()["detail"]


# ---- when nothing is left ---------------------------------------------------------------


async def test_short_availability_is_refused_unless_staff_insist(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client, units=1)
    first = await _book(pg_client, ctx, 1, 4)

    refused = await _try(pg_client, ctx, 3, 6)
    insisted = await _try(pg_client, ctx, 3, 6, allow_overbooking=True)

    assert refused.status_code == 409
    assert refused.json()["detail"]["short_dates"] == [_day(ctx, 3)]
    assert insisted.status_code == 201
    assert insisted.json()["overbooking_risk"] is True
    assert (await pg_client.get(f"{BOOKINGS}/{first['id']}")).json()["overbooking_risk"] is True
    calendar = (
        await pg_client.get("/api/calendar", params={"from": _day(ctx, 2), "to": _day(ctx, 4)})
    ).json()
    days = calendar["room_types"][0]["days"]
    assert [(d["available"], d["oversold"]) for d in days] == [(0, False), (0, True), (0, False)]
    assert await sold_matches_bookings(pg_session, ctx["workspace"]["tenant"]["id"])


async def test_a_refused_booking_leaves_nothing_behind(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client, units=1)
    await _book(pg_client, ctx, 1, 3)

    refused = await _try(pg_client, ctx, 2, 5, guest_name="Tidak Jadi")

    assert refused.status_code == 409
    assert await _available(pg_client, ctx, 1, 4) == [0, 0, 1, 1]
    assert [b["guest"]["name"] for b in (await _list(pg_client, "upcoming"))["items"]] == [
        "Budi Santoso"
    ]
    assert await sold_matches_bookings(pg_session, ctx["workspace"]["tenant"]["id"])


async def test_the_risk_flag_clears_when_the_other_booking_is_cancelled(pg_client) -> None:
    ctx = await _setup(pg_client, units=1)
    first = await _book(pg_client, ctx, 1, 3)
    second = (await _try(pg_client, ctx, 2, 4, allow_overbooking=True)).json()

    await pg_client.post(f"{BOOKINGS}/{first['id']}/cancel", json={})

    assert (await pg_client.get(f"{BOOKINGS}/{second['id']}")).json()["overbooking_risk"] is False


async def test_simultaneous_bookings_cannot_both_take_the_last_unit(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client, units=1)

    responses = await asyncio.gather(
        *(_try(pg_client, ctx, 1, 3, guest_name=f"Tamu {n}") for n in range(5))
    )

    assert sorted(r.status_code for r in responses) == [201, 409, 409, 409, 409]
    assert await _available(pg_client, ctx, 1, 2) == [0, 0]
    assert await sold_matches_bookings(pg_session, ctx["workspace"]["tenant"]["id"])


async def test_closed_dates_and_minimum_stay_do_not_block_staff(pg_client) -> None:
    ctx = await _setup(pg_client)
    for change in ({"kind": "close"}, {"kind": "set_min_stay", "nights": 5}):
        await pg_client.post(
            "/api/calendar/changes",
            json={
                "start": _day(ctx, 1),
                "end": _day(ctx, 3),
                "room_type_ids": [ctx["room"]["id"]],
                "change": change,
            },
        )

    assert (await _try(pg_client, ctx, 1, 3)).status_code == 201


async def test_lowering_the_unit_count_flags_the_bookings_it_strands(pg_client) -> None:
    ctx = await _setup(pg_client, units=2)
    one = await _book(pg_client, ctx, 1, 3)
    two = await _book(pg_client, ctx, 1, 3, guest_name="Tamu Kedua")

    await pg_client.patch(f"/api/room-types/{ctx['room']['id']}", json={"units": 1})

    risks = [
        (await pg_client.get(f"{BOOKINGS}/{b['id']}")).json()["overbooking_risk"]
        for b in (one, two)
    ]
    assert risks == [True, True]


# ---- quoting ----------------------------------------------------------------------------


async def test_quote_shows_price_availability_and_notices(pg_client) -> None:
    ctx = await _setup(pg_client, units=1, amount=500000)
    held = await _book(pg_client, ctx, 2, 3)
    for change in ({"kind": "close"}, {"kind": "set_min_stay", "nights": 4}):
        await pg_client.post(
            "/api/calendar/changes",
            json={
                "start": _day(ctx, 1),
                "end": _day(ctx, 1),
                "room_type_ids": [ctx["room"]["id"]],
                "change": change,
            },
        )
    stay = {
        "arrival": _day(ctx, 1),
        "departure": _day(ctx, 4),
        "room_type_id": ctx["room"]["id"],
        "rate_plan_id": ctx["plan"]["id"],
    }

    quote = (await pg_client.post(f"{BOOKINGS}/quote", json=stay)).json()
    own = (
        await pg_client.post(f"{BOOKINGS}/quote", json={**stay, "exclude_booking_id": held["id"]})
    ).json()

    assert quote["total_amount"] == "1500000.00"
    assert [n["available"] for n in quote["nights"]] == [1, 0, 1]
    assert quote["short_dates"] == [_day(ctx, 2)]
    assert quote["closed_dates"] == [_day(ctx, 1)]
    assert (quote["min_stay"], quote["max_guests"]) == (4, 2)
    assert own["short_dates"] == []  # changing a booking does not compete with itself
    assert await _available(pg_client, ctx, 1, 3) == [1, 0, 1]  # a quote saves nothing


async def test_quote_refuses_what_a_booking_would(pg_client) -> None:
    ctx = await _setup(pg_client)

    response = await pg_client.post(
        f"{BOOKINGS}/quote",
        json={
            "arrival": _day(ctx, 3),
            "departure": _day(ctx, 3),
            "room_type_id": ctx["room"]["id"],
            "rate_plan_id": ctx["plan"]["id"],
        },
    )

    assert response.status_code == 422
    assert "after arrival" in response.json()["detail"]


# ---- the list ---------------------------------------------------------------------------


async def test_tabs_split_by_today_at_the_property(pg_client) -> None:
    ctx = await _setup(pg_client, units=5)
    await _book(pg_client, ctx, -5, -2, guest_name="Sudah Pulang")
    await _book(pg_client, ctx, -1, 0, guest_name="Pulang Hari Ini")
    await _book(pg_client, ctx, -1, 2, guest_name="Sedang Menginap")
    await _book(pg_client, ctx, 0, 1, guest_name="Tiba Hari Ini")
    await _book(pg_client, ctx, 4, 6, guest_name="Minggu Depan")
    await _book(pg_client, ctx, 1, 2, guest_name="Besok")
    gone = await _book(pg_client, ctx, 2, 3, guest_name="Batal")
    await pg_client.post(f"{BOOKINGS}/{gone['id']}/cancel", json={"reason": "Ganti rencana"})

    names = {
        tab: [b["guest"]["name"] for b in (await _list(pg_client, tab))["items"]]
        for tab in ("upcoming", "staying", "past", "cancelled")
    }

    assert names == {
        "upcoming": ["Besok", "Minggu Depan"],
        "staying": ["Tiba Hari Ini", "Sedang Menginap"],
        "past": ["Pulang Hari Ini", "Sudah Pulang"],
        "cancelled": ["Batal"],
    }


async def test_search_by_guest_name_or_number(pg_client) -> None:
    ctx = await _setup(pg_client, units=5)
    made = await _book(pg_client, ctx, 1, 2, guest_name="Komang Ayu")
    await _book(pg_client, ctx, 1, 2, guest_name="Putu_100%")

    by_name = await _list(pg_client, "upcoming", q="mang a")
    by_number = await _list(pg_client, "upcoming", q=made["number"].lower())
    literal = await _list(pg_client, "upcoming", q="_100%")
    wildcard_only = await _list(pg_client, "upcoming", q="%")

    assert [b["id"] for b in by_name["items"]] == [made["id"]]
    assert [b["id"] for b in by_number["items"]] == [made["id"]]
    assert [b["guest"]["name"] for b in literal["items"]] == ["Putu_100%"]
    assert [b["guest"]["name"] for b in wildcard_only["items"]] == ["Putu_100%"]


@pytest.mark.parametrize("tab", ["upcoming", "past", "cancelled"])
async def test_paging_walks_every_booking_once(pg_client, tab) -> None:
    ctx = await _setup(pg_client, units=9)
    offsets = {"upcoming": (1, 2), "past": (-3, -2), "cancelled": (1, 2)}[tab]
    made = []
    for n in range(5):
        booking = await _book(pg_client, ctx, *offsets, guest_name=f"Tamu {n}")
        made.append(booking["id"])
        if tab == "cancelled":
            await pg_client.post(f"{BOOKINGS}/{booking['id']}/cancel", json={})

    seen, cursor = [], None
    for _ in range(4):
        page = await _list(pg_client, tab, limit=2, **({"cursor": cursor} if cursor else {}))
        seen.extend(b["id"] for b in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break

    assert sorted(seen) == sorted(made)
    assert len(seen) == 5


@pytest.mark.parametrize(
    "params",
    [
        {"tab": "someday"},
        {"cursor": "nonsense"},
        {"cursor": "2026-01-01|nope"},
        {"limit": 0},
        {"q": ""},
    ],
)
async def test_bad_list_requests_are_refused(pg_client, params) -> None:
    await _setup(pg_client)

    assert (await pg_client.get(BOOKINGS, params=params)).status_code == 422


async def test_unknown_booking_is_404(pg_client) -> None:
    await _setup(pg_client)

    assert (await pg_client.get(f"{BOOKINGS}/{MISSING}")).status_code == 404


@pytest.mark.parametrize(
    ("arrival", "departure"),
    [("0001-01-01", "9999-12-31"), ("2026-01-01", "2099-01-01"), ("9999-12-30", "9999-12-31")],
)
async def test_an_absurd_date_range_is_refused_at_once(pg_client, arrival, departure) -> None:
    ctx = await _setup(pg_client)
    stay = {
        "arrival": arrival,
        "departure": departure,
        "room_type_id": ctx["room"]["id"],
        "rate_plan_id": ctx["plan"]["id"],
    }

    quote = await pg_client.post(f"{BOOKINGS}/quote", json=stay)
    create = await pg_client.post(BOOKINGS, json={**stay, "guest_name": "X"})

    assert (quote.status_code, create.status_code) == (422, 422)


async def test_units_times_nights_has_a_ceiling(pg_client, pg_session, monkeypatch) -> None:
    ctx = await _setup(pg_client, units=5)
    monkeypatch.setattr("app.services.booking_stays.MAX_UNIT_NIGHTS", 6)

    fits = await _try(pg_client, ctx, 1, 4, units=2, adults=4)
    too_large = await _try(pg_client, ctx, 5, 9, units=2, adults=4)

    assert (fits.status_code, too_large.status_code) == (201, 422)
    assert "Split it" in too_large.json()["detail"]


@pytest.mark.parametrize("change", [{"total_amount": 10**12}, {"notes": "rtl‮over"}])
async def test_huge_totals_and_hidden_characters_in_notes_are_refused(pg_client, change) -> None:
    ctx = await _setup(pg_client)

    assert (await _try(pg_client, ctx, 1, 2, **change)).status_code == 422
