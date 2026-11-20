"""Money staff received for a booking: paid amount, balance and payment state."""

import datetime as dt

import pytest
from sqlalchemy import text

from app.services.calendar_dates import property_today
from tests.pg.conftest import make_booking, make_rate_plan, make_room_type, start_workspace

pytestmark = pytest.mark.integration

BOOKINGS = "/api/bookings"
MISSING = "00000000-0000-0000-0000-000000000000"


async def _booking(client, total: int = 1000000) -> tuple[dict, dt.date]:
    workspace = await start_workspace(client)
    room = await make_room_type(client)
    plan = await make_rate_plan(client, [room], amount=total)
    today = property_today(workspace["property"]["timezone"])
    booking = await make_booking(
        client,
        room,
        plan,
        (today + dt.timedelta(days=3)).isoformat(),
        (today + dt.timedelta(days=4)).isoformat(),
    )
    return booking, today


async def _pay(client, booking: dict, amount: int, today: dt.date, **overrides):
    body = {"amount": amount, "method": "cash", "received_on": today.isoformat(), **overrides}
    return await client.post(f"{BOOKINGS}/{booking['id']}/payments", json=body)


def _money(booking: dict) -> tuple[str, str, str]:
    return booking["paid_amount"], booking["balance_due"], booking["payment_state"]


async def test_a_deposit_then_the_rest(pg_client) -> None:
    booking, today = await _booking(pg_client, total=1000000)

    deposit = await _pay(
        pg_client, booking, 500000, today, method="bank_transfer", note="DP via BCA"
    )
    rest = await _pay(pg_client, booking, 500000, today - dt.timedelta(days=0))

    assert deposit.status_code == 201, deposit.text
    assert _money(deposit.json()) == ("500000.00", "500000.00", "partly_paid")
    [first] = deposit.json()["payments"]
    assert (first["amount"], first["method"], first["note"]) == (
        "500000.00",
        "bank_transfer",
        "DP via BCA",
    )
    assert first["received_on"] == today.isoformat()
    assert _money(rest.json()) == ("1000000.00", "0.00", "paid")
    assert len(rest.json()["payments"]) == 2


async def test_overpayment_is_shown_not_refused(pg_client) -> None:
    booking, today = await _booking(pg_client, total=1000000)

    response = await _pay(pg_client, booking, 1200000, today)

    assert response.status_code == 201
    assert _money(response.json()) == ("1200000.00", "-200000.00", "overpaid")


async def test_a_wrong_entry_can_be_removed_and_the_record_is_kept(pg_client, pg_session) -> None:
    booking, today = await _booking(pg_client, total=1000000)
    paid = (await _pay(pg_client, booking, 300000, today)).json()
    payment_id = paid["payments"][0]["id"]

    removed = await pg_client.delete(f"{BOOKINGS}/{booking['id']}/payments/{payment_id}")
    again = await pg_client.delete(f"{BOOKINGS}/{booking['id']}/payments/{payment_id}")

    assert removed.status_code == 200
    assert _money(removed.json()) == ("0.00", "1000000.00", "unpaid")
    assert removed.json()["payments"] == []
    assert again.status_code == 404
    kept = (
        await pg_session.execute(
            text("SELECT status, failure_reason FROM payment WHERE id = :p"), {"p": payment_id}
        )
    ).one()
    assert tuple(kept) == ("cancelled", "entered_by_mistake")


async def test_balance_follows_a_change_of_price(pg_client) -> None:
    booking, today = await _booking(pg_client, total=1000000)
    await _pay(pg_client, booking, 400000, today)

    changed = (
        await pg_client.patch(f"{BOOKINGS}/{booking['id']}", json={"total_amount": 800000})
    ).json()

    assert _money(changed) == ("400000.00", "400000.00", "partly_paid")


async def test_a_cancelled_booking_keeps_its_payments_and_can_take_a_late_one(pg_client) -> None:
    booking, today = await _booking(pg_client)
    await _pay(pg_client, booking, 250000, today)

    cancelled = (await pg_client.post(f"{BOOKINGS}/{booking['id']}/cancel", json={})).json()
    late = await _pay(pg_client, booking, 50000, today)

    assert _money(cancelled)[0] == "250000.00"
    assert len(cancelled["payments"]) == 1
    assert late.status_code == 201
    assert late.json()["paid_amount"] == "300000.00"


async def test_the_list_shows_the_payment_state(pg_client) -> None:
    booking, today = await _booking(pg_client, total=1000000)
    await _pay(pg_client, booking, 1000000, today)

    [listed] = (await pg_client.get(BOOKINGS, params={"tab": "upcoming"})).json()["items"]

    assert (listed["payment_state"], listed["balance_due"]) == ("paid", "0.00")


@pytest.mark.parametrize(
    "change",
    [
        {"amount": 0},
        {"amount": -5},
        {"amount": "1000.5"},
        {"method": "qris"},
        {"method": "bitcoin"},
        {"received_on": "TOMORROW"},
        {"received_on": "TOO_OLD"},
        {"received_on": "not-a-date"},
        {"note": "x" * 201},
        {"status": "captured"},
    ],
)
async def test_validation(pg_client, change) -> None:
    booking, today = await _booking(pg_client)
    special = {
        "TOMORROW": (today + dt.timedelta(days=1)).isoformat(),
        "TOO_OLD": (today - dt.timedelta(days=400)).isoformat(),
    }
    change = {key: special.get(value, value) for key, value in change.items()}

    response = await _pay(pg_client, booking, change.pop("amount", 100000), today, **change)

    assert response.status_code == 422
    assert (await pg_client.get(f"{BOOKINGS}/{booking['id']}")).json()["paid_amount"] == "0.00"


async def test_unknown_booking_or_payment_is_404(pg_client) -> None:
    booking, today = await _booking(pg_client)

    no_booking = await pg_client.post(
        f"{BOOKINGS}/{MISSING}/payments",
        json={"amount": 1000, "method": "cash", "received_on": today.isoformat()},
    )
    no_payment = await pg_client.delete(f"{BOOKINGS}/{booking['id']}/payments/{MISSING}")

    assert (no_booking.status_code, no_payment.status_code) == (404, 404)


async def test_payment_entries_per_booking_are_limited(pg_client, monkeypatch) -> None:
    booking, today = await _booking(pg_client)
    monkeypatch.setattr("app.services.booking_payments.MAX_PAYMENTS_PER_BOOKING", 2)
    await _pay(pg_client, booking, 1000, today)
    second = await _pay(pg_client, booking, 1000, today)

    third = await _pay(pg_client, booking, 1000, today)
    await pg_client.delete(
        f"{BOOKINGS}/{booking['id']}/payments/{second.json()['payments'][0]['id']}"
    )
    after_removal = await _pay(pg_client, booking, 1000, today)

    assert (third.status_code, after_removal.status_code) == (409, 201)


async def test_a_payment_amount_has_a_ceiling(pg_client) -> None:
    booking, today = await _booking(pg_client)

    assert (await _pay(pg_client, booking, 10**12, today)).status_code == 422
    assert (await _pay(pg_client, booking, 10**12 - 1, today)).status_code == 201
