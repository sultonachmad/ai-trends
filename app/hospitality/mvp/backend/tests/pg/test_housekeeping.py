"""Rooms to clean: tasks kept in step with the front desk, phone actions, inspection."""

import pytest
from sqlalchemy import text

from tests.pg.conftest import start_workspace
from tests.pg.test_front_desk import (
    DESK,
    LEAVE,
    _backdate,
    _checked_in,
    _set_room,
    _setup,
    _today,
)
from tests.pg.test_staff_invites import _joined, _team

pytestmark = pytest.mark.integration

HK = "/api/housekeeping"
PHONE = {"user-agent": "Mozilla/5.0 (Linux; Android 14) Mobile Safari/537.36"}


async def _board(client) -> dict:
    response = await client.get(f"{HK}/board")
    assert response.status_code == 200, response.text
    return response.json()


def _live(board: dict, unit_id: str) -> list[dict]:
    return [t for t in board["tasks"] if t["unit_id"] == unit_id]


async def _checked_out(session, client, ctx) -> dict:
    """A guest who arrived two days ago leaves today: their room is dirty."""
    booking = await _checked_in(session, client, ctx, 0, 2)
    await _backdate(session, booking["id"], 2)
    response = await client.post(f"{DESK}/bookings/{booking['id']}/check-out", json=LEAVE)
    assert response.status_code == 200, response.text
    return booking


async def _staying(session, client, ctx) -> dict:
    """A guest who checked in yesterday and stays two more nights."""
    booking = await _checked_in(session, client, ctx, 0, 3)
    await _backdate(session, booking["id"], 1)
    await session.execute(
        text(
            "UPDATE reservationunit SET checked_in_at = checked_in_at - interval '1 day' "
            "WHERE reservation_id = :b"
        ),
        {"b": booking["id"]},
    )
    await session.commit()
    return booking


def _code(response) -> str:
    return response.json()["detail"]["code"]


async def _act(client, task_id: str, action: str, headers=None, **body):
    return await client.post(f"{HK}/tasks/{task_id}/{action}", json=body or None, headers=headers)


# ---- tasks follow the front desk -----------------------------------------------------


