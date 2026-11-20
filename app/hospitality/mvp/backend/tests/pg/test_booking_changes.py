"""Changing and cancelling a booking: availability moves with it."""

import asyncio
import datetime as dt

import pytest

from app.services.calendar_dates import property_today
from tests.pg.conftest import (
    make_booking,
    make_rate_plan,
    make_room_type,
    sold_matches_bookings,
    start_workspace,
)

pytestmark = pytest.mark.integration

BOOKINGS = "/api/bookings"


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


async def _patch(client, booking: dict, **changes):
    return await client.patch(f"{BOOKINGS}/{booking['id']}", json=changes)


async def _available(client, ctx: dict, first: int, last: int, room_index: int = 0) -> list[int]:
    response = await client.get(
        "/api/calendar", params={"from": _day(ctx, first), "to": _day(ctx, last)}
    )
    return [day["available"] for day in response.json()["room_types"][room_index]["days"]]


async def _consistent(session, ctx: dict) -> bool:
    return await sold_matches_bookings(session, ctx["workspace"]["tenant"]["id"])


async def test_extend_shorten_and_move(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client, units=1, amount=500000)
    booking = await _book(pg_client, ctx, 2, 4)

    extended = (await _patch(pg_client, booking, departure=_day(ctx, 6))).json()
    after_extend = await _available(pg_client, ctx, 1, 6)
    shortened = (await _patch(pg_client, booking, arrival=_day(ctx, 4))).json()
    after_shorten = await _available(pg_client, ctx, 1, 6)
    moved = (
        await _patch(pg_client, booking, arrival=_day(ctx, 10), departure=_day(ctx, 11))
    ).json()

    assert (extended["nights"], extended["total_amount"]) == (4, "2000000.00")
    assert after_extend == [1, 0, 0, 0, 0, 1]
    assert (shortened["nights"], shortened["total_amount"]) == (2, "1000000.00")
    assert after_shorten == [1, 1, 1, 0, 0, 1]
    assert (moved["arrival"], moved["nights"], moved["balance_due"]) == (
        _day(ctx, 10),
        1,
        "500000.00",
    )
    assert await _available(pg_client, ctx, 4, 10) == [1, 1, 1, 1, 1, 1, 0]
    assert moved["number"] == booking["number"]
    assert await _consistent(pg_session, ctx)


async def test_change_room_type_units_and_plan(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client, units=3, amount=500000)
    suite = await make_room_type(pg_client, name="Suite", units=1, max_guests=4)
    promo = await make_rate_plan(pg_client, [ctx["room"], suite], name="Promo", amount=900000)
    booking = await _book(pg_client, ctx, 1, 3)

    more_units = (await _patch(pg_client, booking, units=2, adults=4)).json()
    other_room = (
        await _patch(
            pg_client, booking, room_type_id=suite["id"], rate_plan_id=promo["id"], units=1
        )
    ).json()

    assert (more_units["units"], more_units["total_amount"]) == (2, "2000000.00")
    assert (other_room["room_type"]["name"], other_room["rate_plan"]["name"]) == ("Suite", "Promo")
    assert other_room["total_amount"] == "1800000.00"
    assert await _available(pg_client, ctx, 1, 2, room_index=0) == [3, 3]
    assert await _available(pg_client, ctx, 1, 2, room_index=1) == [0, 0]
    assert await _consistent(pg_session, ctx)


async def test_a_total_set_by_hand_survives_a_change_of_dates(pg_client) -> None:
    ctx = await _setup(pg_client, amount=500000)
    booking = await _book(pg_client, ctx, 1, 3)

    priced = (await _patch(pg_client, booking, total_amount=700000)).json()
    moved = (await _patch(pg_client, booking, departure=_day(ctx, 4))).json()

    assert (priced["total_amount"], priced["price_edited"]) == ("700000.00", True)
    assert [n["amount"] for n in priced["nightly"]] == ["350000.00", "350000.00"]
    assert (moved["total_amount"], moved["nights"]) == ("700000.00", 3)
    assert sum(float(n["amount"]) for n in moved["nightly"]) == 700000


