"""The front desk: arrivals, check-in, check-out, early departure, no-show and undo."""

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.services.calendar_dates import property_today
from tests.pg.conftest import (
    add_staff_member,
    make_booking,
    make_rate_plan,
    make_room_type,
    sold_matches_bookings,
    start_workspace,
)

pytestmark = pytest.mark.integration

DESK = "/api/front-desk"
BOOKINGS = "/api/bookings"
LEAVE = {"leave_unpaid_reason": "Bayar nanti"}  # these tests are not about money


async def _setup(client, units: int = 3) -> dict:
    workspace = await start_workspace(client)
    room = await make_room_type(client, units=units, max_guests=4)
    plan = await make_rate_plan(client, [room], amount=500000)
    today = property_today(workspace["property"]["timezone"])
    return {"workspace": workspace, "room": room, "plan": plan, "today": today}


def _on(ctx: dict, offset: int) -> str:
    return (ctx["today"] + dt.timedelta(days=offset)).isoformat()


async def _book(client, ctx, start: int, end: int, **overrides) -> dict:
    return await make_booking(
        client, ctx["room"], ctx["plan"], _on(ctx, start), _on(ctx, end), **overrides
    )


async def _rooms_given(session, client, ctx, booking: dict, first: int = 0) -> None:
    rows = await session.execute(
        text("SELECT id FROM reservationunit WHERE reservation_id = :b ORDER BY created_at, id"),
        {"b": booking["id"]},
    )
    for index, row in enumerate(rows.all()):
        unit = ctx["room"]["units"][first + index]["id"]
        answer = await client.put(f"{DESK}/lines/{row[0]}/room", json={"unit_id": unit})
        assert answer.status_code == 200, answer.text


async def _checked_in(session, client, ctx, start=0, end=3, **overrides) -> dict:
    booking = await _book(client, ctx, start, end, **overrides)
    await _rooms_given(session, client, ctx, booking)
    answer = await client.post(f"{DESK}/bookings/{booking['id']}/check-in", json={})
    assert answer.status_code == 200, answer.text
    return booking


async def _backdate(session, booking_id: str, days: int) -> None:
    await session.execute(
        text(
            "UPDATE reservation SET arrival_date = arrival_date - CAST(:d AS integer), "
            "departure_date = departure_date - CAST(:d AS integer) WHERE id = :b"
        ),
        {"d": days, "b": booking_id},
    )
    await session.execute(
        text(
            "UPDATE reservationunit SET arrival_date = arrival_date - CAST(:d AS integer), "
            "departure_date = departure_date - CAST(:d AS integer), "
            "start_at = start_at - make_interval(days => CAST(:d AS integer)), "
            "end_at = end_at - make_interval(days => CAST(:d AS integer)), "
            "blocked_until = blocked_until - make_interval(days => CAST(:d AS integer)) "
            "WHERE reservation_id = :b"
        ),
        {"d": days, "b": booking_id},
    )
    await session.commit()


async def _set_room(session, unit_id: str, **fields) -> None:
    assignments = ", ".join(f"{name} = :{name}" for name in fields)
    await session.execute(
        text(f"UPDATE unit SET {assignments} WHERE id = :u"),  # noqa: S608
        {"u": unit_id, **fields},
    )
    await session.commit()


async def _today(client) -> dict:
    response = await client.get(f"{DESK}/today")
    assert response.status_code == 200, response.text
    return response.json()


def _code(response) -> str:
    return response.json()["detail"]["code"]


# ---- check-in ----------------------------------------------------------------------------


async def test_check_in_needs_a_room(pg_client) -> None:
    ctx = await _setup(pg_client)
    booking = await _book(pg_client, ctx, 0, 2)

    response = await pg_client.post(f"{DESK}/bookings/{booking['id']}/check-in", json={})

    assert (response.status_code, _code(response)) == (409, "rooms_missing")


