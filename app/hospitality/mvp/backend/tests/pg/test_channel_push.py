"""Updates out to channels: what gets queued, what gets pushed, and how failures behave."""

import datetime as dt

import pytest
from sqlalchemy import text

from app.services.calendar_dates import property_today
from tests.pg.conftest import (
    connect_channel,
    make_booking,
    make_rate_plan,
    make_room_type,
    push_now,
    start_workspace,
)

pytestmark = pytest.mark.integration

CONNECTIONS = "/api/channel-connections"


async def _live_connection(client, *, units: int = 2, amount: int = 500000) -> dict:
    """A workspace with a room on a plan, connected to the simulated agency and live."""
    workspace = await start_workspace(client)
    room = await make_room_type(client, units=units, max_guests=2)
    plan = await make_rate_plan(client, [room], amount=amount)
    connection = await connect_channel(client)
    saved = await client.put(
        f"{CONNECTIONS}/{connection['id']}/mappings",
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
    live = await client.post(f"{CONNECTIONS}/{connection['id']}/go-live")
    assert live.status_code == 200, live.text
    detail = live.json()
    return {
        "workspace": workspace,
        "room": room,
        "plan": plan,
        "connection": detail,
    }


def _day(ctx: dict, offset: int) -> str:
    return (
        property_today(ctx["workspace"]["property"]["timezone"]) + dt.timedelta(days=offset)
    ).isoformat()


async def _queue_rows(session, tenant_id: str) -> list[tuple[str, str]]:
    rows = await session.execute(
        text(
            "SELECT unit_type_id::text, stay_date::text FROM channelariupdate "
            "WHERE tenant_id = :t ORDER BY stay_date"
        ),
        {"t": tenant_id},
    )
    return [tuple(row) for row in rows.all()]


async def _ari(session, hotel_id: str, room: str = "R1") -> dict:
    stored = (
        await session.execute(
            text("SELECT ari FROM channelsimulatorlisting WHERE hotel_id = :h"), {"h": hotel_id}
        )
    ).scalar_one()
    return {date: day for date, day in (stored or {}).get(room, {}).items()}


async def _messages(session, tenant_id: str, connection_id: str) -> list[tuple[str, int]]:
    rows = await session.execute(
        text(
            "SELECT status, attempts FROM channelmessage WHERE tenant_id = :t "
            "AND channel_connection_id = :c ORDER BY created_at"
        ),
        {"t": tenant_id, "c": connection_id},
    )
    return [tuple(row) for row in rows.all()]


# ---- what gets queued --------------------------------------------------------------------


async def test_go_live_queues_the_whole_window_and_the_sender_pushes_it(
    pg_client, pg_session, pg_session_factory
) -> None:
    ctx = await _live_connection(pg_client)
    tenant_id = ctx["workspace"]["tenant"]["id"]

    rows = await _queue_rows(pg_session, tenant_id)
    pushed = await push_now(pg_session_factory, tenant_id)

    assert len(rows) == 366  # the whole selling window
    assert pushed >= 1
    assert await _queue_rows(pg_session, tenant_id) == []  # acknowledged: queue empty
    ari = await _ari(pg_session, ctx["connection"]["external_property_id"])
    assert len(ari) == 366
    assert ari[_day(ctx, 0)]["available"] == 2
    assert ari[_day(ctx, 0)]["prices"] == {"P1": 500000}
    detail = (await pg_client.get(f"{CONNECTIONS}/{ctx['connection']['id']}")).json()
    assert detail["push_health"]["pending_updates"] == 0
    assert detail["push_health"]["last_success_at"] is not None
    assert detail["push_health"]["at_risk"] is False
    assert [m["status"] for m in detail["messages"][:1]] == ["acked"]


async def test_a_calendar_change_queues_only_its_dates(
    pg_client, pg_session, pg_session_factory
) -> None:
    ctx = await _live_connection(pg_client)
    tenant_id = ctx["workspace"]["tenant"]["id"]
    await push_now(pg_session_factory, tenant_id)

    changed = await pg_client.post(
        "/api/calendar/changes",
        json={
            "start": _day(ctx, 3),
            "end": _day(ctx, 4),
            "room_type_ids": [ctx["room"]["id"]],
            "change": {"kind": "set_price", "rate_plan_id": ctx["plan"]["id"], "amount": 700000},
        },
    )
    assert changed.status_code == 200
    rows = await _queue_rows(pg_session, tenant_id)
    await push_now(pg_session_factory, tenant_id)

    assert [date for _room, date in rows] == [_day(ctx, 3), _day(ctx, 4)]
    ari = await _ari(pg_session, ctx["connection"]["external_property_id"])
    assert ari[_day(ctx, 3)]["prices"] == {"P1": 700000}
    assert ari[_day(ctx, 2)]["prices"] == {"P1": 500000}  # untouched dates are not re-sent


async def test_repeated_changes_collapse_into_one_pending_set(
    pg_client, pg_session, pg_session_factory
) -> None:
    ctx = await _live_connection(pg_client)
    tenant_id = ctx["workspace"]["tenant"]["id"]
    await push_now(pg_session_factory, tenant_id)

    for amount in (600000, 650000, 700000):
        await pg_client.post(
            "/api/calendar/changes",
            json={
                "start": _day(ctx, 2),
                "end": _day(ctx, 2),
                "room_type_ids": [ctx["room"]["id"]],
                "change": {
                    "kind": "set_price",
                    "rate_plan_id": ctx["plan"]["id"],
                    "amount": amount,
                },
            },
        )

    assert len(await _queue_rows(pg_session, tenant_id)) == 1


async def test_bookings_queue_their_nights_and_send_availability(
    pg_client, pg_session, pg_session_factory
) -> None:
    ctx = await _live_connection(pg_client)
    tenant_id = ctx["workspace"]["tenant"]["id"]
    await push_now(pg_session_factory, tenant_id)

    booking = await make_booking(pg_client, ctx["room"], ctx["plan"], _day(ctx, 2), _day(ctx, 5))
    rows = await _queue_rows(pg_session, tenant_id)
    await push_now(pg_session_factory, tenant_id)
    ari = await _ari(pg_session, ctx["connection"]["external_property_id"])
    assert [date for _r, date in rows] == [_day(ctx, 2), _day(ctx, 3), _day(ctx, 4)]
    assert ari[_day(ctx, 2)]["available"] == 1
    assert ari[_day(ctx, 1)]["available"] == 2

    # changing and cancelling also reach the channel
    await pg_client.patch(
        f"/api/bookings/{booking['id']}", json={"arrival": _day(ctx, 4), "departure": _day(ctx, 6)}
    )
    assert len(await _queue_rows(pg_session, tenant_id)) == 4  # old and new nights, deduped
    await push_now(pg_session_factory, tenant_id)
    await pg_client.post(f"/api/bookings/{booking['id']}/cancel", json={})
    await push_now(pg_session_factory, tenant_id)
    ari = await _ari(pg_session, ctx["connection"]["external_property_id"])
    assert ari[_day(ctx, 2)]["available"] == 2  # everything back


async def test_hold_back_and_price_adjustment_change_what_is_sent(
    pg_client, pg_session, pg_session_factory
) -> None:
    ctx = await _live_connection(pg_client, units=3)
    tenant_id = ctx["workspace"]["tenant"]["id"]
    await pg_session.execute(
        text(
            "UPDATE property SET settings = settings || "
            '\'{"business": {"channel_hold_back_units": 1}}\'::jsonb WHERE id = :p'
        ),
        {"p": ctx["workspace"]["property"]["id"]},
    )
    await pg_session.commit()
    await pg_client.patch(
        f"{CONNECTIONS}/{ctx['connection']['id']}", json={"price_adjustment_percent": 10}
    )

    changed = await pg_client.post(
        "/api/calendar/changes",
        json={
            "start": _day(ctx, 1),
            "end": _day(ctx, 1),
            "room_type_ids": [ctx["room"]["id"]],
            "change": {"kind": "set_price", "rate_plan_id": ctx["plan"]["id"], "amount": 100000},
        },
    )
    assert changed.status_code == 200
    await push_now(pg_session_factory, tenant_id)

    ari = await _ari(pg_session, ctx["connection"]["external_property_id"])
    assert ari[_day(ctx, 1)]["available"] == 2  # 3 units, 1 held back
    assert ari[_day(ctx, 1)]["prices"] == {"P1": 110000}  # +10%


async def test_pausing_closes_the_channel_and_resuming_reopens_it(
    pg_client, pg_session, pg_session_factory
) -> None:
    ctx = await _live_connection(pg_client)
    tenant_id = ctx["workspace"]["tenant"]["id"]
    await push_now(pg_session_factory, tenant_id)

    await pg_client.post(f"{CONNECTIONS}/{ctx['connection']['id']}/pause")
    await push_now(pg_session_factory, tenant_id)
    ari = await _ari(pg_session, ctx["connection"]["external_property_id"])
    assert ari[_day(ctx, 10)]["closed"] is True
    assert ari[_day(ctx, 10)]["available"] == 0

    await pg_client.post(f"{CONNECTIONS}/{ctx['connection']['id']}/resume")
    await push_now(pg_session_factory, tenant_id)
    ari = await _ari(pg_session, ctx["connection"]["external_property_id"])
    assert ari[_day(ctx, 10)]["closed"] is False
    assert ari[_day(ctx, 10)]["available"] == 2


async def test_base_price_room_count_and_mapping_changes_queue(
    pg_client, pg_session, pg_session_factory
) -> None:
    ctx = await _live_connection(pg_client)
    tenant_id = ctx["workspace"]["tenant"]["id"]
    await push_now(pg_session_factory, tenant_id)

    await pg_client.patch(
        f"/api/rate-plans/{ctx['plan']['id']}",
        json={"prices": [{"room_type_id": ctx["room"]["id"], "amount": 550000}]},
    )
    price_rows = len(await _queue_rows(pg_session, tenant_id))
    await push_now(pg_session_factory, tenant_id)

    await pg_client.patch(f"/api/room-types/{ctx['room']['id']}", json={"units": 3})
    unit_rows = len(await _queue_rows(pg_session, tenant_id))
    await push_now(pg_session_factory, tenant_id)

    assert price_rows == 366
    assert unit_rows == 366
    ari = await _ari(pg_session, ctx["connection"]["external_property_id"])
    assert ari[_day(ctx, 1)]["prices"] == {"P1": 550000}
    assert ari[_day(ctx, 1)]["available"] == 3


# ---- failures -----------------------------------------------------------------------------


async def test_failed_pushes_retry_with_backoff_and_surface_failing(
    pg_client, pg_session, pg_session_factory
) -> None:
    ctx = await _live_connection(pg_client)
    tenant_id = ctx["workspace"]["tenant"]["id"]
    hotel = ctx["connection"]["external_property_id"]
    connection_id = ctx["connection"]["id"]

    await push_now(pg_session_factory, tenant_id)
    from app.channels.simulator import set_fail_next

    async with pg_session:
        await set_fail_next(pg_session, ctx["workspace"]["tenant"]["id"], hotel, 3)

    changed = await pg_client.post(
        "/api/calendar/changes",
        json={
            "start": _day(ctx, 2),
            "end": _day(ctx, 2),
            "room_type_ids": [ctx["room"]["id"]],
            "change": {"kind": "close"},
        },
    )
    assert changed.status_code == 200

    first = await push_now(pg_session_factory, tenant_id)
    detail = (await pg_client.get(f"{CONNECTIONS}/{connection_id}")).json()
    assert first == 0
    assert detail["push_health"]["pending_updates"] == 1
    assert detail["push_health"]["next_push_at"] is not None
    assert [m["status"] for m in detail["messages"][0:1]] == ["failed"]

    # backoff not yet due: nothing happens even though work is waiting
    second = await push_now(pg_session_factory, tenant_id)
    assert second == 0

    # make each backoff due as we go: attempts two and three set failing_since
    for _attempt in (2, 3):
        await pg_session.execute(
            text(
                "UPDATE channelconnection SET next_push_at = now() - interval '1 second' "
                "WHERE id = :c"
            ),
            {"c": connection_id},
        )
        await pg_session.commit()
        assert await push_now(pg_session_factory, tenant_id) == 0
    detail = (await pg_client.get(f"{CONNECTIONS}/{connection_id}")).json()
    assert detail["push_health"]["failing_since"] is not None
    assert detail["push_health"]["at_risk"] is True  # failing repeatedly

    # the fourth attempt succeeds: flags clear, the queue empties
    await pg_session.execute(
        text(
            "UPDATE channelconnection SET next_push_at = now() - interval '1 second' WHERE id = :c"
        ),
        {"c": connection_id},
    )
    await pg_session.commit()
    fourth = await push_now(pg_session_factory, tenant_id)
    detail = (await pg_client.get(f"{CONNECTIONS}/{connection_id}")).json()
    assert fourth == 1
    assert detail["push_health"]["failing_since"] is None
    assert detail["push_health"]["pending_updates"] == 0
    assert detail["push_health"]["at_risk"] is False
    statuses = [m["status"] for m in detail["messages"]]
    assert statuses[0] == "acked"  # newest first
    ari = await _ari(pg_session, hotel)
    assert ari[_day(ctx, 2)]["closed"] is True


# ---- sync now and drift ------------------------------------------------------------------


async def test_sync_now_repushes_a_range_immediately(
    pg_client, pg_session, pg_session_factory
) -> None:
    ctx = await _live_connection(pg_client)
    await push_now(pg_session_factory, ctx["workspace"]["tenant"]["id"])
    hotel = ctx["connection"]["external_property_id"]

    # the channel loses two days (tampering, as a real channel drifting would)
    await pg_session.execute(
        text(
            "UPDATE channelsimulatorlisting "
            "SET ari = jsonb_set(ari, '{R1}', "
            "(ari->'R1') - :d1 - :d2) WHERE hotel_id = :h"
        ),
        {"h": hotel, "d1": _day(ctx, 2), "d2": _day(ctx, 3)},
    )
    await pg_session.commit()
    drift = (await pg_client.get(f"{CONNECTIONS}/{ctx['connection']['id']}/drift")).json()
    assert drift["differences"] and drift["differences"][0]["kind"] == "missing_on_channel"
    assert len(drift["differences"]) == 2

    synced = await pg_client.post(
        f"{CONNECTIONS}/{ctx['connection']['id']}/sync",
        json={"date_from": _day(ctx, 1), "date_to": _day(ctx, 3)},
    )
    drift_after = (await pg_client.get(f"{CONNECTIONS}/{ctx['connection']['id']}/drift")).json()

    assert synced.status_code == 200, synced.text
    assert synced.json()["push_health"]["pending_updates"] == 0
    assert drift_after["differences"] == []  # brought back in step


async def test_drift_reports_a_price_the_channel_still_has_old(
    pg_client, pg_session, pg_session_factory
) -> None:
    ctx = await _live_connection(pg_client)
    tenant_id = ctx["workspace"]["tenant"]["id"]
    await push_now(pg_session_factory, tenant_id)

    changed = await pg_client.post(
        "/api/calendar/changes",
        json={
            "start": _day(ctx, 2),
            "end": _day(ctx, 2),
            "room_type_ids": [ctx["room"]["id"]],
            "change": {"kind": "set_price", "rate_plan_id": ctx["plan"]["id"], "amount": 800000},
        },
    )
    assert changed.status_code == 200
    # not pushed yet: the channel still has the old price

    drift = (await pg_client.get(f"{CONNECTIONS}/{ctx['connection']['id']}/drift")).json()
    kinds = {item["kind"] for item in drift["differences"]}
    assert kinds == {"differs"}
    differs = drift["differences"][0]
    assert differs["channel"]["prices"] == {"P1": 500000}
    assert differs["ours"]["prices"] == {"P1": 800000}


async def test_sync_and_drift_need_their_permissions(
    pg_client, other_client, pg_session, pg_session_factory
) -> None:
    from tests.pg.conftest import add_staff_member

    ctx = await _live_connection(pg_client)
    await add_staff_member(pg_session, other_client, ctx["workspace"], role=None)
    target = f"{CONNECTIONS}/{ctx['connection']['id']}"

    sync = await other_client.post(f"{target}/sync", json={})
    drift = await other_client.get(f"{target}/drift")
    detail = await other_client.get(target)

    assert (sync.status_code, drift.status_code) == (403, 403)
    assert detail.status_code == 403  # even reading needs channels:view


async def test_nothing_is_queued_without_a_live_connection(
    pg_client, pg_session, pg_session_factory
) -> None:
    workspace = await start_workspace(pg_client)
    room = await make_room_type(pg_client)
    await make_rate_plan(pg_client, [room])
    await connect_channel(pg_client)  # tested, never gone live

    today = property_today(workspace["property"]["timezone"])
    changed = await pg_client.post(
        "/api/calendar/changes",
        json={
            "start": (today + dt.timedelta(days=1)).isoformat(),
            "end": (today + dt.timedelta(days=2)).isoformat(),
            "room_type_ids": [room["id"]],
            "change": {"kind": "close"},
        },
    )

    assert changed.status_code == 200
    assert await _queue_rows(pg_session, workspace["tenant"]["id"]) == []


async def test_a_change_arriving_mid_push_is_not_lost(
    pg_client, pg_session, pg_session_factory
) -> None:
    """A booking made while the channel is answering survives the push."""
    from app.channels import provider as channel_provider

    ctx = await _live_connection(pg_client)
    tenant_id = ctx["workspace"]["tenant"]["id"]
    await push_now(pg_session_factory, tenant_id)

    real = channel_provider._PROVIDERS["simulator"]  # a SimulatedChannel instance

    class SlowChannel:
        """Acknowledge, but a booking for the same night lands mid-flight."""

        def __init__(self) -> None:
            self.inner = real

        async def fetch_property(self, call, property_id):
            return await self.inner.fetch_property(call, property_id)

        async def push_ari(self, call, property_id, days):
            result = await self.inner.push_ari(call, property_id, days)
            # the "in-flight" change: the same date is re-queued under the provider's feet
            await pg_session.execute(
                text(
                    "INSERT INTO channelariupdate (tenant_id, property_id, channel_connection_id, "
                    "unit_type_id, stay_date) VALUES (:t, :p, :c, :r, :d) "
                    "ON CONFLICT ON CONSTRAINT channelariupdate_due_key "
                    "DO UPDATE SET created_at = now()"
                ),
                {
                    "t": tenant_id,
                    "p": ctx["workspace"]["property"]["id"],
                    "c": ctx["connection"]["id"],
                    "r": ctx["room"]["id"],
                    "d": dt.date.fromisoformat(_day(ctx, 6)),
                },
            )
            await pg_session.commit()
            return result

        async def fetch_current_ari(self, call, property_id, room_ids, dates):
            return await self.inner.fetch_current_ari(call, property_id, room_ids, dates)

    import app.services.channel_push as push_module

    original = push_module.get_channel

    def patched(code):
        return SlowChannel() if code == "simulator" else original(code)

    push_module.get_channel = patched
    try:
        await pg_client.post(
            "/api/calendar/changes",
            json={
                "start": _day(ctx, 6),
                "end": _day(ctx, 6),
                "room_type_ids": [ctx["room"]["id"]],
                "change": {"kind": "close"},
            },
        )
        await push_now(pg_session_factory, tenant_id)
    finally:
        push_module.get_channel = original

    rows = await _queue_rows(pg_session, tenant_id)
    assert rows == [(ctx["room"]["id"], _day(ctx, 6))]  # the mid-flight change stayed queued
    assert await push_now(pg_session_factory, tenant_id) == 1  # and the next tick delivers it
    assert await _queue_rows(pg_session, tenant_id) == []


async def test_a_dangling_mapping_no_longer_breaks_pushes(
    pg_client, pg_session, pg_session_factory
) -> None:
    """Removing a room from a rate plan also removes its channel mapping."""
    ctx = await _live_connection(pg_client)
    tenant_id = ctx["workspace"]["tenant"]["id"]
    await push_now(pg_session_factory, tenant_id)

    # the plan stops selling the room; the mapping must go with it
    other = await make_room_type(pg_client, name="Suite")
    await pg_client.patch(
        f"/api/rate-plans/{ctx['plan']['id']}",
        json={"prices": [{"room_type_id": other["id"], "amount": 400000}]},
    )
    mappings = (
        await pg_session.execute(
            text(
                "SELECT count(*) FROM channelmapping WHERE tenant_id = :t "
                "AND rate_plan_id = :p AND unit_type_id = :r"
            ),
            {"t": tenant_id, "p": ctx["plan"]["id"], "r": ctx["room"]["id"]},
        )
    ).scalar_one()
    assert mappings == 0

    pushed = await push_now(pg_session_factory, tenant_id)  # must not raise
    assert pushed == 1
