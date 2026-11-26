"""Cash drawers: float, desk payments, refunds and paid-outs, the count and the difference."""

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
    start_workspace,
)
from tests.pg.test_feature_access import _give_role

pytestmark = pytest.mark.integration

DRAWER = "/api/cash-drawers/mine"
D = Decimal


async def _setup(client) -> dict:
    workspace = await start_workspace(client)
    room = await make_room_type(client, units=2, max_guests=2)
    plan = await make_rate_plan(client, [room], amount=500000)
    today = property_today(workspace["property"]["timezone"])
    booking = await make_booking(
        client, room, plan, today.isoformat(), (today + dt.timedelta(days=2)).isoformat()
    )
    return {"workspace": workspace, "today": today, "booking": booking, "room": room, "plan": plan}


async def _pay(client, ctx, amount: int, method: str = "cash", on: dt.date | None = None):
    response = await client.post(
        f"/api/bills/{ctx['booking']['id']}/payments",
        json={
            "amount": str(amount),
            "method": method,
            "received_on": (on or ctx["today"]).isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _mine(client) -> dict | None:
    response = await client.get(DRAWER)
    assert response.status_code == 200, response.text
    return response.json()["drawer"]


def _code(response) -> str:
    return response.json()["detail"]["code"]


def _money(value) -> Decimal:
    return D(str(value))


async def test_the_drawer_adds_up_payments_and_paid_outs(pg_client) -> None:
    ctx = await _setup(pg_client)
    opened = await pg_client.post(f"{DRAWER}/open", json={"opening_float": "200000"})
    await _pay(pg_client, ctx, 300000)
    await _pay(pg_client, ctx, 400000, method="card")
    paid_out = await pg_client.post(
        f"{DRAWER}/paid-outs", json={"amount": "50000", "reason": "Beli gas"}
    )

    drawer = await _mine(pg_client)

    assert opened.status_code == 200, opened.text
    assert paid_out.status_code == 200, paid_out.text
    assert _money(drawer["opening_float"]) == D("200000")
    assert _money(drawer["cash_in"]) == D("300000")
    assert _money(drawer["paid_outs"]) == D("50000")
    assert _money(drawer["expected_cash"]) == D("450000")  # card money is not in the drawer
    methods = {row["method"]: _money(row["received"]) for row in drawer["by_method"]}
    assert methods == {"card": D("400000"), "cash": D("300000")}


async def test_counting_closes_the_drawer_and_a_difference_needs_a_note(pg_client) -> None:
    ctx = await _setup(pg_client)
    await pg_client.post(f"{DRAWER}/open", json={"opening_float": "100000"})
    await _pay(pg_client, ctx, 250000)

    no_note = await pg_client.post(f"{DRAWER}/close", json={"counted_cash": "340000"})
    closed = await pg_client.post(
        f"{DRAWER}/close", json={"counted_cash": "340000", "note": "Kembalian salah"}
    )

    assert (no_note.status_code, _code(no_note)) == (422, "note_needed")
    assert closed.status_code == 200, closed.text
    body = closed.json()
    assert (body["status"], _money(body["variance"])) == ("closed", D("-10000"))
    assert await _mine(pg_client) is None


async def test_paying_without_a_drawer_opens_one_with_no_float(pg_client) -> None:
    ctx = await _setup(pg_client)

    await _pay(pg_client, ctx, 300000)
    drawer = await _mine(pg_client)
    again = await pg_client.post(f"{DRAWER}/open", json={"opening_float": "100000"})

    assert _money(drawer["opening_float"]) == D("0")
    assert _money(drawer["cash_in"]) == D("300000")
    assert (again.status_code, _code(again)) == (409, "drawer_open")


async def test_a_back_dated_payment_is_not_in_today_s_drawer(pg_client) -> None:
    ctx = await _setup(pg_client)
    await pg_client.post(f"{DRAWER}/open", json={"opening_float": "0"})

    await _pay(pg_client, ctx, 300000, on=ctx["today"] - dt.timedelta(days=1))

    assert _money((await _mine(pg_client))["cash_in"]) == D("0")


async def test_a_removed_payment_leaves_the_drawer(pg_client) -> None:
    ctx = await _setup(pg_client)
    await pg_client.post(f"{DRAWER}/open", json={"opening_float": "0"})
    bill = await _pay(pg_client, ctx, 300000)
    payment_id = bill["payments"][0]["id"]

    removed = await pg_client.delete(f"/api/bookings/{ctx['booking']['id']}/payments/{payment_id}")

    assert removed.status_code == 200, removed.text
    assert _money((await _mine(pg_client))["cash_in"]) == D("0")


async def test_a_cash_refund_comes_out_of_the_drawer(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await pg_client.post(f"{DRAWER}/open", json={"opening_float": "500000"})
    await _pay(pg_client, ctx, 1200000, method="bank_transfer")
    await pg_session.execute(
        text(
            "UPDATE reservation SET source_detail = source_detail || "
            "'{\"refund_due\": true}'::jsonb WHERE id = :b"
        ),
        {"b": ctx["booking"]["id"]},
    )
    await pg_session.commit()

    refunded = await pg_client.post(
        f"/api/bookings/{ctx['booking']['id']}/refund-done",
        json={"amount": "200000", "refunded_on": ctx["today"].isoformat(), "method": "cash"},
    )

    assert refunded.status_code == 200, refunded.text
    drawer = await _mine(pg_client)
    assert _money(drawer["cash_out"]) == D("200000")
    assert _money(drawer["expected_cash"]) == D("300000")
    booking = (await pg_client.get(f"/api/bookings/{ctx['booking']['id']}")).json()
    assert len(booking["payments"]) == 1  # the refund ledger row is not a booking payment


async def test_paid_outs_never_touch_bookings_or_reports(pg_client) -> None:
    ctx = await _setup(pg_client)
    before = (await pg_client.get(f"/api/bookings/{ctx['booking']['id']}")).json()
    report_before = (
        await pg_client.get(
            "/api/reports/channels",
            params={"from": ctx["today"].isoformat(), "to": ctx["today"].isoformat()},
        )
    ).json()

    await pg_client.post(f"{DRAWER}/paid-outs", json={"amount": "75000", "reason": "Beli sabun"})

    after = (await pg_client.get(f"/api/bookings/{ctx['booking']['id']}")).json()
    report_after = (
        await pg_client.get(
            "/api/reports/channels",
            params={"from": ctx["today"].isoformat(), "to": ctx["today"].isoformat()},
        )
    ).json()
    assert (after["payments"], after["balance_due"]) == (before["payments"], before["balance_due"])
    assert report_after == report_before


async def test_paid_outs_need_a_reason_and_a_sensible_amount(pg_client) -> None:
    await _setup(pg_client)

    no_reason = await pg_client.post(f"{DRAWER}/paid-outs", json={"amount": "75000", "reason": ""})
    zero = await pg_client.post(f"{DRAWER}/paid-outs", json={"amount": "0", "reason": "Gas"})

    assert no_reason.status_code == 422
    assert zero.status_code == 422


async def test_a_drawer_needs_bill_rights(pg_client, other_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    staff = await add_staff_member(pg_session, other_client, ctx["workspace"], role=None)
    await _give_role(pg_session, staff["user_id"], "desk-viewer", ["frontdesk:view"])

    response = await other_client.post(f"{DRAWER}/open", json={"opening_float": "0"})

    assert response.status_code == 403


async def test_each_person_has_their_own_drawer(pg_client, other_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await add_staff_member(pg_session, other_client, ctx["workspace"], role="manager")
    await pg_client.post(f"{DRAWER}/open", json={"opening_float": "100000"})
    await _pay(pg_client, ctx, 300000)

    theirs = await _mine(other_client)
    opened = await other_client.post(f"{DRAWER}/open", json={"opening_float": "50000"})

    assert theirs is None
    assert opened.status_code == 200, opened.text
    assert _money(opened.json()["cash_in"]) == D("0")


# ---- after review -----------------------------------------------------------------------


async def test_a_payment_in_a_closed_drawer_cannot_be_removed(pg_client) -> None:
    ctx = await _setup(pg_client)
    bill = await _pay(pg_client, ctx, 300000)
    payment_id = bill["payments"][0]["id"]
    await pg_client.post(f"{DRAWER}/close", json={"counted_cash": "300000"})

    response = await pg_client.delete(f"/api/bookings/{ctx['booking']['id']}/payments/{payment_id}")

    assert (response.status_code, _code(response)) == (409, "drawer_closed")


async def test_yesterday_s_drawer_must_be_closed_before_taking_cash(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await pg_client.post(f"{DRAWER}/open", json={"opening_float": "0"})
    await pg_session.execute(
        text("UPDATE cashiershift SET business_date = business_date - 1 WHERE tenant_id = :t"),
        {"t": ctx["workspace"]["tenant"]["id"]},
    )
    await pg_session.commit()

    response = await pg_client.post(
        f"/api/bills/{ctx['booking']['id']}/payments",
        json={"amount": "100000", "method": "cash", "received_on": ctx["today"].isoformat()},
    )

    assert (response.status_code, response.json()["detail"]["code"]) == (409, "stale_drawer")


async def test_a_card_payment_does_not_open_a_drawer(pg_client) -> None:
    ctx = await _setup(pg_client)

    await _pay(pg_client, ctx, 300000, method="card")

    assert await _mine(pg_client) is None


async def test_a_cash_refund_dated_yesterday_still_leaves_today_s_drawer(
    pg_client, pg_session
) -> None:
    ctx = await _setup(pg_client)
    await pg_client.post(f"{DRAWER}/open", json={"opening_float": "500000"})
    await _pay(pg_client, ctx, 1200000, method="bank_transfer")
    await pg_session.execute(
        text(
            "UPDATE reservation SET source_detail = source_detail || "
            "'{\"refund_due\": true}'::jsonb WHERE id = :b"
        ),
        {"b": ctx["booking"]["id"]},
    )
    await pg_session.commit()

    await pg_client.post(
        f"/api/bookings/{ctx['booking']['id']}/refund-done",
        json={
            "amount": "100000",
            "refunded_on": (ctx["today"] - dt.timedelta(days=1)).isoformat(),
            "method": "cash",
        },
    )

    assert _money((await _mine(pg_client))["cash_out"]) == D("100000")


async def test_a_closed_drawer_cannot_be_changed_in_the_database(pg_client, pg_session) -> None:
    from sqlalchemy.exc import DBAPIError

    ctx = await _setup(pg_client)
    await pg_client.post(f"{DRAWER}/open", json={"opening_float": "0"})
    await pg_client.post(f"{DRAWER}/close", json={"counted_cash": "0"})

    with pytest.raises(DBAPIError):
        await pg_session.execute(
            text("UPDATE cashiershift SET counted_cash = 999 WHERE tenant_id = :t"),
            {"t": ctx["workspace"]["tenant"]["id"]},
        )
    await pg_session.rollback()
