"""Closing a day: checks, override, summary snapshot, the closed-day lock and reopening."""

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.services.calendar_dates import property_today
from tests.pg.conftest import (
    add_staff_member,
    confirm_main_guest_id,
    make_booking,
    make_rate_plan,
    make_room_type,
    start_workspace,
)
from tests.pg.test_feature_access import _give_role

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _property_started_earlier(monkeypatch: pytest.MonkeyPatch, request) -> None:
    """Test properties are created today; most tests close days before that."""
    if "real_first_day" in request.keywords:
        return
    from app.services import closed_days

    real = closed_days.first_day
    monkeypatch.setattr(closed_days, "first_day", lambda prop: real(prop) - dt.timedelta(days=60))


EOD = "/api/end-of-day/days"
DESK = "/api/front-desk"
D = Decimal


async def _setup(client) -> dict:
    workspace = await start_workspace(client)
    room = await make_room_type(client, units=2, max_guests=2)
    plan = await make_rate_plan(client, [room], amount=500000)
    today = property_today(workspace["property"]["timezone"])
    return {
        "workspace": workspace,
        "room": room,
        "plan": plan,
        "today": today,
        "yesterday": today - dt.timedelta(days=1),
    }


def _day(ctx: dict, offset: int) -> str:
    return (ctx["today"] + dt.timedelta(days=offset)).isoformat()


async def _book(client, ctx, start: int, end: int, **fields) -> dict:
    return await make_booking(
        client, ctx["room"], ctx["plan"], _day(ctx, start), _day(ctx, end), **fields
    )


async def _read(client, day: str) -> dict:
    response = await client.get(f"{EOD}/{day}")
    assert response.status_code == 200, response.text
    return response.json()


async def _close(client, day: str, **body):
    return await client.post(f"{EOD}/{day}/close", json=body)


def _code(response) -> str:
    return response.json()["detail"]["code"]


async def _checked_in(session, client, ctx, booking: dict) -> None:
    line = (
        await session.execute(
            text("SELECT id FROM reservationunit WHERE reservation_id = :b"), {"b": booking["id"]}
        )
    ).scalar_one()
    unit = ctx["room"]["units"][0]["id"]
    assert (await client.put(f"{DESK}/lines/{line}/room", json={"unit_id": unit})).is_success
    await confirm_main_guest_id(client, booking["id"])
    answer = await client.post(f"{DESK}/bookings/{booking['id']}/check-in", json={})
    assert answer.status_code == 200, answer.text


# ---- what can be closed -----------------------------------------------------------------


async def test_today_cannot_be_closed(pg_client) -> None:
    ctx = await _setup(pg_client)

    response = await _close(pg_client, ctx["today"].isoformat())

    assert (response.status_code, _code(response)) == (409, "day_not_over")