async def test_details_change_without_touching_availability(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _book(pg_client, ctx, 1, 3, notes="Awal")

    changed = (
        await _patch(
            pg_client,
            booking,
            guest_name="Budi S.",
            source="instagram",
            notes="Minta kasur tambahan",
            adults=1,
            children=1,
        )
    ).json()
    cleared = (await _patch(pg_client, booking, notes="")).json()

    assert changed["guest"]["name"] == "Budi S."
    assert changed["guest"]["id"] == booking["guest"]["id"]  # its own record, renamed
    assert changed["source"]["code"] == "instagram"
    assert (changed["adults"], changed["children"]) == (1, 1)
    assert (changed["notes"], cleared["notes"]) == ("Minta kasur tambahan", None)
    assert changed["nightly"] == booking["nightly"]
    assert await _available(pg_client, ctx, 1, 2) == [1, 1]
    assert await _consistent(pg_session, ctx)


async def test_giving_a_number_links_the_booking_to_that_guest(pg_client) -> None:
    ctx = await _setup(pg_client)
    known = await _book(pg_client, ctx, 1, 2, guest_name="Ketut", guest_phone="081200000009")
    booking = await _book(pg_client, ctx, 3, 4, guest_name="Tanpa Nomor")

    linked = (await _patch(pg_client, booking, guest_phone="+6281200000009")).json()

    assert linked["guest"]["id"] == known["guest"]["id"]
    assert linked["guest"]["name"] == "Ketut"


async def test_a_change_that_runs_short_is_refused_and_changes_nothing(
    pg_client, pg_session
) -> None:
    ctx = await _setup(pg_client, units=1)
    await _book(pg_client, ctx, 4, 6, guest_name="Tetangga")
    booking = await _book(pg_client, ctx, 1, 3)

    refused = await _patch(pg_client, booking, departure=_day(ctx, 5))
    insisted = await _patch(pg_client, booking, departure=_day(ctx, 5), allow_overbooking=True)

    assert refused.status_code == 409
    assert refused.json()["detail"]["short_dates"] == [_day(ctx, 4)]
    assert (insisted.status_code, insisted.json()["overbooking_risk"]) == (200, True)
    assert await _consistent(pg_session, ctx)


async def test_a_refused_change_keeps_the_booking_as_it_was(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client, units=1)
    await _book(pg_client, ctx, 4, 6, guest_name="Tetangga")
    booking = await _book(pg_client, ctx, 1, 3)

    await _patch(pg_client, booking, departure=_day(ctx, 5), notes="tidak boleh tersimpan")

    after = (await pg_client.get(f"{BOOKINGS}/{booking['id']}")).json()
    assert after == booking
    assert await _available(pg_client, ctx, 1, 5) == [0, 0, 1, 0, 0]
    assert await _consistent(pg_session, ctx)


async def test_changes_obey_the_same_rules_as_new_bookings(pg_client) -> None:
    ctx = await _setup(pg_client)
    booking = await _book(pg_client, ctx, 1, 3)

    statuses = [
        (await _patch(pg_client, booking, **change)).status_code
        for change in (
            {"departure": _day(ctx, 1)},
            {"adults": 3},
            {"units": 0},
            {"guest_phone": "123"},
            {"number": "X"},
            {"total_amount": 0},
        )
    ]

    assert statuses == [422] * 6


async def test_an_old_arrival_does_not_block_other_changes(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _book(pg_client, ctx, -20, -18)
    await pg_session.execute(
        __import__("sqlalchemy").text(
            "UPDATE property SET settings = settings || "
            '\'{"business": {"booking_backdate_days": 5}}\'::jsonb WHERE id = :p'
        ),
        {"p": ctx["workspace"]["property"]["id"]},
    )
    await pg_session.commit()

    notes = await _patch(pg_client, booking, notes="Catatan belakangan")
    price = await _patch(pg_client, booking, total_amount=900000)
    earlier = await _patch(pg_client, booking, arrival=_day(ctx, -21))

    assert (notes.status_code, price.status_code, earlier.status_code) == (200, 200, 422)


async def test_cancel_returns_the_units_and_keeps_the_record(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client, units=1)
    booking = await _book(pg_client, ctx, 1, 3)

    response = await pg_client.post(
        f"{BOOKINGS}/{booking['id']}/cancel", json={"reason": "Tamu ganti tanggal"}
    )

    cancelled = response.json()
    assert response.status_code == 200
    assert (cancelled["status"], cancelled["cancel_note"]) == ("cancelled", "Tamu ganti tanggal")
    assert cancelled["cancelled_at"] is not None
    assert cancelled["nightly"] == booking["nightly"]
    assert await _available(pg_client, ctx, 1, 2) == [1, 1]
    assert await _consistent(pg_session, ctx)


async def test_a_cancelled_booking_cannot_be_cancelled_or_changed(pg_client) -> None:
    ctx = await _setup(pg_client)
    booking = await _book(pg_client, ctx, 1, 3)
    await pg_client.post(f"{BOOKINGS}/{booking['id']}/cancel", json={})

    again = await pg_client.post(f"{BOOKINGS}/{booking['id']}/cancel", json={})
    change = await _patch(pg_client, booking, notes="x")

    assert (again.status_code, change.status_code) == (409, 409)
    assert "cancelled" in change.json()["detail"]


async def test_simultaneous_cancel_and_change_stay_consistent(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client, units=1)
    booking = await _book(pg_client, ctx, 1, 3)

    responses = await asyncio.gather(
        pg_client.post(f"{BOOKINGS}/{booking['id']}/cancel", json={}),
        _patch(pg_client, booking, departure=_day(ctx, 5)),
        pg_client.post(f"{BOOKINGS}/{booking['id']}/cancel", json={}),
    )

    assert sorted(r.status_code for r in responses) in ([200, 200, 409], [200, 409, 409])
    final = (await pg_client.get(f"{BOOKINGS}/{booking['id']}")).json()
    assert final["status"] == "cancelled"
    assert await _available(pg_client, ctx, 1, 5) == [1, 1, 1, 1, 1]
    assert await _consistent(pg_session, ctx)


async def test_empty_change_changes_nothing(pg_client) -> None:
    ctx = await _setup(pg_client)
    booking = await _book(pg_client, ctx, 1, 3)

    response = await _patch(pg_client, booking)

    assert response.status_code == 200
    assert response.json() == booking


async def test_fields_can_be_cleared(pg_client) -> None:
    ctx = await _setup(pg_client, amount=500000)
    booking = await _book(
        pg_client, ctx, 1, 3, guest_phone="081200000021", notes="Awal", total_amount=700000
    )

    cleared = (
        await _patch(pg_client, booking, notes="", guest_phone=None, reset_price=True)
    ).json()

    assert cleared["notes"] is None
    assert cleared["guest"]["phone"] is None
    assert cleared["guest"]["id"] != booking["guest"]["id"]  # the numbered guest is left alone
    assert (cleared["total_amount"], cleared["price_edited"]) == ("1000000.00", False)
    assert [n["amount"] for n in cleared["nightly"]] == ["500000.00", "500000.00"]


async def test_a_total_and_a_price_reset_cannot_be_sent_together(pg_client) -> None:
    ctx = await _setup(pg_client)
    booking = await _book(pg_client, ctx, 1, 3)

    response = await _patch(pg_client, booking, total_amount=700000, reset_price=True)

    assert response.status_code == 422


async def test_a_hand_set_total_is_dropped_when_what_is_sold_changes(pg_client) -> None:
    ctx = await _setup(pg_client, units=3, amount=500000)
    booking = await _book(pg_client, ctx, 1, 3, total_amount=700000)

    more_units = (await _patch(pg_client, booking, units=2, adults=4)).json()

    assert (more_units["total_amount"], more_units["price_edited"]) == ("2000000.00", False)


async def test_the_name_of_a_guest_with_a_number_can_be_corrected(pg_client) -> None:
    ctx = await _setup(pg_client)
    booking = await _book(pg_client, ctx, 1, 3, guest_name="Kutut", guest_phone="081200000022")

    renamed = (
        await _patch(pg_client, booking, guest_name="Ketut", guest_phone="081200000022")
    ).json()
    name_only = (await _patch(pg_client, booking, guest_name="I Ketut")).json()

    assert (renamed["guest"]["name"], renamed["guest"]["id"]) == ("Ketut", booking["guest"]["id"])
    assert (name_only["guest"]["name"], name_only["guest"]["phone"]) == (
        "I Ketut",
        "+6281200000022",
    )


async def test_an_overbooked_booking_can_be_corrected_without_new_consent(
    pg_client, pg_session
) -> None:
    ctx = await _setup(pg_client, units=1, amount=500000)
    await _book(pg_client, ctx, 1, 4, guest_name="Pertama")
    over = (
        await pg_client.post(
            BOOKINGS,
            json={
                "arrival": _day(ctx, 2),
                "departure": _day(ctx, 4),
                "room_type_id": ctx["room"]["id"],
                "rate_plan_id": ctx["plan"]["id"],
                "guest_name": "Kedua",
                "units": 1,
                "allow_overbooking": True,
            },
        )
    ).json()

    stay = {
        "room_type_id": ctx["room"]["id"],
        "rate_plan_id": ctx["plan"]["id"],
        "exclude_booking_id": over["id"],
    }
    same = await pg_client.post(
        f"{BOOKINGS}/quote", json={**stay, "arrival": _day(ctx, 2), "departure": _day(ctx, 4)}
    )
    earlier = await pg_client.post(
        f"{BOOKINGS}/quote", json={**stay, "arrival": _day(ctx, 1), "departure": _day(ctx, 4)}
    )
    assert same.json()["short_dates"] == []  # the form agrees with the server: no consent
    assert earlier.json()["short_dates"] == [_day(ctx, 1)]

    price = await _patch(pg_client, over, total_amount=900000)
    shorter = await _patch(pg_client, over, departure=_day(ctx, 3))
    notes = await _patch(pg_client, over, notes="tetap berisiko")
    worse = await _patch(pg_client, over, arrival=_day(ctx, 1))

    assert (price.status_code, shorter.status_code, notes.status_code) == (200, 200, 200)
    assert shorter.json()["overbooking_risk"] is True
    assert worse.status_code == 409  # a night that was fine would become oversold
    assert worse.json()["detail"]["short_dates"] == [_day(ctx, 1)]
    assert await _consistent(pg_session, ctx)


async def test_adding_units_to_an_overbooked_booking_still_needs_consent(pg_client) -> None:
    ctx = await _setup(pg_client, units=2, amount=500000)
    await _book(pg_client, ctx, 1, 3, units=2, adults=4, guest_name="Pertama")
    over = (
        await pg_client.post(
            BOOKINGS,
            json={
                "arrival": _day(ctx, 1),
                "departure": _day(ctx, 3),
                "room_type_id": ctx["room"]["id"],
                "rate_plan_id": ctx["plan"]["id"],
                "guest_name": "Kedua",
                "allow_overbooking": True,
            },
        )
    ).json()

    more = await _patch(pg_client, over, units=2, adults=4)

    assert more.status_code == 409
