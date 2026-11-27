"""The monthly tax summary adds up to the bills, and its files are safe and recorded."""

import csv
import datetime as dt
import io
from decimal import Decimal

import pytest
from sqlalchemy import text

from tests.pg.conftest import make_booking, start_workspace
from tests.pg.test_bill_taxes import BILLS, _bill, _booking, _set_taxes, _setup
from tests.pg.test_staff_invites import _joined

pytestmark = pytest.mark.integration

TAX = "/api/tax-summary"
D = Decimal


def _month(day: dt.date) -> str:
    return day.strftime("%Y-%m")


async def _summary(client, month: str) -> dict:
    response = await client.get(f"{TAX}/{month}")
    assert response.status_code == 200, response.text
    return response.json()


async def _months_total(client, days: list[dt.date], key: str) -> Decimal:
    months = sorted({_month(day) for day in days})
    return sum([D((await _summary(client, m))["totals"][key]) for m in months], D("0"))


async def _charge(client, booking, category: str, amount: int) -> None:
    response = await client.post(
        f"{BILLS}/{booking['id']}/charges",
        json={"category": category, "description": "x", "quantity": 1, "unit_price": amount},
    )
    assert response.status_code == 200, response.text


async def _matches_bill(client, ctx, booking) -> None:
    bill = await _bill(client, booking)
    days = [ctx["today"] + dt.timedelta(days=d) for d in range(3)]
    assert await _months_total(client, days, "service") == D(bill["taxes"]["service"])
    assert await _months_total(client, days, "pbjt") == D(bill["taxes"]["pbjt"])


@pytest.mark.parametrize("mode", ["plus_plus", "nett"])
async def test_the_month_adds_up_to_the_bills(pg_client, mode: str) -> None:
    ctx = await _setup(pg_client, mode)
    booking = await _booking(pg_client, ctx, 0, 2)
    await _charge(pg_client, booking, "laundry", 100000)
    await _charge(pg_client, booking, "transport", 50000)

    await _matches_bill(pg_client, ctx, booking)
    days = [ctx["today"], ctx["today"] + dt.timedelta(days=1)]
    assert await _months_total(pg_client, days, "room_nights") == 2
    assert await _months_total(pg_client, days, "untaxed") == D("50000")


async def test_a_rate_change_mid_stay_is_split_by_date(pg_client) -> None:
    ctx = await _setup(pg_client, "plus_plus")
    await _set_taxes(pg_client, ctx, "plus_plus", start=1, pbjt_pct="5")
    booking = await _booking(pg_client, ctx, 0, 2)

    await _matches_bill(pg_client, ctx, booking)


async def test_nights_count_in_the_month_they_are_stayed(pg_client) -> None:
    ctx = await _setup(pg_client, "plus_plus")
    month_end = (ctx["today"].replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(
        days=1
    )
    await make_booking(
        pg_client,
        ctx["room"],
        ctx["plan"],
        month_end.isoformat(),
        (month_end + dt.timedelta(days=2)).isoformat(),
    )

    this = await _summary(pg_client, _month(month_end))
    following = await _summary(pg_client, _month(month_end + dt.timedelta(days=1)))

    assert [d["date"] for d in this["days"]] == [month_end.isoformat()]
    assert (this["totals"]["room_nights"], following["totals"]["room_nights"]) == (1, 1)


async def test_channel_bookings_are_counted_apart(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client, "plus_plus")
    booking = await _booking(pg_client, ctx, 0, 1)
    await pg_session.execute(
        text("UPDATE reservation SET payment_collect_model = 'channel' WHERE id = :b"),
        {"b": booking["id"]},
    )
    await pg_session.commit()

    totals = (await _summary(pg_client, _month(ctx["today"])))["totals"]

    assert (totals["room_nights"], D(totals["service"]), D(totals["pbjt"])) == (0, 0, 0)
    assert totals["channel_nights"] == 1
    base, service, pbjt = (
        D(totals[k]) for k in ("channel_base", "channel_service", "channel_pbjt")
    )
    assert base + service + pbjt == D("500000")  # the channel's price, tax inside
    assert service > 0 and pbjt > 0


async def test_cancelled_bookings_and_unset_rates_count_nothing(pg_client) -> None:
    ctx = await _setup(pg_client, None)  # no tax rates confirmed yet
    unset = await _summary(pg_client, _month(ctx["today"]))
    await _set_taxes(pg_client, ctx, "plus_plus")
    booking = await _booking(pg_client, ctx, 0, 1)
    cancelled = await pg_client.post(
        f"/api/bookings/{booking['id']}/cancel", json={"reason": "Batal"}
    )

    after = await _summary(pg_client, _month(ctx["today"]))

    assert (unset["is_set"], unset["days"]) == (False, [])
    assert cancelled.status_code == 200, cancelled.text
    assert (after["is_set"], after["totals"]["room_nights"], after["bookings"]) == (True, 0, [])


async def test_the_month_is_a_draft_until_every_day_is_closed(pg_client) -> None:
    ctx = await _setup(pg_client, "plus_plus")

    summary = await _summary(pg_client, _month(ctx["today"]))

    assert (summary["draft"], summary["closed_days"]) == (True, 0)
    assert summary["days_in_month"] >= 28


async def test_the_files_are_safe_marked_and_recorded(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client, "plus_plus")
    await pg_session.execute(
        text("UPDATE property SET name = '=HYPERLINK(1)' WHERE id = :p"),
        {"p": ctx["workspace"]["property"]["id"]},
    )
    await pg_session.commit()
    booking = await _booking(pg_client, ctx, 0, 1)
    month = _month(ctx["today"])

    days = await pg_client.get(f"{TAX}/{month}/days.csv")
    bookings = await pg_client.get(f"{TAX}/{month}/bookings.csv")
    events = (
        (
            await pg_session.execute(
                text(
                    "SELECT payload FROM tenantauditentry "
                    "WHERE event_id = 'tax.exported' AND tenant_id = :t"
                ),
                {"t": ctx["workspace"]["tenant"]["id"]},
            )
        )
        .scalars()
        .all()
    )

    assert days.status_code == 200, days.text
    assert days.headers["content-disposition"] == f'attachment; filename="tax-{month}-days.csv"'
    assert days.text.startswith("﻿")
    rows = list(csv.reader(io.StringIO(days.text.lstrip("﻿"))))
    assert rows[1] == ["Property", "'=HYPERLINK(1)"]  # never runs as a formula
    assert rows[3][1].startswith("DRAFT")
    assert rows[-1][0] == "Total"
    assert booking["number"] in bookings.text and "Budi" not in bookings.text  # no guest names
    assert sorted(e["file"] for e in events) == ["bookings", "days"]


async def test_only_owners_and_managers_see_taxes(pg_client, other_client) -> None:
    await _setup(pg_client, "plus_plus")
    await _joined(pg_client, other_client, role="front_desk")

    refused = await other_client.get(f"{TAX}/2026-11")
    file = await other_client.get(f"{TAX}/2026-11/days.csv")

    assert (refused.status_code, file.status_code) == (403, 403)


async def test_another_workspace_and_bad_months(pg_client, other_client) -> None:
    ctx = await _setup(pg_client, "plus_plus")
    await _booking(pg_client, ctx, 0, 1)
    await start_workspace(other_client)

    theirs = await _summary(other_client, _month(ctx["today"]))
    bad = await pg_client.get(f"{TAX}/2026-13")
    old = await pg_client.get(f"{TAX}/1999-12")

    assert (theirs["totals"]["room_nights"], theirs["bookings"]) == (0, [])
    assert (bad.status_code, old.status_code) == (422, 422)
