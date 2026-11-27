"""Repair requests: reporting, steps, rooms off sale and back, the housekeeping link."""

import datetime as dt
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text

from tests.pg.conftest import PNG_BYTES, image, start_workspace
from tests.pg.test_front_desk import DESK, _book, _rooms_given, _set_room, _setup, _today
from tests.pg.test_staff_invites import _joined, _team

pytestmark = pytest.mark.integration

MT = "/api/maintenance"
HK = "/api/housekeeping"


def _code(response) -> str:
    return response.json()["detail"]["code"]


async def _report(client, unit_id: str | None = None, **fields):
    data = {"category": "ac", "description": "AC bocor", **fields}
    if unit_id:
        data["unit_id"] = unit_id
    files = {"photo": ("x.png", fields.pop("photo"), "image/png")} if "photo" in fields else None
    data.pop("photo", None)
    return await client.post(MT, data=data, files=files)


async def _first(client, unit_id: str, **fields) -> dict:
    response = await _report(client, unit_id, **fields)
    assert response.status_code == 200, response.text
    return response.json()["requests"][0]


async def _blocked(session, room_type_id: str, night: dt.date) -> int:
    found = await session.execute(
        text("SELECT blocked FROM inventoryday WHERE unit_type_id = :t AND stay_date = :d"),
        {"t": room_type_id, "d": night},
    )
    return int(found.scalar() or 0)


def _night(ctx, offset: int) -> str:
    return (ctx["today"] + dt.timedelta(days=offset)).isoformat()


async def _off_sale(client, order_id: str, first: str, last: str):
    return await client.post(
        f"{MT}/{order_id}/off-sale", json={"first_night": first, "last_night": last}
    )


# ---- reporting ----------------------------------------------------------------------


async def test_staff_report_repairs_with_a_number_and_an_optional_photo(pg_client) -> None:
    ctx = await _setup(pg_client)
    unit = ctx["room"]["units"][0]["id"]

    first = await _report(pg_client, unit, urgent="true", photo=image("ac", PNG_BYTES))
    second = await _report(pg_client, None, place="Kolam renang", category="plumbing")
    board = second.json()
    with_photo = next(r for r in board["requests"] if r["number"] == "MT-0001")
    picture = await pg_client.get(f"{MT}/{with_photo['id']}/photo")

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert sorted(r["number"] for r in board["requests"]) == ["MT-0001", "MT-0002"]
    assert (with_photo["urgent"], with_photo["has_photo"], with_photo["status"]) == (
        True,
        True,
        "open",
    )
    assert picture.status_code == 200 and picture.content.startswith(b"\x89PNG")
    assert picture.headers["cache-control"] == "no-store"


async def test_a_request_needs_a_place_and_a_real_photo(pg_client) -> None:
    ctx = await _setup(pg_client)

    nowhere = await _report(pg_client, None)
    not_image = await _report(pg_client, ctx["room"]["units"][0]["id"], photo=b"not an image")

    assert (nowhere.status_code, _code(nowhere)) == (422, "where_needed")
    assert (not_image.status_code, _code(not_image)) == (422, "bad_photo")
    assert (await pg_client.get(MT)).json()["requests"] == []


