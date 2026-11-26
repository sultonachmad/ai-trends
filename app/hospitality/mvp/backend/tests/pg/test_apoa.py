"""APOA: who still needs reporting, deadlines, marks, undo, access and the register."""

import csv
import datetime as dt
import io

import pytest
from sqlalchemy import text

from app.services.calendar_dates import property_today
from tests.pg.conftest import (
    add_staff_member,
    confirm_main_guest_id,
    make_booking,
    make_rate_plan,
    make_room_type,
    set_business_settings,
    start_workspace,
)
from tests.pg.test_feature_access import _give_role

pytestmark = pytest.mark.integration

APOA = "/api/apoa"
DESK = "/api/front-desk"
LEAVE = {"leave_unpaid_reason": "Bayar nanti"}  # these tests are not about money


def _passport(today: dt.date, **overrides) -> dict:
    return {
        "doc_type": "passport",
        "number": "PA1234567",
        "full_name": "Anna Schmidt",
        "birth_date": "1988-07-02",
        "gender": "female",
        "nationality": "DE",
        "expires_on": today.replace(year=today.year + 3).isoformat(),
        "visa_type": "voa",
        "entry_date": today.isoformat(),
        "checked": True,
        **overrides,
    }


async def _setup(client) -> dict:
    workspace = await start_workspace(client)
    room = await make_room_type(client, units=3, max_guests=4)
    plan = await make_rate_plan(client, [room], amount=500000)
    today = property_today(workspace["property"]["timezone"])
    return {"workspace": workspace, "room": room, "plan": plan, "today": today}


async def _booking(client, ctx, guest="Anna Schmidt", adults=2, nights=2) -> dict:
    return await make_booking(
        client,
        ctx["room"],
        ctx["plan"],
        ctx["today"].isoformat(),
        (ctx["today"] + dt.timedelta(days=nights)).isoformat(),
        guest_name=guest,
        adults=adults,
    )


async def _checked_in(session, client, ctx, booking: dict, unit: int = 0, ktp: bool = False):
    line = (
        await session.execute(
            text("SELECT id FROM reservationunit WHERE reservation_id = :b"), {"b": booking["id"]}
        )
    ).scalar_one()
    room = ctx["room"]["units"][unit]["id"]
    assert (await client.put(f"{DESK}/lines/{line}/room", json={"unit_id": room})).is_success
    fields = {} if ktp else _passport(ctx["today"])
    await confirm_main_guest_id(client, booking["id"], **fields)
    answer = await client.post(f"{DESK}/bookings/{booking['id']}/check-in", json={})
    assert answer.status_code == 200, answer.text


async def _list(client) -> dict:
    response = await client.get(APOA)
    assert response.status_code == 200, response.text
    return response.json()


def _code(response) -> str:
    return response.json()["detail"]["code"]


def _step(booking: dict, guest_id: str, step: str, **extra) -> dict:
    return {"booking_id": booking["id"], "guest_id": guest_id, "step": step, **extra}


async def _guest_id(client, booking: dict, index: int = 0) -> str:
    guests = (await client.get(f"/api/bookings/{booking['id']}/guests")).json()["guests"]
    return guests[index]["guest_id"]


# ---- the worklist -----------------------------------------------------------------------


async def test_a_foreign_guest_appears_to_report_with_a_deadline(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx)
    await _checked_in(pg_session, pg_client, ctx, booking)

    body = await _list(pg_client)

    [item] = body["to_report"]
    assert (item["full_name"], item["nationality"], item["masked_number"]) == (
        "Anna Schmidt",
        "DE",
        "••••4567",
    )
    assert item["step"] == "arrival"
    assert item["overdue"] is False
    checked_in = dt.datetime.fromisoformat(item["checked_in_at"])
    assert dt.datetime.fromisoformat(item["due_at"]) - checked_in == dt.timedelta(hours=24)
    assert body["deadline_hours"] == 24
    assert body["to_check_out"] == [] and body["done"] == []


