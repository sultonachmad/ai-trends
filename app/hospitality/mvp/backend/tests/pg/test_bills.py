"""The bill: charges, discounts, voids, corrections and desk payments."""

import asyncio
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

pytestmark = pytest.mark.integration

BILLS = "/api/bills"


async def _setup(client) -> dict:
    workspace = await start_workspace(client)
    room = await make_room_type(client, units=3, max_guests=2)
    plan = await make_rate_plan(client, [room], amount=500000)
    today = property_today(workspace["property"]["timezone"])
    booking = await make_booking(
        client,
        room,
        plan,
        today.isoformat(),
        (today + dt.timedelta(days=2)).isoformat(),
    )
    return {"workspace": workspace, "booking": booking, "today": today, "room": room, "plan": plan}


def _url(ctx: dict) -> str:
    return f"{BILLS}/{ctx['booking']['id']}"


async def _charge(client, ctx, **over):
    body = {
        "category": "food_drinks",
        "description": "Nasi goreng",
        "quantity": 2,
        "unit_price": 35000,
        **over,
    }
    return await client.post(f"{_url(ctx)}/charges", json=body)


def _code(response) -> str:
    return response.json()["detail"]["code"]


async def test_the_bill_lists_room_nights_extras_and_payments(pg_client) -> None:
    ctx = await _setup(pg_client)
    await _charge(pg_client, ctx)
    await pg_client.post(
        f"{_url(ctx)}/payments",
        json={"amount": "500000", "method": "qris", "received_on": ctx["today"].isoformat()},
    )

    bill = (await pg_client.get(_url(ctx))).json()

    assert [Decimal(n["amount"]) for n in bill["room_nights"]] == [500000, 500000]
    assert [(line["category"], Decimal(line["amount"])) for line in bill["lines"]] == [
        ("food_drinks", 70000)
    ]
    assert Decimal(bill["paid"]) == 500000
    assert Decimal(bill["balance"]) == 570000
    assert bill["closed"] is False


@pytest.mark.parametrize(
    "bad",
    [
        {"quantity": 0},
        {"unit_price": 0},
        {"description": ""},
        {"category": "spa"},
        {"quantity": 1000},
    ],
)
async def test_bad_charges_are_refused(pg_client, bad) -> None:
    ctx = await _setup(pg_client)
    assert (await _charge(pg_client, ctx, **bad)).status_code == 422


async def test_a_discount_needs_a_reason_and_cannot_go_below_zero(pg_client) -> None:
    ctx = await _setup(pg_client)
    url = f"{_url(ctx)}/discounts"

    no_reason = await pg_client.post(url, json={"amount": "100000", "reason": ""})
    too_much = await pg_client.post(url, json={"amount": "1000001", "reason": "Langganan"})
    given = await pg_client.post(url, json={"amount": "100000", "reason": "Langganan"})

    assert no_reason.status_code == 422
    assert (too_much.status_code, _code(too_much)) == (422, "discount_too_large")
    assert given.status_code == 200, given.text
    assert Decimal(given.json()["balance"]) == 900000


async def test_a_line_is_voided_once_and_only_the_same_day(pg_client, monkeypatch) -> None:
    ctx = await _setup(pg_client)
    first = (await _charge(pg_client, ctx)).json()["lines"][0]
    second = (await _charge(pg_client, ctx, description="Teh")).json()["lines"][1]

    async def void(line):
        return await pg_client.post(
            f"{_url(ctx)}/lines/{line['id']}/void", json={"reason": "Salah input"}
        )

    voided = await void(first)
    again = await void(first)
    tomorrow = ctx["today"] + dt.timedelta(days=1)
    monkeypatch.setattr("app.services.calendar_dates.property_today", lambda *_a, **_k: tomorrow)
    late = await void(second)

    assert voided.status_code == 200, voided.text
    assert [line["voided"] for line in voided.json()["lines"]] == [True, False]
    assert Decimal(voided.json()["balance"]) == 1070000
    assert (again.status_code, _code(again)) == (409, "already_voided")
    assert (late.status_code, _code(late)) == (409, "void_too_late")


async def test_a_correction_carries_a_reason(pg_client) -> None:
    ctx = await _setup(pg_client)
    await _charge(pg_client, ctx)

    corrected = await pg_client.post(
        f"{_url(ctx)}/corrections", json={"amount": "-20000", "reason": "Harga menu salah"}
    )

    assert corrected.status_code == 200, corrected.text
    line = corrected.json()["lines"][-1]
    assert (line["category"], line["description"], Decimal(line["amount"])) == (
        "correction",
        "Harga menu salah",
        -20000,
    )


