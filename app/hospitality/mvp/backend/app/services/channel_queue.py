"""The queue of channel dates whose truth must (again) be sent.

Any change that affects what a property sells — calendar edits, bookings, room counts,
base prices, matching changes, a connection going live or being paused — drops its
dates here. One row per (connection, room type, date); the unique key collapses
repeated changes into the pending set. The background sender deletes rows as channels
acknowledge them.

Queue rows are written inside the same transaction as the change that caused them, so
a change is never silently un-queued.
"""

import datetime as dt
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import ChannelAriUpdate, ChannelConnection
from app.tenancy.context import TenantContext

LIVE = "live"
PAUSED = "paused"
DISCONNECTED = "disconnected"


async def _sending_connections(
    session: AsyncSession, context: TenantContext, property_id: UUID
) -> list[ChannelConnection]:
    rows = await session.exec(
        select(ChannelConnection).where(
            col(ChannelConnection.tenant_id) == context.tenant_id,
            col(ChannelConnection.property_id) == property_id,
            col(ChannelConnection.status).in_((LIVE, PAUSED)),
        )
    )
    return list(rows.all())


async def enqueue(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    room_type_ids: list[UUID],
    dates: list[dt.date],
) -> int:
    """Queue `dates` of `room_type_ids` for every connection that is sending.

    Nothing is queued when no connection is live or paused. Rows that already exist
    are left as they are (their created_at keeps the original age). Returns the number
    of new rows.
    """
    if not room_type_ids or not dates:
        return 0
    connections = await _sending_connections(session, context, property_id)
    if not connections:
        return 0
    rows = [
        {
            "tenant_id": context.tenant_id,
            "property_id": property_id,
            "channel_connection_id": connection.id,
            "unit_type_id": room_type_id,
            "stay_date": date,
        }
        for connection in connections
        for room_type_id in set(room_type_ids)
        for date in set(dates)
    ]
    statement = pg_insert(ChannelAriUpdate).values(rows)
    # A re-queued date bumps created_at: the sender deletes only the rows it read a
    # snapshot of, so a change arriving while a push is in flight is never lost.
    statement = statement.on_conflict_do_update(
        constraint="channelariupdate_due_key", set_={"created_at": func.now()}
    ).returning(col(ChannelAriUpdate.id))
    result = await session.exec(statement)
    return len(result.all())


def horizon(today: dt.date, days: int) -> list[dt.date]:
    """The whole selling window from `today`, as queue-able dates."""
    return [today + dt.timedelta(days=offset) for offset in range(days)]


async def due_by_connection(
    session: AsyncSession, context: TenantContext
) -> dict[UUID, list[ChannelAriUpdate]]:
    """Every queued row, grouped by connection (the sender walks tenants, not properties)."""
    rows = await session.exec(
        select(ChannelAriUpdate)
        .where(col(ChannelAriUpdate.tenant_id) == context.tenant_id)
        .order_by(col(ChannelAriUpdate.channel_connection_id), col(ChannelAriUpdate.stay_date))
    )
    grouped: dict[UUID, list[ChannelAriUpdate]] = {}
    for row in rows.all():
        grouped.setdefault(row.channel_connection_id, []).append(row)
    return grouped


async def pending_counts(
    session: AsyncSession, context: TenantContext, property_id: UUID
) -> dict[UUID, int]:
    """Queued rows per connection of one property (for the status read)."""
    rows = await session.exec(
        select(
            col(ChannelAriUpdate.channel_connection_id),
            col(ChannelAriUpdate.id),
        ).where(
            col(ChannelAriUpdate.tenant_id) == context.tenant_id,
            col(ChannelAriUpdate.property_id) == property_id,
        )
    )
    counts: dict[UUID, int] = {}
    for connection_id, _row_id in rows.all():
        counts[connection_id] = counts.get(connection_id, 0) + 1
    return counts


async def oldest_pending_at(
    session: AsyncSession, context: TenantContext, connection_id: UUID
) -> dt.datetime | None:
    return (
        await session.exec(
            select(col(ChannelAriUpdate.created_at))
            .where(
                col(ChannelAriUpdate.tenant_id) == context.tenant_id,
                col(ChannelAriUpdate.channel_connection_id) == connection_id,
            )
            .order_by(col(ChannelAriUpdate.created_at))
            .limit(1)
        )
    ).first()
