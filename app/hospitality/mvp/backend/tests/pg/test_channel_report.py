"""The channel report: bookings, nights, revenue, commission and net revenue by source."""

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.services.calendar_dates import property_today
from app.services.channel_report import commission_in_period
from tests.pg.conftest import (
    add_staff_member,
    make_rate_plan,
    make_room_type,
    start_workspace,
)

pytestmark = pytest.mark.integration

REPORT = "/api/reports/channels"


async def _setup(client, *, units: int = 5, amount: int = 500000) -> dict:
    workspace = await start_workspace(client)
    room = await make_room_type(client, units=units, max_guests=2)
    plan = await make_rate_plan(client, [room], amount=amount)
    return {"workspace": workspace, "room": room, "plan": plan}


def _day(ctx: dict, offset: int) -> str:
    today = property_today(ctx["workspace"]["property"]["timezone"])
    return (today + dt.timedelta(days=offset)).isoformat()


async def _book(client, ctx, first: int, last: int, **over) -> dict:
    response = await client.post(
        "/api/bookings",
        json={
            "arrival": _day(ctx, first),
            "departure": _day(ctx, last),
            "room_type_id": ctx["room"]["id"],
            "rate_plan_id": ctx["plan"]["id"],
            "guest_name": "Tamu Laporan",
            **over,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _report(client, ctx, first: int, last: int) -> dict:
    response = await client.get(REPORT, params={"from": _day(ctx, first), "to": _day(ctx, last)})
    assert response.status_code == 200, response.text
    return response.json()


async def _make_channel_booking(session, ctx, booking: dict, commission: str) -> None:
    """Turn a booking into a channel booking with a stored commission."""
    tenant = ctx["workspace"]["tenant"]["id"]
    channel = (
        await session.execute(
            text(
                "INSERT INTO channel (tenant_id, code, name, kind, is_direct) "
                "VALUES (:t, 'ota_test', 'Agen Uji', 'ota', false) "
                "ON CONFLICT (tenant_id, code) DO UPDATE SET name = excluded.name RETURNING id"
            ),
            {"t": tenant},
        )
    ).scalar_one()
    await session.execute(
        text("UPDATE reservation SET channel_id = :c, commission_amount = :a WHERE id = :b"),
        {"c": channel, "a": Decimal(commission), "b": booking["id"]},
    )
    await session.commit()


def test_commission_is_spread_by_revenue() -> None:
    assert commission_in_period(
        Decimal("150000"), Decimal("500000"), Decimal("1000000")
    ) == Decimal("75000.00")
    assert commission_in_period(None, Decimal("1"), Decimal("1")) == Decimal("0")
    assert commission_in_period(Decimal("10"), Decimal("1"), Decimal("0")) == Decimal("0")
    assert commission_in_period(Decimal("100"), Decimal("1"), Decimal("3")) == Decimal("33.33")


async def test_an_empty_period_is_all_zeros(pg_client) -> None:
    ctx = await _setup(pg_client)
    report = await _report(pg_client, ctx, 1, 5)
    assert report["rows"] == []
    assert report["total"]["revenue"] == "0.00"
    assert report["total"]["cancellation_rate"] == "0.0"


async def test_direct_and_channel_rows_add_up(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await _book(pg_client, ctx, 2, 4)  # direct: 2 nights, 1,000,000
    sold = await _book(pg_client, ctx, 2, 5)  # channel: 3 nights, 1,500,000
    await _make_channel_booking(pg_session, ctx, sold, "225000")

    report = await _report(pg_client, ctx, 0, 10)

    [first, second] = report["rows"]
    assert (first["name"], first["is_direct"], first["revenue"]) == (
        "Agen Uji",
        False,
        "1500000.00",
    )
    assert (first["commission"], first["net_revenue"]) == ("225000.00", "1275000.00")
    assert (first["average_per_night"], first["revenue_share"]) == ("500000.00", "60.0")
    assert (second["is_direct"], second["commission"]) == (True, "0.00")
    assert report["direct"]["revenue"] == "1000000.00"
    assert report["channels"]["revenue"] == "1500000.00"
    total = report["total"]
    assert (total["bookings"], total["nights"], total["revenue"]) == (2, 5, "2500000.00")
    assert total["net_revenue"] == "2275000.00"


async def test_a_stay_across_the_edge_counts_only_nights_inside(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    sold = await _book(pg_client, ctx, 3, 7)  # nights 3, 4, 5, 6
    await _make_channel_booking(pg_session, ctx, sold, "200000")

    inside = await _report(pg_client, ctx, 5, 10)
    before = await _report(pg_client, ctx, 0, 4)

    assert (inside["total"]["nights"], inside["total"]["revenue"]) == (2, "1000000.00")
    assert inside["total"]["commission"] == "100000.00"
    assert (before["total"]["nights"], before["total"]["commission"]) == (2, "100000.00")


async def test_two_units_count_as_room_nights(pg_client) -> None:
    ctx = await _setup(pg_client)
    await _book(pg_client, ctx, 2, 4, units=2, adults=2)
    total = (await _report(pg_client, ctx, 0, 10))["total"]
    assert (total["bookings"], total["nights"], total["revenue"]) == (1, 4, "2000000.00")


async def test_cancelled_bookings_are_not_revenue_but_are_counted(pg_client) -> None:
    ctx = await _setup(pg_client)
    await _book(pg_client, ctx, 2, 3)
    gone = await _book(pg_client, ctx, 2, 3)
    await pg_client.post(f"/api/bookings/{gone['id']}/cancel", json={})

    total = (await _report(pg_client, ctx, 0, 10))["total"]

    assert (total["bookings"], total["revenue"], total["cancelled"]) == (1, "500000.00", 1)
    assert total["cancellation_rate"] == "50.0"


async def test_unpaid_holds_are_neither_revenue_nor_cancellations(pg_client, guest) -> None:
    ctx = await _setup(pg_client)
    slug = "laporan-" + ctx["workspace"]["tenant"]["id"][:8]
    await pg_client.put(
        "/api/booking-page",
        json={"slug": slug, "is_published": True, "sold_plan_ids": [ctx["plan"]["id"]]},
    )
    order = {
        "idempotency_key": "report-hold-key-0001",
        "arrival": _day(ctx, 2),
        "departure": _day(ctx, 3),
        "room_type_id": ctx["room"]["id"],
        "rate_plan_id": ctx["plan"]["id"],
        "adults": 1,
        "guest_name": "Tamu Hold",
        "guest_phone": "+6281234567088",
        "pay_choice": "deposit",
        "expected_total": "500000",
        "accepted_terms": True,
    }
    held = (await guest.post(f"/api/book/{slug}/checkout", json=order)).json()

    assert (await _report(pg_client, ctx, 0, 10))["total"]["bookings"] == 0
    token = held["booking_path"].rsplit("/", 1)[1]
    await guest.post(f"/api/guest-booking/{token}/cancel", json={})
    assert (await _report(pg_client, ctx, 0, 10))["total"]["cancelled"] == 0


@pytest.mark.parametrize(("first", "last"), [(5, 1), (0, 400)])
async def test_bad_periods_are_refused(pg_client, first: int, last: int) -> None:
    ctx = await _setup(pg_client)
    response = await pg_client.get(REPORT, params={"from": _day(ctx, first), "to": _day(ctx, last)})
    assert response.status_code == 422


async def test_the_report_needs_its_permission(pg_client, other_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await add_staff_member(pg_session, other_client, ctx["workspace"], role=None)
    response = await other_client.get(REPORT, params={"from": _day(ctx, 0), "to": _day(ctx, 1)})
    assert response.status_code == 403


async def test_another_tenant_sees_nothing(pg_client, other_client) -> None:
    ctx = await _setup(pg_client)
    await _book(pg_client, ctx, 2, 3)
    await start_workspace(other_client)
    theirs = await other_client.get(REPORT, params={"from": _day(ctx, 0), "to": _day(ctx, 10)})
    assert theirs.json()["rows"] == []


async def test_a_reversed_period_is_named_as_such(pg_client) -> None:
    await start_workspace(pg_client)
    response = await pg_client.get(
        "/api/reports/channels", params={"from": "2027-01-02", "to": "2027-01-01"}
    )
    assert response.status_code == 422
    assert "before" in response.json()["detail"]