async def test_a_check_out_puts_the_room_on_the_board_once(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await _checked_out(pg_session, pg_client, ctx)
    unit = ctx["room"]["units"][0]["id"]

    first = await _board(pg_client)
    again = await _board(pg_client)

    tasks = _live(first, unit)
    assert [(t["kind"], t["status"]) for t in tasks] == [("departure_clean", "pending")]
    assert [t["id"] for t in _live(again, unit)] == [tasks[0]["id"]]  # no duplicate


async def test_done_on_a_phone_makes_the_room_clean_for_the_front_desk(
    pg_client, pg_session
) -> None:
    ctx = await _setup(pg_client)
    await _checked_out(pg_session, pg_client, ctx)
    unit = ctx["room"]["units"][0]["id"]
    task = _live(await _board(pg_client), unit)[0]

    started = await _act(pg_client, task["id"], "start", PHONE)
    done = await _act(pg_client, task["id"], "done", PHONE)
    room = next(r for r in (await _today(pg_client))["rooms"] if r["id"] == unit)
    sources = (
        await pg_session.execute(
            text(
                "SELECT new_value, source FROM unitstatuslog WHERE unit_id = :u "
                "AND field = 'hk_status' AND task_id IS NOT NULL ORDER BY changed_at"
            ),
            {"u": unit},
        )
    ).all()

    assert started.status_code == 200, started.text
    assert done.status_code == 200, done.text
    assert room["hk_status"] == "clean"
    assert [tuple(row) for row in sources] == [("in_progress", "mobile"), ("clean", "mobile")]
    finished = _live(done.json(), unit)[0]
    assert (finished["status"], finished["mine"]) == ("done", True)
    assert finished["awaiting_inspection"] is False  # this property does not inspect


async def test_undoing_a_check_out_cancels_a_task_not_started(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _checked_out(pg_session, pg_client, ctx)
    unit = ctx["room"]["units"][0]["id"]
    await _board(pg_client)

    undone = await pg_client.post(
        f"{DESK}/bookings/{booking['id']}/undo", json={"reason": "Belum pergi"}
    )

    assert undone.status_code == 200, undone.text
    assert _live(await _board(pg_client), unit) == []


async def test_a_started_task_is_never_cancelled(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _checked_out(pg_session, pg_client, ctx)
    unit = ctx["room"]["units"][0]["id"]
    task = _live(await _board(pg_client), unit)[0]
    await _act(pg_client, task["id"], "start")

    await pg_client.post(f"{DESK}/bookings/{booking['id']}/undo", json={"reason": "Belum pergi"})

    assert [t["status"] for t in _live(await _board(pg_client), unit)] == ["in_progress"]


async def test_a_staying_guest_s_room_gets_a_stay_over_clean(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await _staying(pg_session, pg_client, ctx)
    unit = ctx["room"]["units"][0]["id"]

    tasks = _live(await _board(pg_client), unit)

    assert [t["kind"] for t in tasks] == ["stayover_clean"]
    assert tasks[0]["staying"]["adults"] >= 1


async def test_on_request_only_cleans_occupied_rooms_when_asked(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await _staying(pg_session, pg_client, ctx)
    unit = ctx["room"]["units"][0]["id"]
    saved = await pg_client.put(
        f"{HK}/settings", json={"ready_when": "clean", "stayover": "on_request"}
    )

    before = _live(saved.json(), unit)
    asked = await pg_client.post(f"{HK}/rooms/{unit}/clean-request")
    twice = await pg_client.post(f"{HK}/rooms/{unit}/clean-request")

    assert saved.status_code == 200, saved.text
    assert before == []  # nobody asked yet (the board read after saving tidies up)
    assert [t["kind"] for t in _live(asked.json(), unit)] == ["stayover_clean"]
    assert (twice.status_code, _code(twice)) == (409, "task_exists")
    assert _live(await _board(pg_client), unit) != []  # a requested task stays


async def test_a_guest_moved_to_another_room_leaves_the_old_one_to_clean(
    pg_client, pg_session
) -> None:
    ctx = await _setup(pg_client)
    booking = await _checked_in(pg_session, pg_client, ctx, 0, 3)
    first, second = ctx["room"]["units"][0]["id"], ctx["room"]["units"][1]["id"]
    line = (
        await pg_session.execute(
            text("SELECT id FROM reservationunit WHERE reservation_id = :b"), {"b": booking["id"]}
        )
    ).scalar_one()

    moved = await pg_client.put(f"{DESK}/lines/{line}/room", json={"unit_id": second})
    board = await _board(pg_client)

    assert moved.status_code == 200, moved.text
    assert [t["kind"] for t in _live(board, first)] == ["departure_clean"]
    assert _live(board, second) == []  # checked in today: no stay-over yet


async def test_yesterday_s_unfinished_room_moves_to_today(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await _checked_out(pg_session, pg_client, ctx)
    unit = ctx["room"]["units"][0]["id"]
    task = _live(await _board(pg_client), unit)[0]
    await _act(pg_client, task["id"], "take")
    await pg_session.execute(
        text("UPDATE task SET scheduled_for = scheduled_for - 1 WHERE id = :t"), {"t": task["id"]}
    )
    await pg_session.commit()

    board = await _board(pg_client)

    carried = _live(board, unit)
    assert [(t["id"], t["status"], t["mine"]) for t in carried] == [(task["id"], "assigned", True)]


async def test_rooms_out_of_order_get_no_task(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    unit = ctx["room"]["units"][0]["id"]
    await _set_room(pg_session, unit, hk_status="dirty", service_status="out_of_order")

    assert _live(await _board(pg_client), unit) == []


# ---- who works which room ------------------------------------------------------------


async def test_a_housekeeper_works_their_rooms_and_free_ones_only(
    pg_client, other_client, third_client, pg_session
) -> None:
    ctx = await _setup(pg_client, units=3)
    holder_email = (await _joined(pg_client, other_client))["email"]
    await _joined(pg_client, third_client)
    for index in range(2):
        await _set_room(pg_session, ctx["room"]["units"][index]["id"], hk_status="dirty")
    board = await _board(pg_client)
    team = {m["email"]: m["staff_id"] for m in (await _team(pg_client))["members"]}
    given, free = board["tasks"][0], board["tasks"][1]
    await pg_client.post(f"{HK}/tasks/{given['id']}/assign", json={"staff_id": team[holder_email]})
    holder, outsider = other_client, third_client

    refused = await _act(outsider, given["id"], "start")
    taken = await _act(outsider, free["id"], "take")
    grab = await _act(outsider, given["id"], "take")
    ok = await _act(holder, given["id"], "start")

    assert (refused.status_code, _code(refused)) == (403, "not_your_task")
    assert taken.status_code == 200, taken.text
    assert (grab.status_code, _code(grab)) == (403, "not_your_task")
    assert ok.status_code == 200, ok.text


async def test_a_housekeeper_cannot_assign_or_inspect(pg_client, other_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await _joined(pg_client, other_client)
    await _set_room(pg_session, ctx["room"]["units"][0]["id"], hk_status="dirty")
    task = (await _board(pg_client))["tasks"][0]

    assign = await other_client.post(f"{HK}/tasks/{task['id']}/assign", json={"staff_id": None})
    inspect = await other_client.post(f"{HK}/tasks/{task['id']}/inspect", json={"passed": True})
    settings = await other_client.put(
        f"{HK}/settings", json={"ready_when": "inspected", "stayover": "daily"}
    )

    assert (assign.status_code, inspect.status_code, settings.status_code) == (403, 403, 403)


async def test_split_evenly_shares_free_rooms(pg_client, other_client, pg_session) -> None:
    ctx = await _setup(pg_client, units=3)
    await _joined(pg_client, other_client)
    for unit in ctx["room"]["units"]:
        await _set_room(pg_session, unit["id"], hk_status="dirty")
    board = await _board(pg_client)
    staff = [s["id"] for s in board["staff"]]

    split = await pg_client.post(f"{HK}/split", json={"staff_ids": staff})
    stranger = await pg_client.post(
        f"{HK}/split", json={"staff_ids": ["00000000-0000-0000-0000-000000000000"]}
    )

    assert split.status_code == 200, split.text
    counts = {s: sum(t["assigned_staff_id"] == s for t in split.json()["tasks"]) for s in staff}
    assert sorted(counts.values()) == [1, 2]
    assert (stranger.status_code, _code(stranger)) == (422, "unknown_staff")


async def test_no_housekeeping_access_sees_nothing(pg_client, other_client, pg_session) -> None:
    from tests.pg.conftest import add_staff_member

    workspace = await start_workspace(pg_client)
    await add_staff_member(pg_session, other_client, workspace, role=None)

    assert (await other_client.get(f"{HK}/board")).status_code == 403


async def test_another_workspace_cannot_touch_my_tasks(pg_client, other_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await _set_room(pg_session, ctx["room"]["units"][0]["id"], hk_status="dirty")
    task = (await _board(pg_client))["tasks"][0]
    await start_workspace(other_client)

    theirs = await _board(other_client)
    start = await _act(other_client, task["id"], "start")
    room = await other_client.put(
        f"{HK}/rooms/{ctx['room']['units'][0]['id']}/status", json={"hk_status": "clean"}
    )

    assert theirs["tasks"] == []
    assert (start.status_code, _code(start)) == (404, "task_not_found")
    assert (room.status_code, _code(room)) == (404, "room_not_found")


# ---- inspection and readiness --------------------------------------------------------


async def test_with_inspection_a_clean_room_waits_for_the_supervisor(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await _checked_out(pg_session, pg_client, ctx)
    unit = ctx["room"]["units"][0]["id"]
    await pg_client.put(f"{HK}/settings", json={"ready_when": "inspected", "stayover": "daily"})
    task = _live(await _board(pg_client), unit)[0]
    await _act(pg_client, task["id"], "done")

    no_reason = await _act(pg_client, task["id"], "inspect", passed=False)
    failed = await _act(pg_client, task["id"], "inspect", passed=False, reason="Kamar mandi kotor")
    again = await _act(pg_client, task["id"], "done")
    passed = await _act(pg_client, task["id"], "inspect", passed=True)
    room = next(r for r in (await _today(pg_client))["rooms"] if r["id"] == unit)

    assert (no_reason.status_code, _code(no_reason)) == (422, "reason_needed")
    assert failed.status_code == 200, failed.text
    assert _live(again.json(), unit)[0]["awaiting_inspection"] is True
    assert _live(failed.json(), unit)[0]["status"] == "failed_inspection"
    assert again.status_code == 200, again.text
    assert passed.status_code == 200, passed.text
    assert room["hk_status"] == "inspected"


async def test_check_in_readiness_follows_the_setting(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    from tests.pg.test_front_desk import _book

    booking = await _book(pg_client, ctx, 0, 2)
    await pg_client.put(f"{HK}/settings", json={"ready_when": "inspected", "stayover": "daily"})

    clean = await pg_client.get(f"{DESK}/bookings/{booking['id']}/free-rooms")
    await _set_room(pg_session, ctx["room"]["units"][0]["id"], hk_status="inspected")
    inspected = await pg_client.get(f"{DESK}/bookings/{booking['id']}/free-rooms")

    assert clean.status_code == 200, clean.text
    assert not any(room["ready"] for room in clean.json())  # clean is not enough now
    assert [room["ready"] for room in inspected.json()][0] is True


async def test_only_a_cleaned_room_can_be_inspected(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await _set_room(pg_session, ctx["room"]["units"][0]["id"], hk_status="dirty")
    task = (await _board(pg_client))["tasks"][0]

    early = await _act(pg_client, task["id"], "inspect", passed=True)

    assert (early.status_code, _code(early)) == (409, "not_done_yet")


# ---- problems and the front desk -----------------------------------------------------


async def test_a_problem_reaches_the_front_desk_until_dealt_with(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await _checked_out(pg_session, pg_client, ctx)
    unit = ctx["room"]["units"][0]["id"]
    task = _live(await _board(pg_client), unit)[0]

    dnd = await _act(pg_client, task["id"], "problem", kind="dnd")
    repair = await _act(pg_client, task["id"], "problem", kind="repair", note="AC bocor")
    desk = (await _today(pg_client))["problems"]
    cleared = await _act(pg_client, task["id"], "clear-problem")
    after = (await _today(pg_client))["problems"]

    assert (dnd.status_code, _code(dnd)) == (409, "not_occupied")  # nobody in the room
    assert repair.status_code == 200, repair.text
    assert [(p["room_name"], p["kind"], p["note"]) for p in desk] == [
        (task["room_name"], "repair", "AC bocor")
    ]
    assert cleared.status_code == 200, cleared.text
    assert after == []


async def test_do_not_disturb_ends_a_stay_over_for_today(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await _staying(pg_session, pg_client, ctx)
    unit = ctx["room"]["units"][0]["id"]
    task = _live(await _board(pg_client), unit)[0]

    dnd = await _act(pg_client, task["id"], "problem", kind="dnd")
    board = await _board(pg_client)

    assert dnd.status_code == 200, dnd.text
    assert [(t["status"], t["problem_kind"]) for t in _live(board, unit)] == [
        ("skipped_dnd", "dnd")
    ]


async def test_marking_a_room_clean_by_hand_finishes_its_task(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await _checked_out(pg_session, pg_client, ctx)
    unit = ctx["room"]["units"][0]["id"]
    await _board(pg_client)

    marked = await pg_client.put(f"{HK}/rooms/{unit}/status", json={"hk_status": "clean"})
    source = (
        await pg_session.execute(
            text(
                "SELECT source FROM unitstatuslog WHERE unit_id = :u AND new_value = 'clean' "
                "ORDER BY changed_at DESC LIMIT 1"
            ),
            {"u": unit},
        )
    ).scalar_one()

    assert marked.status_code == 200, marked.text
    assert [t["status"] for t in _live(marked.json(), unit)] == ["done"]
    assert source == "staff"  # from a desk browser


async def test_big_buttons_are_remembered_for_the_person(pg_client) -> None:
    await _setup(pg_client)

    on = await pg_client.put(f"{HK}/me/mode", json={"big_buttons": True})

    assert on.status_code == 200, on.text
    assert (await _board(pg_client))["big_buttons"] is True


# ---- review fixes ----------------------------------------------------------------------


async def test_a_housekeeper_cannot_inspect_by_hand_or_clear_problems(
    pg_client, other_client, pg_session
) -> None:
    ctx = await _setup(pg_client)
    await _joined(pg_client, other_client)
    unit = ctx["room"]["units"][0]["id"]
    await _set_room(pg_session, unit, hk_status="dirty")
    task = (await _board(pg_client))["tasks"][0]
    await _act(pg_client, task["id"], "problem", kind="repair")

    inspected = await other_client.put(f"{HK}/rooms/{unit}/status", json={"hk_status": "inspected"})
    cleared = await _act(other_client, task["id"], "clear-problem")
    clean = await other_client.put(f"{HK}/rooms/{unit}/status", json={"hk_status": "clean"})

    assert (inspected.status_code, _code(inspected)) == (403, "inspect_permission")
    assert (cleared.status_code, _code(cleared)) == (403, "clear_permission")
    assert clean.status_code == 200, clean.text  # cleaning status by hand stays open to them


async def test_a_room_let_and_left_again_the_same_day_is_cleaned_again(
    pg_client, pg_session
) -> None:
    ctx = await _setup(pg_client)
    unit = ctx["room"]["units"][0]["id"]
    await _set_room(pg_session, unit, hk_status="dirty")
    first = (await _board(pg_client))["tasks"][0]
    await _act(pg_client, first["id"], "done")
    await _set_room(pg_session, unit, hk_status="dirty")  # the next guest has left too

    tasks = _live(await _board(pg_client), unit)

    assert sorted(t["status"] for t in tasks) == ["done", "pending"]


async def test_yesterday_s_started_room_stays_and_an_old_request_for_a_gone_guest_goes(
    pg_client, pg_session
) -> None:
    ctx = await _setup(pg_client)
    started_unit, asked_unit = ctx["room"]["units"][0]["id"], ctx["room"]["units"][1]["id"]
    await _set_room(pg_session, started_unit, hk_status="dirty")
    started = (await _board(pg_client))["tasks"][0]
    await _act(pg_client, started["id"], "start")
    await _set_room(pg_session, started_unit, hk_status="clean")  # need gone, work begun
    await pg_session.execute(
        text(
            "INSERT INTO task (tenant_id, property_id, task_kind, unit_id, scheduled_for, "
            "status, source) SELECT tenant_id, property_id, 'stayover_clean', id, "
            "CURRENT_DATE - 1, 'pending', 'manual' FROM unit WHERE id = :u"
        ),
        {"u": asked_unit},
    )
    await pg_session.execute(
        text("UPDATE task SET scheduled_for = scheduled_for - 1 WHERE id = :t"),
        {"t": started["id"]},
    )
    await pg_session.commit()

    board = await _board(pg_client)

    assert [t["status"] for t in _live(board, started_unit)] == ["in_progress"]
    assert _live(board, asked_unit) == []  # the room is empty: the request is dropped


async def test_housekeepers_see_guest_details_only_for_their_rooms(
    pg_client, other_client, third_client, pg_session
) -> None:
    ctx = await _setup(pg_client)
    await _staying(pg_session, pg_client, ctx)
    first = await _joined(pg_client, other_client)
    await _joined(pg_client, third_client)
    team = {m["email"]: m["staff_id"] for m in (await _team(pg_client))["members"]}
    task = (await _board(pg_client))["tasks"][0]
    await pg_client.post(f"{HK}/tasks/{task['id']}/assign", json={"staff_id": team[first["email"]]})

    theirs = (await _board(other_client))["tasks"][0]["staying"]
    others = (await _board(third_client))["tasks"][0]["staying"]
    owner = (await _board(pg_client))["tasks"][0]["staying"]

    assert theirs["name"] == owner["name"] != ""
    assert (others["name"], others["special_requests"]) == ("", None)
    assert others["adults"] == owner["adults"]  # still enough to prepare the room
