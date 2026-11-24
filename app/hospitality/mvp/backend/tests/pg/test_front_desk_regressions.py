"""Stays that have started: existing booking, money and channel flows keep them right."""

import datetime as dt
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlmodel import select

from app.models.tenant import Payment
from app.services.calendar_dates import property_today
from app.services.gateway_events import PAID_EVENT, GatewayEvent, handle_gateway_event
from app.tenancy.session import bind_tenant
from tests.pg.conftest import (
    make_booking,
    make_rate_plan,
    make_room_type,
    start_workspace,
)
from tests.pg.test_channel_bookings import _agency_book, _day, _envelopes, _live, pull_now

pytestmark = pytest.mark.integration

BOOKINGS = "/api/bookings"


async def _setup(client, units: int = 3) -> dict:
    workspace = await start_workspace(client)
    room = await make_room_type(client, units=units, max_guests=2)
    plan = await make_rate_plan(client, [room], amount=500000)
    today = property_today(workspace["property"]["timezone"])
    return {"workspace": workspace, "room": room, "plan": plan, "today": today}


def _on(ctx: dict, offset: int) -> str:
    return (ctx["today"] + dt.timedelta(days=offset)).isoformat()


async def _mark(session, booking_id: str, status: str) -> None:
    for table, column in (("reservation", "id"), ("reservationunit", "reservation_id")):
        await session.execute(
            text(f"UPDATE {table} SET status = :s WHERE {column} = :b"),  # noqa: S608
            {"s": status, "b": booking_id},
        )
    await session.commit()


async def _assign(session, booking_id: str, unit_id: str) -> None:
    await session.execute(
        text("UPDATE reservationunit SET unit_id = :u WHERE reservation_id = :b"),
        {"u": unit_id, "b": booking_id},
    )
    await session.commit()


async def _units_of(session, booking_id: str) -> list[str | None]:
    rows = await session.execute(
        text("SELECT unit_id FROM reservationunit WHERE reservation_id = :b"), {"b": booking_id}
    )
    return [str(row[0]) if row[0] else None for row in rows.all()]