async def test_a_quiet_yesterday_closes_with_a_snapshot(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    day = ctx["yesterday"].isoformat()

    closed = await _close(pg_client, day)
    body = await _read(pg_client, day)

    assert closed.status_code == 200, closed.text
    assert body["status"] == "closed"
    assert body["closed_by"]
    assert body["summary"]["rooms"]["available"] == 2
    stored = (
        await pg_session.execute(
            text(
                "SELECT stats->'rooms'->>'available' FROM businessday "
                "WHERE tenant_id = :t AND business_date = :d"
            ),
            {"t": ctx["workspace"]["tenant"]["id"], "d": ctx["yesterday"]},
        )
    ).scalar_one()
    assert stored == "2"


async def test_closing_a_day_closes_the_quiet_days_before_it(pg_client) -> None:
    ctx = await _setup(pg_client)
    await _close(pg_client, _day(ctx, -4))

    response = await _close(pg_client, _day(ctx, -1))

    assert response.status_code == 200, response.text
    for offset in (-3, -2, -1):
        assert (await _read(pg_client, _day(ctx, offset)))["status"] == "closed"


# ---- checks and override ----------------------------------------------------------------


async def test_a_guest_not_checked_in_blocks_closing(pg_client) -> None:
    ctx = await _setup(pg_client)
    await _book(pg_client, ctx, -1, 1)
    day = ctx["yesterday"].isoformat()

    body = await _read(pg_client, day)
    refused = await _close(pg_client, day)
    overridden = await _close(pg_client, day, override_reason="Tamu datang hari ini")

    blocking = {c["code"]: c["count"] for c in body["checks"] if c["level"] == "blocking"}
    assert blocking == {"arrivals_pending": 1}
    assert (refused.status_code, _code(refused)) == (409, "day_blocked")
    assert overridden.status_code == 200, overridden.text


async def test_overriding_needs_booking_rights(pg_client, other_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await _book(pg_client, ctx, -1, 1)
    staff = await add_staff_member(pg_session, other_client, ctx["workspace"], role=None)
    await _give_role(pg_session, staff["user_id"], "closer", ["endofday:view", "endofday:edit"])

    response = await _close(other_client, ctx["yesterday"].isoformat(), override_reason="Lanjut")

    assert (response.status_code, _code(response)) == (403, "override_permission")


async def test_an_open_drawer_of_the_day_blocks_closing(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await pg_client.post("/api/cash-drawers/mine/open", json={"opening_float": "0"})
    await pg_session.execute(
        text("UPDATE cashiershift SET business_date = :d WHERE tenant_id = :t"),
        {"d": ctx["yesterday"], "t": ctx["workspace"]["tenant"]["id"]},
    )
    await pg_session.commit()

    body = await _read(pg_client, ctx["yesterday"].isoformat())

    assert [c["code"] for c in body["checks"] if c["level"] == "blocking"] == ["drawers_open"]


async def test_the_override_reason_is_in_the_history(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await _book(pg_client, ctx, -1, 1)

    await _close(pg_client, ctx["yesterday"].isoformat(), override_reason="Tamu datang hari ini")

    logged = await pg_session.execute(
        text(
            "SELECT payload->>'override_reason' FROM tenantauditentry "
            "WHERE event_id = 'day.closed' AND tenant_id = :t"
        ),
        {"t": ctx["workspace"]["tenant"]["id"]},
    )
    assert logged.scalar_one() == "Tamu datang hari ini"


# ---- summary ----------------------------------------------------------------------------


async def test_the_summary_works_out_occupancy_adr_and_revpar(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _book(pg_client, ctx, -1, 1)
    await _checked_in(pg_session, pg_client, ctx, booking)
    await pg_client.post(
        f"/api/bills/{booking['id']}/payments",
        json={"amount": "200000", "method": "cash", "received_on": ctx["yesterday"].isoformat()},
    )
    future = await _book(pg_client, ctx, 5, 6, guest_name="Siti")
    await pg_client.post(
        f"/api/bills/{future['id']}/payments",
        json={"amount": "100000", "method": "qris", "received_on": ctx["yesterday"].isoformat()},
    )

    summary = (await _read(pg_client, ctx["yesterday"].isoformat()))["summary"]

    rooms = summary["rooms"]
    assert (rooms["available"], rooms["sold"]) == (2, 1)
    assert D(rooms["occupancy_pct"]) == D("50.0")
    assert (D(rooms["revenue"]), D(rooms["adr"]), D(rooms["revpar"])) == (
        D("500000"),
        D("500000"),
        D("250000"),
    )
    received = {row["method"]: D(row["amount"]) for row in summary["money"]["received"]}
    assert received == {"cash": D("200000"), "qris": D("100000")}
    assert D(summary["money"]["deposits"]) == D("100000")


# ---- lock and reopen --------------------------------------------------------------------


async def test_a_closed_day_refuses_back_dated_money(pg_client) -> None:
    ctx = await _setup(pg_client)
    booking = await _book(pg_client, ctx, 0, 2)
    paid = await pg_client.post(
        f"/api/bills/{booking['id']}/payments",
        json={"amount": "100000", "method": "cash", "received_on": ctx["yesterday"].isoformat()},
    )
    payment_id = paid.json()["payments"][0]["id"]
    await _close(pg_client, ctx["yesterday"].isoformat())

    late = await pg_client.post(
        f"/api/bills/{booking['id']}/payments",
        json={"amount": "50000", "method": "cash", "received_on": ctx["yesterday"].isoformat()},
    )
    removed = await pg_client.delete(f"/api/bookings/{booking['id']}/payments/{payment_id}")
    today = await pg_client.post(
        f"/api/bills/{booking['id']}/payments",
        json={"amount": "50000", "method": "cash", "received_on": ctx["today"].isoformat()},
    )

    assert (late.status_code, _code(late)) == (409, "day_closed")
    assert (removed.status_code, _code(removed)) == (409, "day_closed")
    assert today.status_code == 200, today.text


async def test_reopening_needs_a_reason_and_allows_changes_again(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _book(pg_client, ctx, 0, 2)
    day = ctx["yesterday"].isoformat()
    await _close(pg_client, day)

    no_reason = await pg_client.post(f"{EOD}/{day}/reopen", json={"reason": ""})
    reopened = await pg_client.post(f"{EOD}/{day}/reopen", json={"reason": "Pembayaran terlewat"})
    late = await pg_client.post(
        f"/api/bills/{booking['id']}/payments",
        json={"amount": "50000", "method": "cash", "received_on": day},
    )
    again = await _close(pg_client, day)

    assert no_reason.status_code == 422
    assert reopened.status_code == 200, reopened.text
    assert late.status_code == 200, late.text
    assert again.status_code == 200, again.text
    received = (await _read(pg_client, day))["summary"]["money"]["received"]
    assert [(r["method"], D(r["amount"])) for r in received] == [("cash", D("50000"))]


async def test_only_the_latest_closed_day_can_be_reopened(pg_client) -> None:
    ctx = await _setup(pg_client)
    await _close(pg_client, _day(ctx, -2))
    await _close(pg_client, _day(ctx, -1))

    response = await pg_client.post(f"{EOD}/{_day(ctx, -2)}/reopen", json={"reason": "Salah"})

    assert (response.status_code, _code(response)) == (409, "reopen_latest_first")


async def test_a_refund_dated_on_a_closed_day_is_refused(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await _book(pg_client, ctx, 0, 2)
    await pg_client.post(
        f"/api/bills/{booking['id']}/payments",
        json={
            "amount": "1200000",
            "method": "bank_transfer",
            "received_on": ctx["today"].isoformat(),
        },
    )
    await pg_session.execute(
        text(
            "UPDATE reservation SET source_detail = source_detail || "
            "'{\"refund_due\": true}'::jsonb WHERE id = :b"
        ),
        {"b": booking["id"]},
    )
    await pg_session.commit()
    await _close(pg_client, ctx["yesterday"].isoformat())

    response = await pg_client.post(
        f"/api/bookings/{booking['id']}/refund-done",
        json={"amount": "200000", "refunded_on": ctx["yesterday"].isoformat()},
    )

    assert (response.status_code, response.json()["detail"]["code"]) == (409, "day_closed")


# ---- front desk, access and tenants -----------------------------------------------------


async def test_the_front_desk_says_yesterday_is_not_closed(pg_client) -> None:
    ctx = await _setup(pg_client)

    before = (await pg_client.get(f"{DESK}/today")).json()["day_close"]
    await _close(pg_client, ctx["yesterday"].isoformat())
    after = (await pg_client.get(f"{DESK}/today")).json()["day_close"]

    assert before == {"unclosed": _day(ctx, -60)}  # the property's first day
    assert after == {"unclosed": None}


async def test_view_only_cannot_close(pg_client, other_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    staff = await add_staff_member(pg_session, other_client, ctx["workspace"], role=None)
    await _give_role(pg_session, staff["user_id"], "eod-viewer", ["endofday:view"])

    seen = await other_client.get(f"{EOD}/{ctx['yesterday'].isoformat()}")
    refused = await _close(other_client, ctx["yesterday"].isoformat())

    assert seen.status_code == 200
    assert refused.status_code == 403


async def test_without_a_role_nothing_is_reachable(pg_client, other_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await add_staff_member(pg_session, other_client, ctx["workspace"], role=None)

    assert (await other_client.get(f"{EOD}/{ctx['yesterday'].isoformat()}")).status_code == 403


async def test_tenants_are_separate(pg_client, other_client) -> None:
    ctx = await _setup(pg_client)
    await _close(pg_client, ctx["yesterday"].isoformat())
    await start_workspace(other_client)

    assert (await _read(other_client, ctx["yesterday"].isoformat()))["status"] == "open"


# ---- after review -----------------------------------------------------------------------


@pytest.mark.real_first_day
async def test_days_before_the_property_started_cannot_be_closed(pg_client) -> None:
    await _setup(pg_client)

    response = await _close(pg_client, "2000-01-01")
    desk = (await pg_client.get(f"{DESK}/today")).json()["day_close"]

    assert (response.status_code, _code(response)) == (409, "before_first_day")
    assert desk == {"unclosed": None}  # a property created today has no past day to close


async def test_the_first_close_starts_at_the_property_s_first_day(pg_client) -> None:
    ctx = await _setup(pg_client)

    await _close(pg_client, _day(ctx, -1))

    for offset in (-60, -30, -1):
        assert (await _read(pg_client, _day(ctx, offset)))["status"] == "closed"


async def test_a_closed_day_cannot_be_deleted_or_rewritten(pg_client, pg_session) -> None:
    from sqlalchemy.exc import DBAPIError

    ctx = await _setup(pg_client)
    await _close(pg_client, ctx["yesterday"].isoformat())
    where = {"t": ctx["workspace"]["tenant"]["id"], "d": ctx["yesterday"]}

    for statement in (
        "DELETE FROM businessday WHERE tenant_id = :t AND business_date = :d",
        "UPDATE businessday SET stats = '{}'::jsonb WHERE tenant_id = :t AND business_date = :d",
        "UPDATE businessday SET status = 'open' WHERE tenant_id = :t AND business_date = :d",
    ):
        with pytest.raises(DBAPIError):
            await pg_session.execute(text(statement), where)
        await pg_session.rollback()


async def test_reopening_keeps_the_old_figures_in_the_history(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    day = ctx["yesterday"].isoformat()
    await _close(pg_client, day)

    await pg_client.post(f"{EOD}/{day}/reopen", json={"reason": "Pembayaran terlewat"})

    logged = await pg_session.execute(
        text(
            "SELECT payload->'previous_stats'->'rooms'->>'available' FROM tenantauditentry "
            "WHERE event_id = 'day.reopened' AND tenant_id = :t"
        ),
        {"t": ctx["workspace"]["tenant"]["id"]},
    )
    assert logged.scalar_one() == "2"


async def test_invisible_characters_are_not_a_reason(pg_client) -> None:
    ctx = await _setup(pg_client)
    await _book(pg_client, ctx, -1, 1)

    response = await _close(
        pg_client, ctx["yesterday"].isoformat(), override_reason="\u200b\u200b\u200b"
    )

    assert response.status_code == 422


async def test_two_guests_left_unpaid_the_same_way_are_both_counted(pg_client, pg_session) -> None:

    ctx = await _setup(pg_client)
    first = await _book(pg_client, ctx, -2, -1)
    second = await _book(pg_client, ctx, -2, -1, guest_name="Siti")
    for booking in (first, second):
        await pg_session.execute(
            text(
                "UPDATE reservation SET source_detail = source_detail || "
                '\'{"left_unpaid": {"amount": "100000", "reason": "Nanti"}}\'::jsonb '
                "WHERE id = :b"
            ),
            {"b": booking["id"]},
        )
        await pg_session.execute(
            text(
                "UPDATE reservationunit SET checked_out_at = now() - interval '1 day' "
                "WHERE reservation_id = :b"
            ),
            {"b": booking["id"]},
        )
    await pg_session.commit()

    summary = (await _read(pg_client, ctx["yesterday"].isoformat()))["summary"]

    assert summary["left_unpaid"] == {"count": 2, "amount": "200000"}