async def test_check_in_marks_booking_and_room(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _checked_in(pg_session, pg_client, ctx)

    today = await _today(pg_client)

    assert (await pg_client.get(f"{BOOKINGS}/{booking['id']}")).json()["status"] == "in_house"
    assert [entry["id"] for entry in today["in_house"]] == [booking["id"]]
    assert today["arrivals"] == []
    room = next(r for r in today["rooms"] if r["id"] == ctx["room"]["units"][0]["id"])
    assert (room["fo_status"], room["guest_name"]) == ("occupied", "Budi Santoso")
    logged = await pg_session.execute(
        text(
            "SELECT count(*) FROM tenantauditentry WHERE event_id = 'booking.checked_in' "
            "AND entity_id = :b"
        ),
        {"b": booking["id"]},
    )
    assert logged.scalar_one() == 1


@pytest.mark.parametrize(("start", "end"), [(1, 3)])
async def test_check_in_only_during_the_stay(pg_client, pg_session, start, end) -> None:
    ctx = await _setup(pg_client)
    booking = await _book(pg_client, ctx, start, end)
    await _rooms_given(pg_session, pg_client, ctx, booking)

    response = await pg_client.post(f"{DESK}/bookings/{booking['id']}/check-in", json={})

    assert (response.status_code, _code(response)) == (409, "outside_stay")


async def test_a_dirty_room_needs_confirmation(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _book(pg_client, ctx, 0, 2)
    await _rooms_given(pg_session, pg_client, ctx, booking)
    await _set_room(pg_session, ctx["room"]["units"][0]["id"], hk_status="dirty")
    url = f"{DESK}/bookings/{booking['id']}/check-in"

    refused = await pg_client.post(url, json={})
    accepted = await pg_client.post(url, json={"accept_not_ready": True})

    assert (refused.status_code, _code(refused)) == (409, "room_not_ready")
    assert refused.json()["detail"]["rooms"]
    assert accepted.status_code == 200, accepted.text


async def test_an_out_of_order_room_blocks_check_in(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _book(pg_client, ctx, 0, 2)
    await _rooms_given(pg_session, pg_client, ctx, booking)
    await _set_room(pg_session, ctx["room"]["units"][0]["id"], service_status="out_of_order")

    response = await pg_client.post(
        f"{DESK}/bookings/{booking['id']}/check-in", json={"accept_not_ready": True}
    )

    assert (response.status_code, _code(response)) == (409, "room_out_of_order")


async def test_a_room_still_occupied_blocks_check_in(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _book(pg_client, ctx, 0, 2)
    await _rooms_given(pg_session, pg_client, ctx, booking)
    await _set_room(pg_session, ctx["room"]["units"][0]["id"], fo_status="occupied")

    response = await pg_client.post(f"{DESK}/bookings/{booking['id']}/check-in", json={})

    assert (response.status_code, _code(response)) == (409, "room_occupied")


async def test_a_multi_room_booking_checks_in_as_a_whole(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _book(pg_client, ctx, 0, 2, units=2)
    rows = await pg_session.execute(
        text("SELECT id FROM reservationunit WHERE reservation_id = :b ORDER BY created_at, id"),
        {"b": booking["id"]},
    )
    first_line = str(rows.first()[0])
    await pg_client.put(
        f"{DESK}/lines/{first_line}/room", json={"unit_id": ctx["room"]["units"][0]["id"]}
    )
    url = f"{DESK}/bookings/{booking['id']}/check-in"

    partial = await pg_client.post(url, json={})
    assert (partial.status_code, _code(partial)) == (409, "rooms_missing")

    await pg_client.put(f"{DESK}/lines/{first_line}/room", json={"unit_id": None})
    await _rooms_given(pg_session, pg_client, ctx, booking)
    assert (await pg_client.post(url, json={})).status_code == 200
    states = await pg_session.execute(
        text("SELECT DISTINCT status FROM reservationunit WHERE reservation_id = :b"),
        {"b": booking["id"]},
    )
    assert [row[0] for row in states.all()] == ["in_house"]


async def test_checking_in_twice_is_refused(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _checked_in(pg_session, pg_client, ctx)

    response = await pg_client.post(f"{DESK}/bookings/{booking['id']}/check-in", json={})

    assert (response.status_code, _code(response)) == (409, "not_confirmed")


# ---- check-out and leaving early ---------------------------------------------------------


async def test_check_out_on_the_day_leaves_the_room_dirty(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _checked_in(pg_session, pg_client, ctx, 0, 2)
    await _backdate(pg_session, booking["id"], 2)

    response = await pg_client.post(f"{DESK}/bookings/{booking['id']}/check-out", json=LEAVE)

    assert response.status_code == 200, response.text
    detail = (await pg_client.get(f"{BOOKINGS}/{booking['id']}")).json()
    assert (detail["status"], Decimal(detail["total_amount"])) == ("checked_out", 1000000)
    room = next(
        r for r in (await _today(pg_client))["rooms"] if r["id"] == ctx["room"]["units"][0]["id"]
    )
    assert (room["fo_status"], room["hk_status"], room["booking_id"]) == ("vacant", "dirty", None)


async def test_leaving_early_needs_a_choice(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _checked_in(pg_session, pg_client, ctx, 0, 3)

    response = await pg_client.post(f"{DESK}/bookings/{booking['id']}/check-out", json={})

    assert (response.status_code, _code(response)) == (409, "early_choice_needed")


@pytest.mark.parametrize(("early", "total"), [("keep_price", 1500000), ("nights_stayed", 500000)])
async def test_leaving_early_frees_the_nights(pg_client, pg_session, early, total) -> None:
    ctx = await _setup(pg_client, units=1)
    booking = await _checked_in(pg_session, pg_client, ctx, -1, 2)  # came yesterday

    response = await pg_client.post(
        f"{DESK}/bookings/{booking['id']}/check-out", json={**LEAVE, "early": early}
    )

    assert response.status_code == 200, response.text
    detail = (await pg_client.get(f"{BOOKINGS}/{booking['id']}")).json()
    assert detail["departure"] == _on(ctx, 0)
    assert Decimal(detail["total_amount"]) == total
    assert sum(Decimal(n["amount"]) for n in detail["nightly"]) == total
    assert len(detail["nightly"]) == 1
    assert await sold_matches_bookings(pg_session, ctx["workspace"]["tenant"]["id"])
    again = await _book(pg_client, ctx, 0, 2)  # the room can be sold from today
    assert again["overbooking_risk"] is False


async def test_leaving_on_arrival_day_keeps_one_night(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _checked_in(pg_session, pg_client, ctx, 0, 3)

    response = await pg_client.post(
        f"{DESK}/bookings/{booking['id']}/check-out", json={**LEAVE, "early": "nights_stayed"}
    )

    assert response.status_code == 200, response.text
    detail = (await pg_client.get(f"{BOOKINGS}/{booking['id']}")).json()
    assert (detail["departure"], Decimal(detail["total_amount"])) == (_on(ctx, 1), 500000)


async def test_extending_keeps_old_prices_and_needs_the_room(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _checked_in(pg_session, pg_client, ctx, 0, 2)

    longer = await pg_client.patch(f"{BOOKINGS}/{booking['id']}", json={"departure": _on(ctx, 3)})

    assert longer.status_code == 200, longer.text
    assert Decimal(longer.json()["total_amount"]) == 1500000
    next_guest = await _book(pg_client, ctx, 3, 5)
    await _rooms_given(pg_session, pg_client, ctx, next_guest)
    blocked = await pg_client.patch(f"{BOOKINGS}/{booking['id']}", json={"departure": _on(ctx, 4)})
    assert blocked.status_code == 409
    assert (await pg_client.get(f"{BOOKINGS}/{booking['id']}")).json()["departure"] == _on(ctx, 3)


async def test_an_in_house_stay_cannot_end_before_today(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _checked_in(pg_session, pg_client, ctx, 0, 3)
    await _backdate(pg_session, booking["id"], 1)

    response = await pg_client.patch(
        f"{BOOKINGS}/{booking['id']}", json={"departure": _on(ctx, -1)}
    )

    assert response.status_code == 422


# ---- no-show -----------------------------------------------------------------------------


async def test_no_show_frees_the_nights(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client, units=1)
    booking = await _book(pg_client, ctx, 0, 2)

    response = await pg_client.post(f"{DESK}/bookings/{booking['id']}/no-show")

    assert response.status_code == 200, response.text
    assert (await pg_client.get(f"{BOOKINGS}/{booking['id']}")).json()["status"] == "no_show"
    assert await sold_matches_bookings(pg_session, ctx["workspace"]["tenant"]["id"])
    assert (await _today(pg_client))["arrivals"] == []


async def test_no_show_only_from_the_arrival_date(pg_client) -> None:
    ctx = await _setup(pg_client)
    booking = await _book(pg_client, ctx, 1, 3)

    response = await pg_client.post(f"{DESK}/bookings/{booking['id']}/no-show")

    assert (response.status_code, _code(response)) == (409, "cannot_no_show")


# ---- undo --------------------------------------------------------------------------------


async def test_undo_needs_a_reason(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _checked_in(pg_session, pg_client, ctx)

    response = await pg_client.post(f"{DESK}/bookings/{booking['id']}/undo", json={"reason": ""})

    assert response.status_code == 422


async def test_undo_check_in_the_same_day(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _checked_in(pg_session, pg_client, ctx)

    response = await pg_client.post(
        f"{DESK}/bookings/{booking['id']}/undo", json={"reason": "Salah tamu"}
    )

    assert response.status_code == 200, response.text
    today = await _today(pg_client)
    assert [entry["id"] for entry in today["arrivals"]] == [booking["id"]]
    room = next(r for r in today["rooms"] if r["id"] == ctx["room"]["units"][0]["id"])
    assert room["fo_status"] == "vacant"


async def test_undo_is_refused_on_a_later_day(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _checked_in(pg_session, pg_client, ctx)
    await pg_session.execute(
        text(
            "UPDATE reservationunit SET checked_in_at = checked_in_at - interval '2 days' "
            "WHERE reservation_id = :b"
        ),
        {"b": booking["id"]},
    )
    await pg_session.commit()

    response = await pg_client.post(
        f"{DESK}/bookings/{booking['id']}/undo", json={"reason": "Salah"}
    )

    assert (response.status_code, _code(response)) == (409, "undo_not_allowed")


async def test_undo_check_out_restores_the_guest(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _checked_in(pg_session, pg_client, ctx, 0, 1)
    await _backdate(pg_session, booking["id"], 1)
    await pg_client.post(f"{DESK}/bookings/{booking['id']}/check-out", json=LEAVE)

    response = await pg_client.post(
        f"{DESK}/bookings/{booking['id']}/undo", json={"reason": "Belum pergi"}
    )

    assert response.status_code == 200, response.text
    assert (await pg_client.get(f"{BOOKINGS}/{booking['id']}")).json()["status"] == "in_house"


async def test_undo_check_out_is_refused_after_leaving_early(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _checked_in(pg_session, pg_client, ctx, 0, 3)
    await pg_client.post(
        f"{DESK}/bookings/{booking['id']}/check-out", json={**LEAVE, "early": "keep_price"}
    )

    response = await pg_client.post(
        f"{DESK}/bookings/{booking['id']}/undo", json={"reason": "Salah"}
    )

    assert (response.status_code, _code(response)) == (409, "undo_not_allowed")


async def test_undo_no_show_takes_the_nights_back(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _book(pg_client, ctx, 0, 2)
    await pg_client.post(f"{DESK}/bookings/{booking['id']}/no-show")

    response = await pg_client.post(
        f"{DESK}/bookings/{booking['id']}/undo", json={"reason": "Tamu datang malam"}
    )

    assert response.status_code == 200, response.text
    assert (await pg_client.get(f"{BOOKINGS}/{booking['id']}")).json()["status"] == "confirmed"
    assert await sold_matches_bookings(pg_session, ctx["workspace"]["tenant"]["id"])


async def test_undo_no_show_is_refused_when_the_room_was_resold(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client, units=1)
    booking = await _book(pg_client, ctx, 0, 2)
    await pg_client.post(f"{DESK}/bookings/{booking['id']}/no-show")
    await _book(pg_client, ctx, 0, 2)

    response = await pg_client.post(
        f"{DESK}/bookings/{booking['id']}/undo", json={"reason": "Tamu datang"}
    )

    assert (response.status_code, _code(response)) == (409, "no_rooms_left")
    assert (await pg_client.get(f"{BOOKINGS}/{booking['id']}")).json()["status"] == "no_show"
    assert await sold_matches_bookings(pg_session, ctx["workspace"]["tenant"]["id"])


# ---- lists -------------------------------------------------------------------------------


async def test_lists_show_todays_work(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    arriving = await _book(pg_client, ctx, 0, 2)
    later = await _book(pg_client, ctx, 1, 3)
    late = await _book(pg_client, ctx, 0, 3)
    await _backdate(pg_session, late["id"], 2)
    too_old = await _book(pg_client, ctx, 0, 1)
    await _backdate(pg_session, too_old["id"], 8)

    today = await _today(pg_client)

    by_id = {entry["id"]: entry for entry in today["arrivals"]}
    assert set(by_id) == {arriving["id"], late["id"]}
    assert (by_id[arriving["id"]]["overdue"], by_id[late["id"]]["overdue"]) == (False, True)
    assert later["id"] not in by_id


async def test_departures_list_includes_overstays(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _checked_in(pg_session, pg_client, ctx, 0, 1)
    await _backdate(pg_session, booking["id"], 2)

    today = await _today(pg_client)

    assert [(e["id"], e["overdue"]) for e in today["departures"]] == [(booking["id"], True)]


async def test_front_desk_needs_permission(pg_client, other_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await add_staff_member(pg_session, other_client, ctx["workspace"], role=None)
    booking = await _book(pg_client, ctx, 0, 2)

    assert (await other_client.get(f"{DESK}/today")).status_code == 403
    assert (
        await other_client.post(f"{DESK}/bookings/{booking['id']}/check-in", json={})
    ).status_code == 403


async def test_tenants_are_separate(pg_client, other_client) -> None:
    ctx = await _setup(pg_client)
    await start_workspace(other_client)
    booking = await _book(pg_client, ctx, 0, 2)

    assert (await _today(other_client))["arrivals"] == []
    assert (
        await other_client.post(f"{DESK}/bookings/{booking['id']}/check-in", json={})
    ).status_code == 404


async def test_todays_finished_stays_stay_reachable_for_undo(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    left = await _checked_in(pg_session, pg_client, ctx, 0, 1)
    await _backdate(pg_session, left["id"], 1)
    missed = await _book(pg_client, ctx, 0, 2)
    await pg_client.post(f"{DESK}/bookings/{left['id']}/check-out", json=LEAVE)
    await pg_client.post(f"{DESK}/bookings/{missed['id']}/no-show")

    done = {entry["id"] for entry in (await _today(pg_client))["done_today"]}

    assert done == {left["id"], missed["id"]}


async def test_a_shortened_stay_is_not_offered_for_undo(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _checked_in(pg_session, pg_client, ctx, 0, 3)
    await pg_client.post(
        f"{DESK}/bookings/{booking['id']}/check-out", json={**LEAVE, "early": "keep_price"}
    )

    assert (await _today(pg_client))["done_today"] == []


async def test_a_no_show_has_nothing_left_to_collect(pg_client) -> None:
    ctx = await _setup(pg_client)
    booking = await _book(pg_client, ctx, 0, 2)

    await pg_client.post(f"{DESK}/bookings/{booking['id']}/no-show")

    detail = (await pg_client.get(f"{BOOKINGS}/{booking['id']}")).json()
    assert Decimal(detail["balance_due"]) == 0


# ---- review fixes ------------------------------------------------------------------------


async def test_charging_fewer_nights_needs_booking_edit(
    pg_client, other_client, pg_session
) -> None:
    from tests.pg.test_feature_access import _give_role

    ctx = await _setup(pg_client)
    booking = await _checked_in(pg_session, pg_client, ctx, 0, 3)
    staff = await add_staff_member(pg_session, other_client, ctx["workspace"], role=None)
    await _give_role(
        pg_session, staff["user_id"], "desk_only", ["frontdesk:view", "frontdesk:edit"]
    )
    await pg_session.commit()
    url = f"{DESK}/bookings/{booking['id']}/check-out"

    refused = await other_client.post(url, json={"early": "nights_stayed"})
    await pg_client.post(
        f"{BOOKINGS}/{booking['id']}/payments",
        json={"amount": "1500000", "method": "cash", "received_on": _on(ctx, 0)},
    )
    allowed = await other_client.post(url, json={"early": "keep_price"})

    assert (refused.status_code, _code(refused)) == (403, "price_permission")
    assert allowed.status_code == 200, allowed.text


async def test_charging_fewer_nights_than_paid_flags_a_refund(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _checked_in(pg_session, pg_client, ctx, 0, 3)
    paid = await pg_client.post(
        f"{BOOKINGS}/{booking['id']}/payments",
        json={"amount": "1000000", "method": "cash", "received_on": _on(ctx, 0)},
    )
    assert paid.status_code in (200, 201), paid.text

    await pg_client.post(
        f"{DESK}/bookings/{booking['id']}/check-out", json={"early": "nights_stayed"}
    )

    assert (await pg_client.get(f"{BOOKINGS}/{booking['id']}")).json()["refund_due"] is True
    audit = await pg_session.execute(
        text(
            "SELECT payload FROM tenantauditentry WHERE event_id = 'booking.checked_out' "
            "AND entity_id = :b"
        ),
        {"b": booking["id"]},
    )
    payload = audit.scalar_one()
    assert (payload["total_before"], payload["total_after"]) == ("1500000.00", "500000.00")


async def test_extending_an_overstay_is_not_refused_for_old_dates(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _checked_in(pg_session, pg_client, ctx, 0, 1)
    await _backdate(pg_session, booking["id"], 60)
    await pg_session.execute(
        text(
            "UPDATE reservationdailyrate SET stay_date = stay_date - 60 "
            "WHERE reservation_unit_id IN "
            "(SELECT id FROM reservationunit WHERE reservation_id = :b)"
        ),
        {"b": booking["id"]},
    )
    await pg_session.commit()

    response = await pg_client.patch(f"{BOOKINGS}/{booking['id']}", json={"departure": _on(ctx, 1)})

    assert response.status_code == 200, response.text


async def test_undo_check_out_is_refused_after_shortening_while_in_house(
    pg_client, pg_session
) -> None:
    ctx = await _setup(pg_client)
    booking = await _checked_in(pg_session, pg_client, ctx, -1, 3)
    await pg_client.patch(f"{BOOKINGS}/{booking['id']}", json={"departure": _on(ctx, 0)})
    await pg_client.post(f"{DESK}/bookings/{booking['id']}/check-out", json=LEAVE)

    response = await pg_client.post(
        f"{DESK}/bookings/{booking['id']}/undo", json={"reason": "Salah"}
    )

    assert (response.status_code, _code(response)) == (409, "undo_not_allowed")


async def test_undo_is_offered_only_on_the_day_of_check_in(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _checked_in(pg_session, pg_client, ctx)
    assert (await _today(pg_client))["in_house"][0]["can_undo"] is True
    await pg_session.execute(
        text(
            "UPDATE reservationunit SET checked_in_at = checked_in_at - interval '2 days' "
            "WHERE reservation_id = :b"
        ),
        {"b": booking["id"]},
    )
    await pg_session.commit()

    assert (await _today(pg_client))["in_house"][0]["can_undo"] is False


async def test_a_finished_stay_cannot_be_locked(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _book(pg_client, ctx, 0, 2)
    rows = await pg_session.execute(
        text("SELECT id FROM reservationunit WHERE reservation_id = :b"), {"b": booking["id"]}
    )
    line = rows.scalar_one()
    await pg_client.post(f"{DESK}/bookings/{booking['id']}/no-show")

    response = await pg_client.put(f"{DESK}/lines/{line}/lock", json={"locked": True})

    assert (response.status_code, _code(response)) == (409, "not_assignable")