async def test_needs_repair_from_cleaning_becomes_one_request(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    unit = ctx["room"]["units"][0]["id"]
    await _set_room(pg_session, unit, hk_status="dirty")
    task = (await pg_client.get(f"{HK}/board")).json()["tasks"][0]

    for _ in range(2):
        response = await pg_client.post(
            f"{HK}/tasks/{task['id']}/problem", json={"kind": "repair", "note": "Keran bocor"}
        )
        assert response.status_code == 200, response.text
    requests = (await pg_client.get(MT)).json()["requests"]

    assert [(r["unit_id"], r["description"], r["from_housekeeping"]) for r in requests] == [
        (unit, "Keran bocor", True)
    ]


# ---- steps ----------------------------------------------------------------------------


async def test_a_repair_goes_from_open_to_fixed(pg_client) -> None:
    ctx = await _setup(pg_client)
    order = await _first(pg_client, ctx["room"]["units"][0]["id"])

    started = await pg_client.post(f"{MT}/{order['id']}/start")
    no_note = await pg_client.post(f"{MT}/{order['id']}/wait", json={"note": ""})
    waiting = await pg_client.post(f"{MT}/{order['id']}/wait", json={"note": "Tunggu freon"})
    fixed = await pg_client.post(f"{MT}/{order['id']}/fix", json={"cost": "150000"})
    again = await pg_client.post(f"{MT}/{order['id']}/start")

    assert started.json()["requests"][0]["mine"] is True  # taken by whoever starts it
    assert no_note.status_code == 422
    assert waiting.json()["requests"][0]["status"] == "waiting_parts"
    done = fixed.json()["requests"][0]
    assert (done["status"], done["cost"]) == ("completed", "150000.00")
    assert (again.status_code, _code(again)) == (409, "request_closed")


async def test_a_repair_given_to_someone_else_is_theirs(
    pg_client, other_client, third_client, pg_session
) -> None:
    ctx = await _setup(pg_client)
    holder = await _joined(pg_client, other_client)
    await _joined(pg_client, third_client)
    staff = {m["email"]: m["staff_id"] for m in (await _team(pg_client))["members"]}
    order = await _first(pg_client, ctx["room"]["units"][0]["id"])
    given = await pg_client.post(
        f"{MT}/{order['id']}/assign", json={"staff_id": staff[holder["email"]]}
    )

    refused = await third_client.post(f"{MT}/{order['id']}/start")
    ok = await other_client.post(f"{MT}/{order['id']}/start")
    assign = await third_client.post(f"{MT}/{order['id']}/assign", json={"staff_id": None})
    off = await third_client.post(
        f"{MT}/{order['id']}/off-sale",
        json={"first_night": _night(ctx, 0), "last_night": _night(ctx, 0)},
    )

    assert given.json()["requests"][0]["status"] == "assigned"
    assert (refused.status_code, _code(refused)) == (403, "not_your_request")
    assert ok.status_code == 200, ok.text
    assert (assign.status_code, off.status_code) == (403, 403)  # supervisors only


async def test_an_outside_repairer_and_a_cancelled_request(pg_client) -> None:
    ctx = await _setup(pg_client)
    order = await _first(pg_client, ctx["room"]["units"][0]["id"])

    vendor = await pg_client.post(
        f"{MT}/{order['id']}/assign", json={"vendor_name": "Pak Made (AC)"}
    )
    stranger = await pg_client.post(
        f"{MT}/{order['id']}/assign", json={"staff_id": "00000000-0000-0000-0000-000000000000"}
    )
    cancelled = await pg_client.post(f"{MT}/{order['id']}/cancel", json={"reason": "Dobel"})

    assert vendor.json()["requests"][0]["vendor_name"] == "Pak Made (AC)"
    assert (stranger.status_code, _code(stranger)) == (422, "unknown_staff")
    done = cancelled.json()["requests"][0]
    assert (done["status"], done["status_note"]) == ("cancelled", "Dobel")


# ---- off sale and back ----------------------------------------------------------------


async def test_a_room_off_sale_is_blocked_everywhere_until_fixed(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client, units=2)
    unit = ctx["room"]["units"][0]["id"]
    order = await _first(pg_client, unit)

    off = await _off_sale(pg_client, order["id"], _night(ctx, 0), _night(ctx, 1))
    blocked_now = await _blocked(pg_session, ctx["room"]["id"], ctx["today"])
    booking = await _book(pg_client, ctx, 0, 1)
    free = await pg_client.get(f"{DESK}/bookings/{booking['id']}/free-rooms")
    room = next(r for r in (await _today(pg_client))["rooms"] if r["id"] == unit)
    desk = (await _today(pg_client))["maintenance"]
    fixed = await pg_client.post(f"{MT}/{order['id']}/fix", json={})
    back = next(r for r in (await _today(pg_client))["rooms"] if r["id"] == unit)
    cleaning = (await pg_client.get(f"{HK}/board")).json()["tasks"]

    assert off.status_code == 200, off.text
    assert off.json()["requests"][0]["off_sale"] == {
        "first_night": _night(ctx, 0),
        "last_night": _night(ctx, 1),
    }
    assert blocked_now == 1
    assert unit not in [r["id"] for r in free.json()]
    # Out of order once tonight's check-in time (14:00 at the property) has passed.
    begun = dt.datetime.now(ZoneInfo(ctx["workspace"]["property"]["timezone"])).hour >= 14
    assert room["service_status"] == ("out_of_order" if begun else "in_service")
    assert [(n["number"], n["off_sale_until"]) for n in desk] == [("MT-0001", _night(ctx, 1))]
    assert fixed.status_code == 200, fixed.text
    assert await _blocked(pg_session, ctx["room"]["id"], ctx["today"]) == 0
    assert (back["service_status"], back["hk_status"]) == ("in_service", "dirty")
    assert [(t["unit_id"], t["kind"]) for t in cleaning] == [(unit, "departure_clean")]


async def test_a_room_with_a_guest_booked_in_stays_on_sale(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client, units=2)
    booking = await _book(pg_client, ctx, 1, 3)
    await _rooms_given(pg_session, pg_client, ctx, booking)
    order = await _first(pg_client, ctx["room"]["units"][0]["id"])

    refused = await _off_sale(pg_client, order["id"], _night(ctx, 0), _night(ctx, 1))
    before = await _off_sale(pg_client, order["id"], _night(ctx, 0), _night(ctx, 0))

    assert (refused.status_code, _code(refused)) == (409, "room_booked")
    assert refused.json()["detail"]["items"] == [booking["number"]]
    assert before.status_code == 200, before.text  # the guest arrives after that night


async def test_a_room_off_sale_must_leave_enough_for_booked_guests(pg_client) -> None:
    ctx = await _setup(pg_client, units=1)
    await _book(pg_client, ctx, 0, 1)  # the only room of this type is sold tonight
    order = await _first(pg_client, ctx["room"]["units"][0]["id"])

    refused = await _off_sale(pg_client, order["id"], _night(ctx, 0), _night(ctx, 1))

    assert (refused.status_code, _code(refused)) == (409, "would_oversell")
    assert refused.json()["detail"]["items"] == [_night(ctx, 0)]


async def test_choosing_other_nights_replaces_the_first_choice(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client, units=2)
    order = await _first(pg_client, ctx["room"]["units"][0]["id"])
    await _off_sale(pg_client, order["id"], _night(ctx, 0), _night(ctx, 1))

    longer = await _off_sale(pg_client, order["id"], _night(ctx, 0), _night(ctx, 3))
    past = await _off_sale(pg_client, order["id"], _night(ctx, -1), _night(ctx, 0))
    blocked = [
        await _blocked(pg_session, ctx["room"]["id"], ctx["today"] + dt.timedelta(d))
        for d in range(5)
    ]

    room = next(
        r for r in (await _today(pg_client))["rooms"] if r["id"] == ctx["room"]["units"][0]["id"]
    )

    assert longer.status_code == 200, longer.text
    assert room["hk_status"] == "clean"  # other nights chosen: not a new clean
    assert (past.status_code, _code(past)) == (422, "bad_nights")
    assert blocked == [1, 1, 1, 1, 0]


async def test_back_on_sale_by_hand_and_when_the_nights_pass(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client, units=3)
    first, second = ctx["room"]["units"][0]["id"], ctx["room"]["units"][1]["id"]
    by_hand = await _first(pg_client, first)
    passing = await _first(pg_client, second)
    await _off_sale(pg_client, by_hand["id"], _night(ctx, 0), _night(ctx, 1))
    await _off_sale(pg_client, passing["id"], _night(ctx, 0), _night(ctx, 0))
    await pg_session.execute(
        text(
            "UPDATE unitblock SET start_at = start_at - interval '3 days', "
            "end_at = end_at - interval '3 days' WHERE work_order_id = :o"
        ),
        {"o": passing["id"]},
    )
    await pg_session.commit()

    on = await pg_client.post(f"{MT}/{by_hand['id']}/on-sale")
    not_off = await pg_client.post(f"{MT}/{by_hand['id']}/on-sale")
    board = (await pg_client.get(MT)).json()
    rooms = {r["id"]: r for r in (await _today(pg_client))["rooms"]}

    assert on.status_code == 200, on.text
    assert (not_off.status_code, _code(not_off)) == (409, "not_off_sale")
    assert all(r["off_sale"] is None for r in board["requests"])
    assert rooms[first]["service_status"] == rooms[second]["service_status"] == "in_service"


async def test_a_room_off_sale_later_cannot_be_given_for_those_nights(
    pg_client, pg_session
) -> None:
    ctx = await _setup(pg_client, units=2)
    unit = ctx["room"]["units"][0]["id"]
    order = await _first(pg_client, unit)
    await _off_sale(pg_client, order["id"], _night(ctx, 2), _night(ctx, 3))
    booking = await _book(pg_client, ctx, 2, 4)
    line = (
        await pg_session.execute(
            text("SELECT id FROM reservationunit WHERE reservation_id = :b"), {"b": booking["id"]}
        )
    ).scalar_one()

    given = await pg_client.put(f"{DESK}/lines/{line}/room", json={"unit_id": unit})
    room = next(r for r in (await _today(pg_client))["rooms"] if r["id"] == unit)

    assert (given.status_code, _code(given)) == (409, "room_out_of_order")
    assert room["service_status"] == "in_service"  # its nights have not begun


# ---- access ---------------------------------------------------------------------------


async def test_a_housekeeper_reports_but_cannot_cancel(pg_client, other_client) -> None:
    ctx = await _setup(pg_client)
    await _joined(pg_client, other_client)

    reported = await _report(other_client, ctx["room"]["units"][0]["id"])
    order = reported.json()["requests"][0]
    cancel = await other_client.post(f"{MT}/{order['id']}/cancel", json={"reason": "x"})

    assert reported.status_code == 200, reported.text
    assert order["reported_by_name"] == "Wayan"
    assert cancel.status_code == 403


async def test_another_workspace_sees_and_touches_nothing(pg_client, other_client) -> None:
    ctx = await _setup(pg_client)
    order = await _first(pg_client, ctx["room"]["units"][0]["id"], photo=image("x", PNG_BYTES))
    await start_workspace(other_client)

    theirs = (await other_client.get(MT)).json()
    start = await other_client.post(f"{MT}/{order['id']}/start")
    photo = await other_client.get(f"{MT}/{order['id']}/photo")
    room = await _report(other_client, ctx["room"]["units"][0]["id"])

    assert theirs["requests"] == []
    assert (start.status_code, _code(start)) == (404, "request_not_found")
    assert photo.status_code == 404
    assert (room.status_code, _code(room)) == (422, "where_needed")


async def test_only_a_supervisor_marks_a_room_off_sale_fixed(pg_client, other_client) -> None:
    ctx = await _setup(pg_client, units=2)
    await _joined(pg_client, other_client)
    order = await _first(pg_client, ctx["room"]["units"][0]["id"])
    await _off_sale(pg_client, order["id"], _night(ctx, 0), _night(ctx, 1))

    by_housekeeper = await other_client.post(f"{MT}/{order['id']}/fix", json={})
    by_owner = await pg_client.post(f"{MT}/{order['id']}/fix", json={})

    assert (by_housekeeper.status_code, _code(by_housekeeper)) == (403, "supervisor_needed")
    assert by_owner.status_code == 200, by_owner.text


async def test_a_repair_given_to_an_outside_repairer_is_not_free(pg_client, other_client) -> None:
    ctx = await _setup(pg_client)
    await _joined(pg_client, other_client)
    order = await _first(pg_client, ctx["room"]["units"][0]["id"])
    await pg_client.post(f"{MT}/{order['id']}/assign", json={"vendor_name": "Pak Made"})

    refused = await other_client.post(f"{MT}/{order['id']}/start")
    mine = (await other_client.get(MT)).json()["requests"][0]["mine"]

    assert (refused.status_code, _code(refused)) == (403, "not_your_request")
    assert mine is False


async def test_two_requests_cannot_both_take_one_room_off_sale(pg_client) -> None:
    ctx = await _setup(pg_client, units=2)
    unit = ctx["room"]["units"][0]["id"]
    leak = await _first(pg_client, unit)
    ac = await _first(pg_client, unit)
    await _off_sale(pg_client, leak["id"], _night(ctx, 0), _night(ctx, 1))

    second = await _off_sale(pg_client, ac["id"], _night(ctx, 1), _night(ctx, 2))

    assert (second.status_code, _code(second)) == (409, "already_off_sale")
    assert second.json()["detail"]["items"] == [leak["number"]]


async def test_check_in_refuses_a_room_that_went_off_sale(pg_client, pg_session) -> None:
    from tests.pg.conftest import confirm_main_guest_id

    ctx = await _setup(pg_client, units=2)
    unit = ctx["room"]["units"][0]["id"]
    booking = await _book(pg_client, ctx, 0, 1)
    await _rooms_given(pg_session, pg_client, ctx, booking)
    await confirm_main_guest_id(pg_client, booking["id"])
    await pg_session.execute(  # a block made before the room was given, as an old record
        text(
            "INSERT INTO unitblock (tenant_id, unit_id, kind, start_at, end_at, status) "
            "SELECT tenant_id, id, 'out_of_order', now() - interval '1 hour', "
            "now() + interval '2 days', 'active' FROM unit WHERE id = :u"
        ),
        {"u": unit},
    )
    await pg_session.commit()

    refused = await pg_client.post(f"{DESK}/bookings/{booking['id']}/check-in", json={})

    assert (refused.status_code, _code(refused)) == (409, "room_out_of_order")
