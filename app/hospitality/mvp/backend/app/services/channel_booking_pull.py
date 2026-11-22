"""The booking poller: what the channel sold, fetched and applied on a timer.

For every live connection, ask the channel for booking changes since the last pull
(`channelconnection.last_booking_pull_at`) and feed each one through
`channel_bookings.handle_booking_event` — the same handler a webhook would call. An
empty answer is healthy; a failure is logged and retried on the next tick.

Single-process assumption as with the sender (documented until we run more than one).
"""

import asyncio
import datetime as dt
import logging
from uuid import UUID

from sqlmodel import col, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.channels.provider import ChannelCall, get_channel
from app.models.control_plane import Tenant
from app.models.tenant import ChannelConnection
from app.services import channel_bookings
from app.services.channel_connections import channel_of
from app.tenancy.session import bind_tenant

log = logging.getLogger(__name__)

LIVE = "live"


async def pull_connection(session: AsyncSession, context, connection: ChannelConnection) -> int:
    """Fetch and apply one connection's booking changes. Returns events applied."""
    code = (await channel_of(session, context, connection)).code
    provider = get_channel(code)
    since = connection.last_booking_pull_at
    call = ChannelCall(tenant_id=context.tenant_id, session=session)
    # The simulator's clock has second granularity; two events can share a timestamp.
    # Fetch from one second before the cursor and let the handler's idempotency drop
    # what was already applied — correctness never depends on the clock.
    since_iso = None
    if since is not None:
        since_iso = (since - dt.timedelta(seconds=1)).isoformat()
    events = await provider.fetch_booking_changes(
        call, connection.external_property_id or "", since_iso
    )
    applied = 0
    for event in events:
        try:
            await channel_bookings.handle_booking_event(session, context, connection, event)
            applied += 1
        except (channel_bookings.DuplicateEventError, channel_bookings.StaleVersionError):
            continue  # already applied; a healthy repeat
    if events:
        connection.last_booking_pull_at = dt.datetime.fromisoformat(
            max(event.occurred_at for event in events)
        )
    elif since is None:
        connection.last_booking_pull_at = dt.datetime.now(dt.UTC)
    session.add(connection)
    await session.commit()
    return applied


async def pull_tenant(session: AsyncSession, tenant_id: UUID) -> int:
    """Pull every live connection of one tenant."""
    from app.services.channel_push import _context as sender_context

    context = sender_context(tenant_id, session)
    connections = (
        await session.exec(
            select(ChannelConnection).where(
                col(ChannelConnection.tenant_id) == tenant_id,
                col(ChannelConnection.status) == LIVE,
            )
        )
    ).all()
    applied = 0
    for connection in connections:
        try:
            applied += await pull_connection(session, context, connection)
        except Exception:  # noqa: BLE001 — one connection must not stop the others
            log.exception("Booking pull failed tenant=%s connection=%s", tenant_id, connection.id)
    return applied


async def pull_due(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """The poller's tick: pull every tenant with a live connection."""
    async with session_factory() as session:
        tenant_ids = list((await session.exec(select(col(Tenant.id)))).all())
    applied = 0
    for tenant_id in tenant_ids:
        try:
            async with session_factory() as session:
                await bind_tenant(session, tenant_id)
                applied += await pull_tenant(session, tenant_id)
        except Exception:  # noqa: BLE001 — keep going with the other tenants
            log.exception("Booking pull failed for tenant=%s", tenant_id)
    return applied


async def run_booking_poller(
    session_factory: async_sessionmaker[AsyncSession], stop: asyncio.Event, interval_seconds: int
) -> None:
    """The background loop started with the app."""
    log.info("Channel booking poller started (every %ss)", interval_seconds)
    while not stop.is_set():
        try:
            await pull_due(session_factory)
        except Exception:  # noqa: BLE001 — the loop must survive anything
            log.exception("Channel booking poller tick failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
        except TimeoutError:
            pass
    log.info("Channel booking poller stopped")