async def test_indonesians_are_never_listed(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    ktp = await _booking(pg_client, ctx, guest="Budi Santoso", adults=1)
    await _checked_in(pg_session, pg_client, ctx, ktp, ktp=True)
    wni = await _booking(pg_client, ctx, guest="Siti", adults=1)
    await _checked_in(pg_session, pg_client, ctx, wni, unit=1)
    await confirm_main_guest_id(
        pg_client, wni["id"], **_passport(ctx["today"], nationality="ID", full_name="Siti")
    )

    assert (await _list(pg_client))["to_report"] == []


async def test_a_companion_added_after_check_in_appears(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx)
    await _checked_in(pg_session, pg_client, ctx, booking)

    added = await pg_client.post(
        f"/api/bookings/{booking['id']}/guests",
        json=_passport(ctx["today"], number="PB7654321", full_name="Ben Lee", nationality="AU"),
    )

    assert added.status_code == 200, added.text
    names = sorted(item["full_name"] for item in (await _list(pg_client))["to_report"])
    assert names == ["Anna Schmidt", "Ben Lee"]


async def test_a_foreign_party_with_unlisted_guests_is_flagged(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx, adults=3)
    await _checked_in(pg_session, pg_client, ctx, booking)

    [flag] = (await _list(pg_client))["unregistered"]

    assert (flag["booking_id"], flag["listed"], flag["expected"]) == (booking["id"], 1, 3)


async def test_past_the_deadline_is_overdue(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx)
    await _checked_in(pg_session, pg_client, ctx, booking)
    await pg_session.execute(
        text(
            "UPDATE reservationunit SET checked_in_at = now() - interval '25 hours' "
            "WHERE reservation_id = :b"
        ),
        {"b": booking["id"]},
    )
    await pg_session.commit()

    body = await _list(pg_client)
    desk = (await pg_client.get(f"{DESK}/today")).json()

    assert body["to_report"][0]["overdue"] is True
    assert desk["apoa"] == {"due": 1, "overdue": 1}


async def test_the_deadline_is_a_setting(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await set_business_settings(
        pg_session, ctx["workspace"]["property"]["id"], apoa_deadline_hours=6
    )
    booking = await _booking(pg_client, ctx)
    await _checked_in(pg_session, pg_client, ctx, booking)

    item = (await _list(pg_client))["to_report"][0]

    due = dt.datetime.fromisoformat(item["due_at"]) - dt.datetime.fromisoformat(
        item["checked_in_at"]
    )
    assert due == dt.timedelta(hours=6)


async def test_cancelled_bookings_are_never_listed(pg_client) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx)
    await confirm_main_guest_id(pg_client, booking["id"], **_passport(ctx["today"]))
    await pg_client.post(f"/api/bookings/{booking['id']}/cancel", json={"reason": "Batal"})

    body = await _list(pg_client)

    assert body["to_report"] == [] and body["unregistered"] == []


# ---- marking ----------------------------------------------------------------------------


async def test_marking_check_in_then_check_out(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx)
    await _checked_in(pg_session, pg_client, ctx, booking)
    guest = await _guest_id(pg_client, booking)

    reported = await pg_client.post(
        f"{APOA}/marks", json=_step(booking, guest, "arrival", reference="STT-001")
    )
    early = await pg_client.post(f"{APOA}/marks", json=_step(booking, guest, "departure"))
    out = await pg_client.post(
        f"{DESK}/bookings/{booking['id']}/check-out", json={"early": "keep_price", **LEAVE}
    )
    assert out.status_code == 200, out.text
    to_check_out = (await _list(pg_client))["to_check_out"]
    left = await pg_client.post(f"{APOA}/marks", json=_step(booking, guest, "departure"))

    assert reported.status_code == 200, reported.text
    assert reported.json()["to_report"] == []
    assert (early.status_code, _code(early)) == (409, "not_checked_out")
    assert [(i["full_name"], i["step"]) for i in to_check_out] == [("Anna Schmidt", "departure")]
    assert to_check_out[0]["arrival"]["reference"] == "STT-001"
    done = left.json()["done"]
    assert [(i["full_name"], i["arrival"]["status"], i["departure"]["status"]) for i in done] == [
        ("Anna Schmidt", "submitted", "submitted")
    ]
    assert done[0]["arrival"]["by"]


async def test_marking_twice_is_refused_and_records_no_full_number(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx)
    await _checked_in(pg_session, pg_client, ctx, booking)
    guest = await _guest_id(pg_client, booking)
    await pg_client.post(f"{APOA}/marks", json=_step(booking, guest, "arrival"))

    again = await pg_client.post(f"{APOA}/marks", json=_step(booking, guest, "arrival"))

    assert (again.status_code, _code(again)) == (409, "already_marked")
    row = (
        await pg_session.execute(
            text(
                "SELECT status, method, payload::text FROM foreignguestreport WHERE guest_id = :g"
            ),
            {"g": guest},
        )
    ).one()
    assert row[:2] == ("submitted", "manual")
    assert "PA1234567" not in row[2] and "4567" in row[2]


async def test_departure_needs_the_arrival_first(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx)
    await _checked_in(pg_session, pg_client, ctx, booking)
    guest = await _guest_id(pg_client, booking)
    await pg_client.post(
        f"{DESK}/bookings/{booking['id']}/check-out", json={"early": "keep_price", **LEAVE}
    )

    refused = await pg_client.post(f"{APOA}/marks", json=_step(booking, guest, "departure"))
    late = (await _list(pg_client))["to_report"]

    assert (refused.status_code, _code(refused)) == (409, "arrival_first")
    assert [item["full_name"] for item in late] == ["Anna Schmidt"]  # still to report, late


async def test_not_required_and_undo_need_reasons_and_are_logged(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx)
    await _checked_in(pg_session, pg_client, ctx, booking)
    guest = await _guest_id(pg_client, booking)

    no_reason = await pg_client.post(f"{APOA}/not-required", json=_step(booking, guest, "arrival"))
    skipped = await pg_client.post(
        f"{APOA}/not-required", json=_step(booking, guest, "arrival", reason="Diplomat, dicek")
    )
    undone = await pg_client.post(
        f"{APOA}/undo", json=_step(booking, guest, "arrival", reason="Salah tandai")
    )

    assert no_reason.status_code == 422
    assert skipped.json()["to_report"] == []
    assert [i["full_name"] for i in undone.json()["to_report"]] == ["Anna Schmidt"]
    events = (
        (
            await pg_session.execute(
                text(
                    "SELECT event_id FROM tenantauditentry WHERE entity_id = :b "
                    "AND event_id LIKE 'apoa.%' ORDER BY occurred_at"
                ),
                {"b": booking["id"]},
            )
        )
        .scalars()
        .all()
    )
    assert events == ["apoa.not_required", "apoa.undone"]


async def test_an_arrival_cannot_be_undone_after_the_departure(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx)
    await _checked_in(pg_session, pg_client, ctx, booking)
    guest = await _guest_id(pg_client, booking)
    await pg_client.post(f"{APOA}/marks", json=_step(booking, guest, "arrival"))
    await pg_client.post(
        f"{DESK}/bookings/{booking['id']}/check-out", json={"early": "keep_price", **LEAVE}
    )
    await pg_client.post(f"{APOA}/marks", json=_step(booking, guest, "departure"))

    refused = await pg_client.post(
        f"{APOA}/undo", json=_step(booking, guest, "arrival", reason="Salah tandai")
    )

    assert (refused.status_code, _code(refused)) == (409, "departure_first")


async def test_only_foreign_guests_on_the_booking_can_be_marked(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    ktp = await _booking(pg_client, ctx, guest="Budi Santoso", adults=1)
    await _checked_in(pg_session, pg_client, ctx, ktp, ktp=True)
    guest = await _guest_id(pg_client, ktp)

    response = await pg_client.post(f"{APOA}/marks", json=_step(ktp, guest, "arrival"))

    assert (response.status_code, _code(response)) == (409, "not_foreign")


async def test_a_booking_not_checked_in_cannot_be_marked(pg_client) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx)
    body = await confirm_main_guest_id(pg_client, booking["id"], **_passport(ctx["today"]))
    guest = body["guests"][0]["guest_id"]

    response = await pg_client.post(f"{APOA}/marks", json=_step(booking, guest, "arrival"))

    assert (response.status_code, _code(response)) == (409, "not_checked_in")


# ---- register ---------------------------------------------------------------------------


async def test_the_register_lists_marks_without_full_numbers(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx, guest="=cmd|' /C calc'!A0")
    await _checked_in(pg_session, pg_client, ctx, booking)
    guest = await _guest_id(pg_client, booking)
    await pg_client.post(f"{APOA}/marks", json=_step(booking, guest, "arrival", reference="STT-9"))
    day = ctx["today"].isoformat()

    response = await pg_client.get(f"{APOA}/register", params={"from": day, "to": day})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["cache-control"] == "no-store"
    assert response.text.startswith("\ufeff")  # spreadsheets read it as UTF-8
    rows = list(csv.reader(io.StringIO(response.text.removeprefix("\ufeff"))))
    assert rows[0][0] == "booking"
    assert len(rows) == 2
    assert "PA1234567" not in response.text
    assert "••••4567" in response.text and "STT-9" in response.text


async def test_the_register_refuses_a_reversed_or_long_range(pg_client) -> None:
    await _setup(pg_client)

    reversed_ = await pg_client.get(
        f"{APOA}/register", params={"from": "2026-02-01", "to": "2026-01-01"}
    )
    too_long = await pg_client.get(
        f"{APOA}/register", params={"from": "2025-01-01", "to": "2026-12-31"}
    )

    assert reversed_.status_code == 422
    assert too_long.status_code == 422


async def test_register_cells_cannot_start_a_formula(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx)
    await _checked_in(pg_session, pg_client, ctx, booking)
    guest = await _guest_id(pg_client, booking)
    await pg_client.post(
        f"{APOA}/marks", json=_step(booking, guest, "arrival", reference="=HYPERLINK(1)")
    )
    day = ctx["today"].isoformat()

    response = await pg_client.get(f"{APOA}/register", params={"from": day, "to": day})

    body = response.text.removeprefix("\ufeff")
    cells = [cell for row in csv.reader(io.StringIO(body)) for cell in row]
    assert not any(cell.startswith(("=", "+", "-", "@")) for cell in cells)


# ---- access -----------------------------------------------------------------------------


async def test_view_only_cannot_mark(pg_client, other_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx)
    await _checked_in(pg_session, pg_client, ctx, booking)
    guest = await _guest_id(pg_client, booking)
    staff = await add_staff_member(pg_session, other_client, ctx["workspace"], role=None)
    await _give_role(pg_session, staff["user_id"], "apoa-viewer", ["apoa:view"])

    seen = await other_client.get(APOA)
    refused = await other_client.post(f"{APOA}/marks", json=_step(booking, guest, "arrival"))

    assert seen.status_code == 200
    assert refused.status_code == 403


async def test_without_a_role_nothing_is_reachable(pg_client, other_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await add_staff_member(pg_session, other_client, ctx["workspace"], role=None)

    assert (await other_client.get(APOA)).status_code == 403
    assert (await other_client.get(f"{APOA}/register")).status_code == 403


async def test_tenants_are_separate(pg_client, other_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx)
    await _checked_in(pg_session, pg_client, ctx, booking)
    guest = await _guest_id(pg_client, booking)
    await start_workspace(other_client)

    assert (await _list(other_client))["to_report"] == []
    response = await other_client.post(f"{APOA}/marks", json=_step(booking, guest, "arrival"))
    assert (response.status_code, _code(response)) == (404, "not_found")


async def test_a_reported_companion_cannot_be_taken_off_the_booking(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx)
    await _checked_in(pg_session, pg_client, ctx, booking)
    added = await pg_client.post(
        f"/api/bookings/{booking['id']}/guests",
        json=_passport(ctx["today"], number="PB7654321", full_name="Ben Lee", nationality="AU"),
    )
    companion = added.json()["guests"][1]["guest_id"]
    await pg_client.post(f"{APOA}/marks", json=_step(booking, companion, "arrival"))

    refused = await pg_client.delete(f"/api/bookings/{booking['id']}/guests/{companion}")
    await pg_client.post(
        f"{APOA}/undo", json=_step(booking, companion, "arrival", reason="Salah tamu")
    )
    removed = await pg_client.delete(f"/api/bookings/{booking['id']}/guests/{companion}")

    assert (refused.status_code, _code(refused)) == (409, "guest_reported")
    assert removed.status_code == 204, removed.text


# ---- after review -----------------------------------------------------------------------


async def _undo(client, booking: dict):
    return await client.post(
        f"{DESK}/bookings/{booking['id']}/undo", json={"reason": "Salah tekan"}
    )


async def test_undo_check_in_is_refused_once_apoa_is_recorded(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx)
    await _checked_in(pg_session, pg_client, ctx, booking)
    guest = await _guest_id(pg_client, booking)
    await pg_client.post(f"{APOA}/marks", json=_step(booking, guest, "arrival"))

    refused = await _undo(pg_client, booking)
    await pg_client.post(f"{APOA}/undo", json=_step(booking, guest, "arrival", reason="Salah"))
    allowed = await _undo(pg_client, booking)

    assert (refused.status_code, _code(refused)) == (409, "apoa_marked")
    assert allowed.status_code == 200, allowed.text
    left = await pg_session.execute(
        text("SELECT count(*) FROM foreignguestreport WHERE guest_id = :g"), {"g": guest}
    )
    assert left.scalar_one() == 0  # nothing stale left behind for the next check-in


async def test_undo_check_out_is_refused_once_the_apoa_check_out_is_recorded(
    pg_client, pg_session
) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx, nights=1)
    await _checked_in(pg_session, pg_client, ctx, booking)
    guest = await _guest_id(pg_client, booking)
    await pg_client.post(f"{APOA}/marks", json=_step(booking, guest, "arrival"))
    await pg_client.post(
        f"{DESK}/bookings/{booking['id']}/check-out", json={"early": "keep_price", **LEAVE}
    )
    await pg_client.post(f"{APOA}/marks", json=_step(booking, guest, "departure"))

    refused = await _undo(pg_client, booking)

    assert (refused.status_code, _code(refused)) == (409, "apoa_marked")


async def test_a_skipped_arrival_needs_no_departure(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx, nights=1)
    await _checked_in(pg_session, pg_client, ctx, booking)
    guest = await _guest_id(pg_client, booking)
    await pg_client.post(
        f"{APOA}/not-required", json=_step(booking, guest, "arrival", reason="Dilaporkan agen")
    )
    await pg_client.post(
        f"{DESK}/bookings/{booking['id']}/check-out", json={"early": "keep_price", **LEAVE}
    )

    response = await pg_client.post(f"{APOA}/marks", json=_step(booking, guest, "departure"))

    assert (response.status_code, _code(response)) == (409, "arrival_skipped")
    assert (await _list(pg_client))["to_check_out"] == []


async def test_counts_need_apoa_access(pg_client, other_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx)
    await _checked_in(pg_session, pg_client, ctx, booking)
    staff = await add_staff_member(pg_session, other_client, ctx["workspace"], role=None)
    await _give_role(pg_session, staff["user_id"], "desk-no-apoa", ["frontdesk:view"])

    hidden = (await other_client.get(f"{DESK}/today")).json()["apoa"]
    shown = (await pg_client.get(f"{DESK}/today")).json()["apoa"]

    assert hidden == {"due": 0, "overdue": 0}
    assert shown == {"due": 1, "overdue": 0}


async def test_downloading_the_register_is_recorded(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    day = ctx["today"].isoformat()

    await pg_client.get(f"{APOA}/register", params={"from": day, "to": day})

    logged = await pg_session.execute(
        text(
            "SELECT payload->>'from', payload->>'rows' FROM tenantauditentry "
            "WHERE event_id = 'apoa.register_exported' AND tenant_id = :t"
        ),
        {"t": ctx["workspace"]["tenant"]["id"]},
    )
    assert tuple(logged.one()) == (day, "0")


async def test_the_register_forgets_passport_details_with_the_id_number(
    pg_client, pg_session, pg_session_factory
) -> None:
    from app.documents.storage import DocumentStorage
    from app.services.id_retention import purge_expired_ids

    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx)
    await _checked_in(pg_session, pg_client, ctx, booking)
    guest = await _guest_id(pg_client, booking)
    await pg_client.post(f"{APOA}/marks", json=_step(booking, guest, "arrival"))

    await purge_expired_ids(
        pg_session_factory, DocumentStorage(), today=ctx["today"] + dt.timedelta(days=4000)
    )

    payload = (
        await pg_session.execute(
            text("SELECT payload FROM foreignguestreport WHERE guest_id = :g"), {"g": guest}
        )
    ).scalar_one()
    assert "last4" not in payload and "visa_type" not in payload and "entry_date" not in payload
    assert payload["full_name"] == "Anna Schmidt"


async def test_reasons_refuse_direction_tricks(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _booking(pg_client, ctx)
    await _checked_in(pg_session, pg_client, ctx, booking)
    guest = await _guest_id(pg_client, booking)

    response = await pg_client.post(
        f"{APOA}/not-required",
        json=_step(booking, guest, "arrival", reason="ok ‮denied"),
    )

    assert response.status_code == 422