async def test_editing_a_booking_keeps_its_room(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    booking = await make_booking(pg_client, ctx["room"], ctx["plan"], _on(ctx, 3), _on(ctx, 5))
    unit = ctx["room"]["units"][1]["id"]
    await _assign(pg_session, booking["id"], unit)

    changed = await pg_client.patch(
        f"{BOOKINGS}/{booking['id']}", json={"arrival": _on(ctx, 4), "departure": _on(ctx, 7)}
    )

    assert changed.status_code == 200, changed.text
    assert await _units_of(pg_session, booking["id"]) == [unit]


async def test_an_edit_that_clashes_drops_only_the_room(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    first = await make_booking(pg_client, ctx["room"], ctx["plan"], _on(ctx, 3), _on(ctx, 5))
    other = await make_booking(pg_client, ctx["room"], ctx["plan"], _on(ctx, 5), _on(ctx, 7))
    unit = ctx["room"]["units"][0]["id"]
    await _assign(pg_session, first["id"], unit)
    await _assign(pg_session, other["id"], unit)

    changed = await pg_client.patch(f"{BOOKINGS}/{first['id']}", json={"departure": _on(ctx, 6)})

    assert changed.status_code == 200, changed.text
    assert await _units_of(pg_session, first["id"]) == [None]
    assert await _units_of(pg_session, other["id"]) == [unit]


@pytest.mark.parametrize(
    ("status", "counted"), [("in_house", 1), ("checked_out", 1), ("no_show", 0)]
)
async def test_report_follows_the_stay(pg_client, pg_session, status, counted) -> None:
    ctx = await _setup(pg_client)
    booking = await make_booking(pg_client, ctx["room"], ctx["plan"], _on(ctx, 1), _on(ctx, 3))
    await _mark(pg_session, booking["id"], status)

    report = await pg_client.get(
        "/api/reports/channels", params={"from": _on(ctx, 0), "to": _on(ctx, 10)}
    )

    assert report.status_code == 200, report.text
    assert report.json()["total"]["bookings"] == counted
    assert report.json()["total"]["cancelled"] == 0


async def test_an_extra_payment_on_an_in_house_stay_is_flagged(
    pg_client, guest, pg_session, pg_session_factory
) -> None:
    ctx = await _setup(pg_client)
    slug = f"inhouse-{uuid.uuid4().hex[:8]}"
    await pg_client.put(
        "/api/booking-page",
        json={"slug": slug, "is_published": True, "sold_plan_ids": [ctx["plan"]["id"]]},
    )
    made = await guest.post(
        f"/api/book/{slug}/checkout",
        json={
            "idempotency_key": uuid.uuid4().hex,
            "arrival": _on(ctx, 10),
            "departure": _on(ctx, 11),
            "room_type_id": ctx["room"]["id"],
            "rate_plan_id": ctx["plan"]["id"],
            "adults": 1,
            "guest_name": "Tamu Inap",
            "guest_phone": "+6281234567055",
            "pay_choice": "full",
            "expected_total": "500000",
            "accepted_terms": True,
        },
    )
    assert made.status_code == 201, made.text
    token = made.json()["pay_url"].rsplit("/", 1)[1]
    await guest.post(f"/api/pay/{token}/payments", json={"method": "qris"})
    await guest.post(
        f"/api/pay/{token}/payments", json={"method": "virtual_account", "bank": "BCA"}
    )
    await guest.post(f"/api/simulator/payments/{token}/pay")
    [booking] = (await pg_client.get(BOOKINGS, params={"tab": "upcoming"})).json()["items"]
    await _mark(pg_session, booking["id"], "in_house")

    tenant_id = uuid.UUID(ctx["workspace"]["tenant"]["id"])
    async with pg_session_factory() as own:
        await bind_tenant(own, tenant_id)
        extra = (
            await own.exec(
                select(Payment).where(Payment.tenant_id == tenant_id, Payment.status != "captured")
            )
        ).first()
        event = GatewayEvent(
            gateway_event_id=f"extra-{uuid.uuid4().hex}",
            event_type=PAID_EVENT,
            gateway_reference=extra.gateway_reference,
            amount=extra.amount,
            signature_valid=True,
        )
        await handle_gateway_event(own, tenant_id, extra.gateway_account_id, event)

    detail = (await pg_client.get(f"{BOOKINGS}/{booking['id']}")).json()
    assert detail["refund_due"] is True
    assert Decimal(detail["paid_amount"]) == 500000


@pytest.mark.parametrize("kind", ["cancel", "modify"])
async def test_a_channel_change_to_a_started_stay_reaches_staff(
    pg_client, pg_session, pg_session_factory, kind
) -> None:
    ctx = await _live(pg_client)
    tenant_id = ctx["workspace"]["tenant"]["id"]
    made = await _agency_book(pg_client, ctx, arrival=_day(ctx, 2), departure=_day(ctx, 4))
    await pull_now(pg_session_factory, tenant_id)
    [booking] = (await pg_client.get(BOOKINGS, params={"tab": "upcoming"})).json()["items"]
    await _mark(pg_session, booking["id"], "in_house")

    body = {
        "hotel_id": ctx["hotel"],
        "external_booking_id": made["external_booking_id"],
        "version": 2,
        "arrival": _day(ctx, 2),
        "departure": _day(ctx, 5),
        "total_amount": 750000,
        **({"kind": "cancel"} if kind == "cancel" else {}),
    }
    assert (
        await pg_client.post("/api/simulator/channels/listings/bookings/change", json=body)
    ).status_code == 201
    await pull_now(pg_session_factory, tenant_id)

    latest = (await _envelopes(pg_session, tenant_id))[-1]
    assert (latest[3], latest[4]) == ("needs_attention", "stay_started")
    detail = (await pg_client.get(f"{BOOKINGS}/{booking['id']}")).json()
    assert (detail["status"], detail["departure"]) == ("in_house", _day(ctx, 4))


@pytest.mark.parametrize("status", ["in_house", "checked_out", "no_show"])
async def test_a_started_stay_cannot_be_cancelled(pg_client, pg_session, status) -> None:
    ctx = await _setup(pg_client)
    booking = await make_booking(pg_client, ctx["room"], ctx["plan"], _on(ctx, 0), _on(ctx, 2))
    await _mark(pg_session, booking["id"], status)

    response = await pg_client.post(f"{BOOKINGS}/{booking['id']}/cancel", json={})

    assert response.status_code == 409
    assert (await pg_client.get(f"{BOOKINGS}/{booking['id']}")).json()["status"] == status


@pytest.mark.parametrize("status", ["checked_out", "no_show"])
async def test_a_finished_stay_cannot_be_edited(pg_client, pg_session, status) -> None:
    ctx = await _setup(pg_client)
    booking = await make_booking(pg_client, ctx["room"], ctx["plan"], _on(ctx, 0), _on(ctx, 2))
    await _mark(pg_session, booking["id"], status)

    response = await pg_client.patch(f"{BOOKINGS}/{booking['id']}", json={"departure": _on(ctx, 3)})

    assert response.status_code == 409


@pytest.mark.parametrize(
    "change", [{"room_type_id": "other"}, {"units": 2}, {"total_amount": "1"}, {"arrival": "next"}]
)
async def test_after_check_in_only_stay_end_guests_and_notes_change(
    pg_client, pg_session, change
) -> None:
    ctx = await _setup(pg_client)
    booking = await make_booking(pg_client, ctx["room"], ctx["plan"], _on(ctx, 0), _on(ctx, 2))
    await _mark(pg_session, booking["id"], "in_house")
    if "room_type_id" in change:
        change = {"room_type_id": (await make_room_type(pg_client, name="Suite"))["id"]}
    if "arrival" in change:
        change = {"arrival": _on(ctx, 1)}

    response = await pg_client.patch(f"{BOOKINGS}/{booking['id']}", json=change)

    assert response.status_code == 409, response.text


async def test_a_room_with_a_guest_is_not_retired(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client, units=2)
    booking = await make_booking(pg_client, ctx["room"], ctx["plan"], _on(ctx, 3), _on(ctx, 5))
    busy = ctx["room"]["units"][1]["id"]
    await _assign(pg_session, booking["id"], busy)

    reduced = await pg_client.patch(f"/api/room-types/{ctx['room']['id']}", json={"units": 1})

    assert reduced.status_code == 200, reduced.text
    assert [unit["id"] for unit in reduced.json()["units"]] == [busy]


async def test_reducing_below_rooms_in_use_is_refused(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client, units=2)
    for index, offset in enumerate((3, 3)):
        booking = await make_booking(
            pg_client, ctx["room"], ctx["plan"], _on(ctx, offset), _on(ctx, offset + 2)
        )
        await _assign(pg_session, booking["id"], ctx["room"]["units"][index]["id"])

    reduced = await pg_client.patch(f"/api/room-types/{ctx['room']['id']}", json={"units": 1})

    assert reduced.status_code == 409


@pytest.mark.parametrize(
    ("status", "tab"), [("in_house", "staying"), ("checked_out", "past"), ("no_show", "past")]
)
async def test_true_status_and_tab(pg_client, pg_session, status, tab) -> None:
    ctx = await _setup(pg_client)
    booking = await make_booking(pg_client, ctx["room"], ctx["plan"], _on(ctx, 0), _on(ctx, 2))
    await _mark(pg_session, booking["id"], status)

    items = (await pg_client.get(BOOKINGS, params={"tab": tab})).json()["items"]

    assert [(item["id"], item["status"]) for item in items] == [(booking["id"], status)]
