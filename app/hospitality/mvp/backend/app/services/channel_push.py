"""The sender: due queue rows become pushes to channels, with retries until acknowledged.

Per connection, one push attempt at a time:

    read the queued rows (plain read, no lock) → build the truth → commit
    → call the channel with no lock held
    → on acknowledgement: delete those rows, stamp `last_ari_success_at`, clear failures
    → on failure: leave the rows queued, write the message log row with the error and
      set `next_push_at` (backoff); after three failures `failing_since` is set.

A paused connection is sent as closed everywhere (availability zero), which is also
what pausing pushes. Everything sent is recorded in `channelmessage` with its payload,
status and attempt count; retries append a new row so the history stays honest.
"""

import asyncio
import datetime as dt
import logging
import uuid
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import col, delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.channels.provider import (
    AriDay,
    ChannelCall,
    ChannelUnavailableError,
    UnknownChannelPropertyError,
    get_channel,
)
from app.models.tenant import ChannelAriUpdate, ChannelConnection, ChannelMessage, Property
from app.services import channel_truth
from app.services.calendar_dates import property_today
from app.services.channel_connections import channel_of
from app.services.channel_queue import due_by_connection
from app.services.channel_truth import mappings_of
from app.tenancy.business_settings import resolve_property_settings
from app.tenancy.context import TenantContext
from app.tenancy.session import bind_tenant

log = logging.getLogger(__name__)

OUTBOUND = "outbound"
DELTA = "ari_delta"
FULL_SYNC = "ari_full_sync"
SENT = "sent"
ACKED = "acked"
FAILED = "failed"
# Backoff after a failed push: 5 s, 30 s, 2 m, 10 m, then every 30 m.
BACKOFF_SECONDS = (5, 30, 120, 600, 1800)
FAILING_AFTER = 3
MAX_CELLS_PER_PUSH = 20_000
DRIFT_WINDOW_DAYS = 60


class NothingToPushError(Exception):
    """The connection has nothing queued."""


def _context(tenant_id: UUID, session: AsyncSession) -> TenantContext:
    # The sender runs outside a request: a synthetic context with the ids it needs.
    return TenantContext(
        tenant_id=tenant_id,
        user_id=0,
        email="",
        is_owner=False,
        staff_member_id=None,
        last_property_id=None,
    )


async def _property_of(session: AsyncSession, property_id: UUID) -> Property:
    return (await session.exec(select(Property).where(col(Property.id) == property_id))).one()


async def _attempts_since_success(session: AsyncSession, connection_id: UUID) -> int:
    rows = await session.exec(
        select(col(ChannelMessage.status))
        .where(
            col(ChannelMessage.channel_connection_id) == connection_id,
            col(ChannelMessage.direction) == OUTBOUND,
        )
        .order_by(col(ChannelMessage.created_at).desc(), col(ChannelMessage.id).desc())
        .limit(50)
    )
    count = 0
    for status in rows.all():
        if status == ACKED:
            break
        if status == FAILED:
            count += 1
    return count


async def _log_row(
    session: AsyncSession,
    context: TenantContext,
    connection: ChannelConnection,
    *,
    message_type: str,
    status: str,
    attempt: int,
    date_from: dt.date,
    date_to: dt.date,
    request: dict[str, Any] | None = None,
    error: str | None = None,
    next_attempt_at: dt.datetime | None = None,
) -> ChannelMessage:
    row = ChannelMessage(
        tenant_id=context.tenant_id,
        channel_connection_id=connection.id,
        direction=OUTBOUND,
        message_type=message_type,
        status=status,
        attempts=attempt,
        date_from=date_from,
        date_to=date_to,
        correlation_id=uuid.uuid4().hex,
        request_payload=request,
        error=error,
        next_attempt_at=next_attempt_at,
        sent_at=dt.datetime.now(dt.UTC) if status in (SENT, ACKED) else None,
        created_by="channel-sender",
    )
    session.add(row)
    return row


