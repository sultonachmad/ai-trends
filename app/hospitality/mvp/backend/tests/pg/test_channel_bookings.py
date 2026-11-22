"""Channel bookings inbound: applied, flagged, never duplicated, never rejected."""

import datetime as dt

import pytest
from sqlalchemy import text

from app.services.calendar_dates import property_today
from tests.pg.conftest import (
    connect_channel,
    make_rate_plan,
    make_room_type,
    push_now,
    start_workspace,
)

pytestmark = pytest.mark.integration

BOOKINGS = "/api/bookings"
ATTENTION = "/api/bookings/channel-attention"
AGENCY = "/api/simulator/channels/listings"


async def _live(client, *, units: int = 3, amount: int = 500000) -> dict:
    workspace = await start_workspace(client)
    room = await make_room_type(client, units=units, max_guests=2)
    plan = await make_rate_plan(client, [room], amount=amount)
    connection = await connect_channel(client)
    saved = await client.put(
        f"/api/channel-connections/{connection['id']}/mappings",
        json={
            "mappings": [
                {
                    "room_type_id": room["id"],
                    "rate_plan_id": plan["id"],
                    "external_room_id": "R1",
                    "external_rate_id": "P1",
                }
            ]
        },
    )
    assert saved.status_code == 200, saved.text
    live = await client.post(f"/api/channel-connections/{connection['id']}/go-live")
    assert live.status_code == 200, live.text
    return {
        "workspace": workspace,
        "room": room,
        "plan": plan,
        "connection": live.json(),
        "hotel": connection["external_property_id"],
    }


def _day(ctx: dict, offset: int) -> str:
    return (
        property_today(ctx["workspace"]["property"]["timezone"]) + dt.timedelta(days=offset)
    ).isoformat()