async def test_nothing_is_ever_deleted(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    line = (await _charge(pg_client, ctx)).json()["lines"][0]
    await pg_client.post(f"{_url(ctx)}/lines/{line['id']}/void", json={"reason": "Salah"})

    count = await pg_session.execute(
        text(
            "SELECT count(*) FROM foliotransaction WHERE folio_id IN "
            "(SELECT id FROM folio WHERE reservation_id = :b)"
        ),
        {"b": ctx["booking"]["id"]},
    )
    assert count.scalar_one() == 2


@pytest.mark.parametrize("status", ["cancelled", "no_show", "checked_out"])
async def test_a_closed_bill_takes_no_charges(pg_client, pg_session, status) -> None:
    ctx = await _setup(pg_client)
    for table, column in (("reservation", "id"), ("reservationunit", "reservation_id")):
        await pg_session.execute(
            text(f"UPDATE {table} SET status = :s WHERE {column} = :b"),  # noqa: S608
            {"s": status, "b": ctx["booking"]["id"]},
        )
    await pg_session.commit()

    response = await _charge(pg_client, ctx)

    assert (response.status_code, _code(response)) == (409, "bill_closed")
    assert (await pg_client.get(_url(ctx))).json()["closed"] is True


async def test_two_charges_at_once_both_count(pg_client) -> None:
    ctx = await _setup(pg_client)

    answers = await asyncio.gather(_charge(pg_client, ctx), _charge(pg_client, ctx))

    assert [answer.status_code for answer in answers] == [200, 200]
    assert len((await pg_client.get(_url(ctx))).json()["lines"]) == 2


async def test_bills_need_permission(pg_client, other_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await add_staff_member(pg_session, other_client, ctx["workspace"], role=None)

    assert (await other_client.get(_url(ctx))).status_code == 403
    assert (await _charge(other_client, ctx)).status_code == 403


async def test_tenants_are_separate(pg_client, other_client) -> None:
    ctx = await _setup(pg_client)
    await start_workspace(other_client)

    assert (await other_client.get(_url(ctx))).status_code == 404
    assert (await _charge(other_client, ctx)).status_code == 404


# ---- review fixes ------------------------------------------------------------------------


async def _desk_clerk(pg_client, other_client, pg_session, ctx) -> None:
    from tests.pg.test_feature_access import _give_role

    staff = await add_staff_member(pg_session, other_client, ctx["workspace"], role=None)
    await _give_role(pg_session, staff["user_id"], "cashier", ["bills:view", "bills:edit"])
    await pg_session.commit()


async def test_discounts_and_corrections_need_booking_edit(
    pg_client, other_client, pg_session
) -> None:
    ctx = await _setup(pg_client)
    await _desk_clerk(pg_client, other_client, pg_session, ctx)

    discount = await other_client.post(
        f"{_url(ctx)}/discounts", json={"amount": "1000000", "reason": "Gratis saja"}
    )
    correction = await other_client.post(
        f"{_url(ctx)}/corrections", json={"amount": "-1000000", "reason": "Hapus saja"}
    )
    charge = await _charge(other_client, ctx)

    assert (discount.status_code, _code(discount)) == (403, "price_permission")
    assert (correction.status_code, _code(correction)) == (403, "price_permission")
    assert charge.status_code == 200, charge.text


async def test_a_correction_has_a_sane_ceiling(pg_client) -> None:
    ctx = await _setup(pg_client)

    response = await pg_client.post(
        f"{_url(ctx)}/corrections", json={"amount": "999999999999", "reason": "Salah ketik"}
    )

    assert response.status_code == 422


async def test_money_changes_are_in_the_history_with_reason_and_owed(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await pg_client.post(f"{_url(ctx)}/discounts", json={"amount": "100000", "reason": "Langganan"})

    row = await pg_session.execute(
        text(
            "SELECT payload FROM tenantauditentry WHERE event_id = 'bill.discount_given' "
            "AND entity_id = :b"
        ),
        {"b": ctx["booking"]["id"]},
    )
    payload = row.scalar_one()
    assert (payload["reason"], payload["owed_before"], payload["owed_after"]) == (
        "Langganan",
        "1000000.00",
        "900000.00",
    )


async def test_one_guest_bill_per_booking_is_enforced_by_the_database(
    pg_client, pg_session
) -> None:
    ctx = await _setup(pg_client)
    await _charge(pg_client, ctx)

    with pytest.raises(Exception, match="ux_folio_guest_reservation"):
        await pg_session.execute(
            text(
                "INSERT INTO folio (id, tenant_id, property_id, kind, reservation_id, window_no, "
                "status, currency, balance, version) SELECT gen_random_uuid(), tenant_id, "
                "property_id, 'guest', reservation_id, 1, 'open', 'IDR', 0, 1 FROM folio "
                "WHERE reservation_id = :b"
            ),
            {"b": ctx["booking"]["id"]},
        )
    await pg_session.rollback()