async def push_connection(
    session: AsyncSession,
    context: TenantContext,
    connection: ChannelConnection,
    queued: list[ChannelAriUpdate],
    *,
    force_closed: bool = False,
) -> bool:
    """Push one connection's queued dates. Commits in three steps (read, send, record).

    Returns True when the channel acknowledged. `force_closed` sends availability zero
    for every queued date — what pausing uses.
    """
    if not queued:
        raise NothingToPushError
    prop = await _property_of(session, connection.property_id)
    settings = resolve_property_settings(prop.settings)
    mappings = await mappings_of(session, context, connection.id)
    dates = sorted({row.stay_date for row in queued})
    # Chunk by date: a queue larger than one push is sent in several, so a big
    # go-live or sync can never leave rows the sender refuses to drain.
    room_count = max(len({row.unit_type_id for row in queued}), 1)
    date_chunks: list[list[dt.date]] = []
    chunk: list[dt.date] = []
    for date in dates:
        chunk.append(date)
        if len(chunk) * room_count >= MAX_CELLS_PER_PUSH:
            date_chunks.append(chunk)
            chunk = []
    if chunk:
        date_chunks.append(chunk)
    for chunk_dates in date_chunks:
        acknowledged = await _push_chunk(
            session,
            context,
            connection,
            prop,
            settings,
            mappings,
            [row for row in queued if row.stay_date in set(chunk_dates)],
            chunk_dates,
            force_closed=force_closed,
        )
        if not acknowledged:
            return False  # a failure waits out its backoff; the rest stays queued
    return True