async def _agency_book(client, ctx, *, arrival, departure, amount=500000, **overrides):
    body = {
        "hotel_id": ctx["hotel"],
        "arrival": arrival,
        "departure": departure,
        "total_amount": amount,
        "guest_name": "Made Kanal",
        "guest_phone": "+6281234500999",
        **overrides,
    }
    response = await client.post(f"{AGENCY}/bookings", json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def pull_now(pg_session_factory, tenant_id):
    from app.services.channel_booking_pull import pull_tenant

    async with pg_session_factory() as session:
        from app.tenancy.session import bind_tenant

        await bind_tenant(session, tenant_id)
        return await pull_tenant(session, tenant_id)


async def _envelopes(session, tenant_id: str) -> list[tuple]:
    rows = await session.execute(
        text(
            "SELECT external_booking_id, external_version, event_kind, processing_status, "
            "attention_reason, reservation_id IS NOT NULL FROM channelbooking "
            "WHERE tenant_id = :t ORDER BY received_at"
        ),
        {"t": tenant_id},
    )
    return [tuple(row) for row in rows.all()]


# ---- a booking arrives on its own --------------------------------------------------------


async def test_a_new_channel_booking_lands(
    pg_client,
    pg_session,
    pg_session_factory,
) -> None:
    ctx = await _live(pg_client)
    tenant_id = ctx["workspace"]["tenant"]["id"]
    await push_now(pg_session_factory, tenant_id)

    made = await _agency_book(
        pg_client, ctx, arrival=_day(ctx, 3), departure=_day(ctx, 5), amount=1000000
    )
    assert await pull_now(pg_session_factory, tenant_id) == 1

    page = (await pg_client.get(BOOKINGS, params={"tab": "upcoming"})).json()
    [booking] = page["items"]
    assert booking["guest"]["name"] == "Made Kanal"
    assert booking["guest"]["phone"] == "+6281234500999"
    assert booking["source"]["code"] == "simulator"
    assert booking["source"]["is_direct"] is False
    assert booking["total_amount"] == "1000000.00"
    assert booking["channel_reference"] == made["external_booking_id"]
    assert booking["channel_attention"] is None
    detail = (await pg_client.get(f"{BOOKINGS}/{booking['id']}")).json()
    assert detail["source"]["name"] == "Simulated agency (test)"
    envelopes = await _envelopes(pg_session, tenant_id)
    assert envelopes == [(made["external_booking_id"], "1", "new", "applied", None, True)]


async def test_duplicate_and_stale_deliveries_are_ignored(
    pg_client, pg_session, pg_session_factory
) -> None:
    ctx = await _live(pg_client)
    tenant_id = ctx["workspace"]["tenant"]["id"]
    await _agency_book(pg_client, ctx, arrival=_day(ctx, 1), departure=_day(ctx, 2))
    assert await pull_now(pg_session_factory, tenant_id) == 1
    before = (await pg_client.get(BOOKINGS, params={"tab": "upcoming"})).json()

    # replay the same event through the handler: a healthy repeat changes nothing
    from sqlmodel import col, select

    from app.channels.provider import ChannelCall
    from app.channels.simulator import SimulatedChannel
    from app.models.tenant import ChannelConnection
    from app.services.channel_bookings import DuplicateEventError, handle_booking_event
    from app.services.channel_push import _context
    from app.tenancy.session import bind_tenant

    async with pg_session_factory() as session:
        await bind_tenant(session, tenant_id)
        connection = (
            await session.exec(
                select(ChannelConnection).where(col(ChannelConnection.tenant_id) == tenant_id)
            )
        ).first()
        events = await SimulatedChannel().fetch_booking_changes(
            ChannelCall(tenant_id=tenant_id, session=session),
            connection.external_property_id,
            None,
        )
        context = _context(tenant_id, session)
        with pytest.raises(DuplicateEventError):
            await handle_booking_event(session, context, connection, events[-1])

    after = (await pg_client.get(BOOKINGS, params={"tab": "upcoming"})).json()
    assert [b["id"] for b in after["items"]] == [b["id"] for b in before["items"]]
    assert len(await _envelopes(pg_session, tenant_id)) == 1


async def test_modify_and_cancel_move_the_booking(
    pg_client, pg_session, pg_session_factory
) -> None:
    ctx = await _live(pg_client)
    tenant_id = ctx["workspace"]["tenant"]["id"]
    made = await _agency_book(pg_client, ctx, arrival=_day(ctx, 2), departure=_day(ctx, 4))
    await pull_now(pg_session_factory, tenant_id)
    [booking] = (await pg_client.get(BOOKINGS, params={"tab": "upcoming"})).json()["items"]

    changed = await pg_client.post(
        f"{AGENCY}/bookings/change",
        json={
            "hotel_id": ctx["hotel"],
            "external_booking_id": made["external_booking_id"],
            "version": 2,
            "arrival": _day(ctx, 6),
            "departure": _day(ctx, 8),
            "total_amount": 1200000,
            "guest_name": "Made Kanal",
            "guest_phone": "+6281234500999",
        },
    )
    assert changed.status_code == 201, changed.text
    assert await pull_now(pg_session_factory, tenant_id) == 1

    moved = (await pg_client.get(f"{BOOKINGS}/{booking['id']}")).json()
    assert (moved["arrival"], moved["departure"], moved["total_amount"]) == (
        _day(ctx, 6),
        _day(ctx, 8),
        "1200000.00",
    )
    assert moved["number"] == booking["number"]

    cancelled = await pg_client.post(
        f"{AGENCY}/bookings/change",
        json={
            "hotel_id": ctx["hotel"],
            "external_booking_id": made["external_booking_id"],
            "version": 3,
            "kind": "cancel",
            "arrival": _day(ctx, 6),
            "departure": _day(ctx, 8),
            "total_amount": 1200000,
        },
    )
    assert cancelled.status_code == 201
    assert (await pull_now(pg_session_factory, tenant_id)) == 1
    gone = (await pg_client.get(f"{BOOKINGS}/{booking['id']}")).json()
    assert gone["status"] == "cancelled"
    assert gone["cancel_note"] == "Dibatalkan di kanal"


# ---- never rejected, always flagged ------------------------------------------------------


async def test_overbooking_is_taken_and_flagged(
    pg_client,
    pg_session,
    pg_session_factory,
) -> None:
    ctx = await _live(pg_client, units=1)
    tenant_id = ctx["workspace"]["tenant"]["id"]
    await push_now(pg_session_factory, tenant_id)
    # a direct booking takes the only unit
    direct = await pg_client.post(
        BOOKINGS,
        json={
            "arrival": _day(ctx, 2),
            "departure": _day(ctx, 4),
            "room_type_id": ctx["room"]["id"],
            "rate_plan_id": ctx["plan"]["id"],
            "guest_name": "Tamu Langsung",
        },
    )
    assert direct.status_code == 201

    await _agency_book(pg_client, ctx, arrival=_day(ctx, 2), departure=_day(ctx, 4))
    assert await pull_now(pg_session_factory, tenant_id) == 1

    items = (await pg_client.get(BOOKINGS, params={"tab": "upcoming"})).json()["items"]
    channel_booking = next(b for b in items if b["source"]["is_direct"] is False)
    assert channel_booking["overbooking_risk"] is True
    assert channel_booking["channel_attention"] == "overbooking_risk"
    attention = (await pg_client.get(ATTENTION)).json()
    assert [a["reason"] for a in attention] == ["overbooking_risk"]


async def test_an_unmapped_channel_room_is_stored_and_flagged(
    pg_client, pg_session, pg_session_factory
) -> None:
    ctx = await _live(pg_client)
    tenant_id = ctx["workspace"]["tenant"]["id"]
    await push_now(pg_session_factory, tenant_id)

    # R3 exists only on the agency (the extra room)
    made = await _agency_book(
        pg_client,
        ctx,
        arrival=_day(ctx, 1),
        departure=_day(ctx, 2),
        external_room_id="R3",
        external_rate_id="P2",
    )
    assert await pull_now(pg_session_factory, tenant_id) == 1

    items = (await pg_client.get(BOOKINGS, params={"tab": "upcoming"})).json()["items"]
    assert items == []  # no reservation was created
    attention = (await pg_client.get(ATTENTION)).json()
    assert len(attention) == 1
    assert attention[0]["reason"] == "unmapped_product"
    assert attention[0]["external_booking_id"] == made["external_booking_id"]
    assert attention[0]["reservation_id"] is None


async def test_a_price_far_from_our_truth_flags_a_warning(
    pg_client, pg_session, pg_session_factory
) -> None:
    ctx = await _live(pg_client, amount=500000)
    tenant_id = ctx["workspace"]["tenant"]["id"]
    await push_now(pg_session_factory, tenant_id)

    # one night at our truth 500000, sold on the channel for 700000 (40% off)
    await _agency_book(pg_client, ctx, arrival=_day(ctx, 1), departure=_day(ctx, 2), amount=700000)
    await pull_now(pg_session_factory, tenant_id)

    [booking] = (await pg_client.get(BOOKINGS, params={"tab": "upcoming"})).json()["items"]
    assert booking["channel_attention"] == "price_mismatch"
    assert booking["overbooking_risk"] is False


async def test_a_price_within_tolerance_is_not_flagged(
    pg_client, pg_session, pg_session_factory
) -> None:
    ctx = await _live(pg_client, amount=500000)
    tenant_id = ctx["workspace"]["tenant"]["id"]
    await push_now(pg_session_factory, tenant_id)

    await _agency_book(pg_client, ctx, arrival=_day(ctx, 1), departure=_day(ctx, 2), amount=505000)
    await pull_now(pg_session_factory, tenant_id)

    [booking] = (await pg_client.get(BOOKINGS, params={"tab": "upcoming"})).json()["items"]
    assert booking["channel_attention"] is None


# ---- the channel's own window shrinks ----------------------------------------------------


async def test_the_channel_availability_drops_after_its_booking(
    pg_client, pg_session, pg_session_factory
) -> None:
    ctx = await _live(pg_client, units=3)
    tenant_id = ctx["workspace"]["tenant"]["id"]
    await push_now(pg_session_factory, tenant_id)
    before = await _agency_window(pg_session, ctx)
    assert before[_day(ctx, 2)] == 3

    await _agency_book(pg_client, ctx, arrival=_day(ctx, 2), departure=_day(ctx, 4))
    await pull_now(pg_session_factory, tenant_id)
    await push_now(pg_session_factory, tenant_id)  # availability out (M4 triggers)

    after = await _agency_window(pg_session, ctx)
    assert after[_day(ctx, 2)] == 2
    assert after[_day(ctx, 3)] == 2
    assert after[_day(ctx, 4)] == 3  # departure night is not slept


async def _agency_window(session, ctx) -> dict:
    stored = (
        await session.execute(
            text("SELECT ari FROM channelsimulatorlisting WHERE hotel_id = :h"),
            {"h": ctx["hotel"]},
        )
    ).scalar_one()
    return {date: day["available"] for date, day in (stored or {}).get("R1", {}).items()}


# ---- commission, collect model, guests ---------------------------------------------------


async def test_commission_and_collect_model_follow_the_connection(
    pg_client, pg_session, pg_session_factory
) -> None:
    ctx = await _live(pg_client)
    tenant_id = ctx["workspace"]["tenant"]["id"]
    await pg_client.patch(
        f"/api/channel-connections/{ctx['connection']['id']}", json={"commission_percent": 15}
    )
    await push_now(pg_session_factory, tenant_id)

    await _agency_book(pg_client, ctx, arrival=_day(ctx, 1), departure=_day(ctx, 2), amount=400000)
    await pull_now(pg_session_factory, tenant_id)

    row = (
        await pg_session.execute(
            text(
                "SELECT commission_amount, payment_collect_model, channel_reference "
                "FROM reservation WHERE tenant_id = :t"
            ),
            {"t": tenant_id},
        )
    ).one()
    assert (str(row[0]), row[1], row[2] is not None) == ("60000.00", "channel", True)


async def test_the_guest_links_by_phone(
    pg_client,
    pg_session,
    pg_session_factory,
) -> None:
    from tests.pg.conftest import guest_says

    ctx = await _live(pg_client)
    tenant_id = ctx["workspace"]["tenant"]["id"]
    await guest_says(pg_client, "Halo", phone="+6281234500999", name="Wayan Sudah Kenal")

    await push_now(pg_session_factory, tenant_id)
    await _agency_book(pg_client, ctx, arrival=_day(ctx, 1), departure=_day(ctx, 2))
    await pull_now(pg_session_factory, tenant_id)

    [booking] = (await pg_client.get(BOOKINGS, params={"tab": "upcoming"})).json()["items"]
    assert booking["guest"]["phone"] == "+6281234500999"
    assert booking["guest"]["name"] == "Wayan Sudah Kenal"  # a known phone keeps the person


# ---- isolation and permissions ------------------------------------------------------------


async def test_another_property_never_sees_channel_bookings(
    pg_client, other_client, pg_session, pg_session_factory
) -> None:
    ctx = await _live(pg_client)
    await start_workspace(other_client)
    await _agency_book(pg_client, ctx, arrival=_day(ctx, 1), departure=_day(ctx, 2))
    await pull_now(pg_session_factory, ctx["workspace"]["tenant"]["id"])

    theirs = (await other_client.get(BOOKINGS, params={"tab": "upcoming"})).json()["items"]
    attention = (await other_client.get(ATTENTION)).json()
    assert theirs == []
    assert attention == []


async def test_versions_past_nine_still_order_and_dedup(
    pg_client, pg_session, pg_session_factory
) -> None:
    """Version ordering is numeric: v10 supersedes v9, and a replayed v10 is a repeat."""
    ctx = await _live(pg_client)
    tenant_id = ctx["workspace"]["tenant"]["id"]
    await _agency_book(pg_client, ctx, arrival=_day(ctx, 1), departure=_day(ctx, 2))
    await pull_now(pg_session_factory, tenant_id)
    ref = (
        await pg_session.execute(
            text("SELECT external_booking_id FROM channelbooking WHERE tenant_id = :t LIMIT 1"),
            {"t": tenant_id},
        )
    ).scalar_one()

    for version in range(2, 12):  # v2..v11
        changed = await pg_client.post(
            f"{AGENCY}/bookings/change",
            json={
                "hotel_id": ctx["hotel"],
                "external_booking_id": ref,
                "version": version,
                "arrival": _day(ctx, 1 + (version % 2)),
                "departure": _day(ctx, 3 + (version % 2)),
                "total_amount": 500000 + version,
                "guest_name": "Made Kanal",
                "guest_phone": "+6281234500999",
            },
        )
        assert changed.status_code == 201, changed.text
    assert await pull_now(pg_session_factory, tenant_id) == 10

    # a replay of v11 is a healthy repeat; nothing new is applied
    assert await pull_now(pg_session_factory, tenant_id) == 0
    latest = (
        await pg_session.execute(
            text(
                "SELECT external_version, processing_status FROM channelbooking "
                "WHERE tenant_id = :t AND external_booking_id = :ref "
                "ORDER BY received_at DESC LIMIT 1"
            ),
            {"t": tenant_id, "ref": ref},
        )
    ).one()
    assert tuple(latest) == ("11", "applied")


async def test_a_price_only_modify_on_a_full_night_is_not_flagged(
    pg_client, pg_session, pg_session_factory
) -> None:
    """The units the reservation itself holds are not a shortage (no false overbooking)."""
    ctx = await _live(pg_client, units=1)
    tenant_id = ctx["workspace"]["tenant"]["id"]
    made = await _agency_book(pg_client, ctx, arrival=_day(ctx, 2), departure=_day(ctx, 4), amount=1000000)
    await pull_now(pg_session_factory, tenant_id)
    [first] = (await pg_client.get(BOOKINGS, params={"tab": "upcoming"})).json()["items"]
    assert first["channel_attention"] is None  # the booking took the only unit, cleanly

    changed = await pg_client.post(
        f"{AGENCY}/bookings/change",
        json={
            "hotel_id": ctx["hotel"],
            "external_booking_id": made["external_booking_id"],
            "version": 2,
            "arrival": _day(ctx, 2),
            "departure": _day(ctx, 4),
            "total_amount": 1010000,
            "guest_name": "Made Kanal",
            "guest_phone": "+6281234500999",
        },
    )
    assert changed.status_code == 201
    await pull_now(pg_session_factory, tenant_id)

    [after] = (await pg_client.get(BOOKINGS, params={"tab": "upcoming"})).json()["items"]
    assert after["channel_attention"] is None  # its own units are not a shortage
    assert after["total_amount"] == "1010000.00"
    assert after["overbooking_risk"] is False


async def test_the_attention_list_and_agency_routes_need_permissions(
    pg_client, other_client, pg_session
) -> None:
    from tests.pg.conftest import add_staff_member

    ctx = await _live(pg_client)
    await add_staff_member(pg_session, other_client, ctx["workspace"], role=None)

    attention = await other_client.get(ATTENTION)
    agency = await other_client.post(
        f"{AGENCY}/bookings",
        json={
            "hotel_id": ctx["hotel"],
            "arrival": _day(ctx, 1),
            "departure": _day(ctx, 2),
            "total_amount": 1000,
        },
    )

    assert (attention.status_code, agency.status_code) == (403, 403)


async def test_an_unprocessable_booking_is_stamped_failed_and_shown(
    pg_client, pg_session, pg_session_factory
) -> None:
    """A booking we cannot apply is never silently pending: staff see it as failed."""
    from sqlalchemy import text as sql

    ctx = await _live(pg_client)
    tenant_id = ctx["workspace"]["tenant"]["id"]
    # place a stay outside the calendar horizon directly on the agency store
    from app.channels import simulator
    from app.channels.provider import ChannelCall
    from sqlmodel import col, select
    from app.models.tenant import ChannelConnection
    from app.services.channel_push import _context
    from app.tenancy.session import bind_tenant
    from app.services.channel_bookings import handle_booking_event

    event = simulator.make_booking_event(
        external_room_id="R1",
        external_rate_id="P1",
        arrival="2030-01-01",
        departure="2030-01-03",
        total_amount=500000,
    )
    async with pg_session_factory() as session:
        await bind_tenant(session, tenant_id)
        connection = (
            await session.exec(
                select(ChannelConnection).where(col(ChannelConnection.tenant_id) == tenant_id)
            )
        ).first()
        await handle_booking_event(session, _context(tenant_id, session), connection, event)

    status = (
        await pg_session.execute(
            sql(
                "SELECT processing_status, attention_reason FROM channelbooking WHERE tenant_id = :t"
            ),
            {"t": tenant_id},
        )
    ).one()
    assert status[0] == "failed"
    assert "processing_error" in status[1]
    attention = (await pg_client.get(ATTENTION)).json()
    assert [a["reason"] for a in attention] == [status[1]]


@pytest.mark.parametrize(
    "body",
    [
        {"arrival": "2030-01-05", "departure": "2030-01-05"},  # zero nights
        {"arrival": "2030-01-05", "departure": "2030-01-04"},  # reversed
        {"arrival": "2030-01-01", "departure": "2030-06-01"},  # too long
        {"payment_collect": "hotel"},  # not a collect model
    ],
)
async def test_the_agency_route_validates_its_bookings(pg_client, ctx_stub, body) -> None:
    payload = {
        "hotel_id": "SIM-ANY",
        "arrival": "2030-01-01",
        "departure": "2030-01-03",
        "total_amount": 500000,
        **body,
    }
    response = await pg_client.post(f"{AGENCY}/bookings", json=payload)
    assert response.status_code == 422


@pytest.fixture
async def ctx_stub(pg_client):
    await start_workspace(pg_client)
    return None