async def _push_chunk(
    session: AsyncSession,
    context: TenantContext,
    connection: ChannelConnection,
    prop: Property,
    settings: object,
    mappings: list,
    chunk_rows: list[ChannelAriUpdate],
    chunk_dates: list[dt.date],
    *,
    force_closed: bool,
) -> bool:
    """Push one chunk of dates to the channel. True when it acknowledged."""
    days = await channel_truth.build_days(
        session, context, prop, settings, connection, mappings, chunk_dates
    )
    if force_closed:
        days = {
            room: [
                AriDay(
                    date=day.date,
                    available=0,
                    closed=True,
                    min_stay=day.min_stay,
                    prices=day.prices,
                )
                for day in room_days
            ]
            for room, room_days in days.items()
        }
    payload = {room: [day.__dict__ for day in room_days] for room, room_days in days.items()}
    chunk_ids = [row.id for row in chunk_rows]
    # Rows re-queued while this push is in flight get a newer created_at and survive.
    snapshot = max((row.created_at for row in chunk_rows), default=dt.datetime.now(dt.UTC))
    connection_id = connection.id  # read before any rollback: expired attrs raise
    await session.commit()  # our reads are done; the channel is called with no lock held

    code = (await channel_of(session, context, connection)).code
    provider = get_channel(code)
    attempt = await _attempts_since_success(session, connection.id) + 1
    try:
        await provider.push_ari(
            ChannelCall(tenant_id=context.tenant_id, session=session),
            connection.external_property_id or "",
            days,
        )
    except (ChannelUnavailableError, UnknownChannelPropertyError) as exc:
        await session.rollback()
        connection = (
            await session.exec(
                select(ChannelConnection)
                .where(
                    col(ChannelConnection.tenant_id) == context.tenant_id,
                    col(ChannelConnection.id) == connection_id,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).one()
        backoff = BACKOFF_SECONDS[min(attempt - 1, len(BACKOFF_SECONDS) - 1)]
        now = dt.datetime.now(dt.UTC)
        connection.next_push_at = now + dt.timedelta(seconds=backoff)
        if attempt >= FAILING_AFTER:
            connection.failing_since = connection.failing_since or now
        session.add(connection)
        await _log_row(
            session,
            context,
            connection,
            message_type=DELTA,
            status=FAILED,
            attempt=attempt,
            date_from=chunk_dates[0],
            date_to=chunk_dates[-1],
            request={"rooms": sorted(days)},
            error=str(exc)[:500],
            next_attempt_at=connection.next_push_at,
        )
        await session.commit()
        log.warning("Channel push failed connection=%s attempt=%s: %s", connection.id, attempt, exc)
        return False

    connection = (
        await session.exec(
            select(ChannelConnection)
            .where(
                col(ChannelConnection.tenant_id) == context.tenant_id,
                col(ChannelConnection.id) == connection.id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).one()
    now = dt.datetime.now(dt.UTC)
    connection.last_ari_success_at = now
    connection.error_message = None
    connection.next_push_at = None
    connection.failing_since = None
    session.add(connection)
    await _log_row(
        session,
        context,
        connection,
        message_type=DELTA,
        status=ACKED,
        attempt=attempt,
        date_from=chunk_dates[0],
        date_to=chunk_dates[-1],
        request=payload,
    )
    await session.exec(
        delete(ChannelAriUpdate).where(
            col(ChannelAriUpdate.tenant_id) == context.tenant_id,
            col(ChannelAriUpdate.id).in_(chunk_ids),
            col(ChannelAriUpdate.created_at) <= snapshot,
        )
    )
    await session.commit()
    log.info("Channel push acknowledged connection=%s dates=%s", connection.id, len(chunk_dates))
    return True


async def process_tenant(
    session: AsyncSession, tenant_id: UUID, *, now: dt.datetime | None = None
) -> int:
    """Push everything due for one tenant. Returns the number of pushes acknowledged."""
    now = now or dt.datetime.now(dt.UTC)
    context = _context(tenant_id, session)
    due = await due_by_connection(session, context)
    acknowledged = 0
    for connection_id, queued in due.items():
        connection = (
            await session.exec(
                select(ChannelConnection)
                .where(
                    col(ChannelConnection.tenant_id) == tenant_id,
                    col(ChannelConnection.id) == connection_id,
                )
                .execution_options(populate_existing=True)
            )
        ).first()
        if connection is None or connection.status == "disconnected":
            continue
        if connection.next_push_at and connection.next_push_at > now:
            continue  # a failed push is waiting out its backoff
        acknowledged += await push_connection(
            session, context, connection, queued, force_closed=connection.status == "paused"
        )
    return acknowledged


async def process_due(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """The worker's tick: push everything due for every tenant with queued work."""
    from app.models.control_plane import Tenant

    async with session_factory() as session:
        # From the control plane (readable under RLS via the own-tenant policy), not the
        # queue: the queue is a tenant table under FORCE RLS, and a least-privilege
        # connection role would see none of it here.
        tenant_ids = list((await session.exec(select(col(Tenant.id)))).all())
    acknowledged = 0
    for tenant_id in tenant_ids:
        try:
            async with session_factory() as session:
                await bind_tenant(session, tenant_id)
                acknowledged += await process_tenant(session, tenant_id)
        except Exception:  # noqa: BLE001 — one tenant must not stop the others
            log.exception("Channel push failed for tenant=%s", tenant_id)
    return acknowledged


async def run_channel_pusher(
    session_factory: async_sessionmaker[AsyncSession], stop: asyncio.Event, interval_seconds: int
) -> None:
    """The background loop started with the app."""
    log.info("Channel pusher started (every %ss)", interval_seconds)
    while not stop.is_set():
        try:
            await process_due(session_factory)
        except Exception:  # noqa: BLE001 — the loop must survive anything
            log.exception("Channel pusher tick failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
        except TimeoutError:
            pass
    log.info("Channel pusher stopped")


async def sync_connection(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_id: UUID,
    connection_id: UUID,
    *,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
) -> int:
    """Re-send a date range (or the whole window) to one connection, now.

    Queue rows are added first (the whole matched set for the range), then the sender
    runs for this connection until its queue is empty or a push fails. Returns the
    number of pushes acknowledged.
    """
    from app.services.channel_queue import enqueue as enqueue_channels
    from app.services.channel_queue import horizon as channel_horizon

    async with session_factory() as session:
        await bind_tenant(session, tenant_id)
        context = _context(tenant_id, session)
        connection = (
            await session.exec(
                select(ChannelConnection).where(
                    col(ChannelConnection.tenant_id) == tenant_id,
                    col(ChannelConnection.id) == connection_id,
                )
            )
        ).first()
        if connection is None:
            raise ValueError("connection not found")
        if connection.next_push_at is not None:
            # "Sync now" is an explicit instruction: past failures wait out their
            # backoff in the background loop, but a person asking means: try now.
            connection.next_push_at = None
            session.add(connection)
        mappings = await mappings_of(session, context, connection.id)
        prop = await _property_of(session, connection.property_id)
        if date_from is None or date_to is None:
            dates = channel_horizon(property_today(prop.timezone), DRIFT_WINDOW_DAYS + 1)
        else:
            dates = [
                date_from + dt.timedelta(days=n) for n in range((date_to - date_from).days + 1)
            ]
        await enqueue_channels(
            session,
            context,
            connection.property_id,
            list({m.unit_type_id for m in mappings}),
            dates,
        )
        # mark this as a full-sync range in the log by processing it in one go
        await session.commit()
    acknowledged = 0
    while True:
        async with session_factory() as session:
            await bind_tenant(session, tenant_id)
            context = _context(tenant_id, session)
            connection = (
                await session.exec(
                    select(ChannelConnection).where(
                        col(ChannelConnection.tenant_id) == tenant_id,
                        col(ChannelConnection.id) == connection_id,
                    )
                )
            ).first()
            if connection is None:
                break
            queued = (await due_by_connection(session, context)).get(connection_id, [])
            if not queued:
                break
            if connection.next_push_at and connection.next_push_at > dt.datetime.now(dt.UTC):
                break  # a failure is waiting out its backoff; the worker will retry
            ok = await push_connection(
                session,
                context,
                connection,
                queued,
                force_closed=connection.status == "paused",
            )
            if not ok:
                break
            acknowledged += 1
            if acknowledged > 50:  # a hard stop for pathological queues
                break
    return acknowledged


async def drift_for_connection(
    session: AsyncSession, context: TenantContext, connection: ChannelConnection
) -> list[dict[str, object]]:
    """Dates where what the channel holds differs from our truth, next 60 days."""
    from app.channels.provider import get_channel as _get
    from app.services.channel_truth import build_days

    mappings = await mappings_of(session, context, connection.id)
    if not mappings:
        return []
    prop = await _property_of(session, connection.property_id)
    settings = resolve_property_settings(prop.settings)
    today = property_today(prop.timezone)
    dates = [today + dt.timedelta(days=n) for n in range(DRIFT_WINDOW_DAYS)]
    truth = await build_days(session, context, prop, settings, connection, mappings, dates)
    if connection.status == "paused":  # the sender pushes paused connections as closed
        truth = {
            room: [
                AriDay(
                    date=day.date,
                    available=0,
                    closed=True,
                    min_stay=day.min_stay,
                    prices=day.prices,
                )
                for day in room_days
            ]
            for room, room_days in truth.items()
        }
    code = (await channel_of(session, context, connection)).code
    current = await _get(code).fetch_current_ari(
        ChannelCall(tenant_id=context.tenant_id, session=session),
        connection.external_property_id or "",
        sorted(truth),
        [date.isoformat() for date in dates],
    )
    differences = []
    for room, room_truth in truth.items():
        held = {day.date: day for day in current.get(room, [])}
        for day in room_truth:
            theirs = held.get(day.date)
            if theirs is None:
                differences.append({"room": room, "date": day.date, "kind": "missing_on_channel"})
            elif (
                theirs.available != day.available
                or theirs.closed != day.closed
                or theirs.min_stay != day.min_stay
                or theirs.prices != day.prices
            ):
                differences.append(
                    {
                        "room": room,
                        "date": day.date,
                        "kind": "differs",
                        "channel": {
                            "available": theirs.available,
                            "closed": theirs.closed,
                            "min_stay": theirs.min_stay,
                            "prices": theirs.prices,
                        },
                        "ours": {
                            "available": day.available,
                            "closed": day.closed,
                            "min_stay": day.min_stay,
                            "prices": day.prices,
                        },
                    }
                )
    return sorted(differences, key=lambda item: (item["date"], item["room"]))[:100]
