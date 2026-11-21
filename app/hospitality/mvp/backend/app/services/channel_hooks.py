"""What happens on a channel when a connection goes live, is paused or resumes.

Going live and resuming queue the whole selling window, so the channel is brought up
to date (the sender pushes what was queued). Pausing queues the window too — the
sender sends a paused connection as closed everywhere, which stops sale on the
channel at once.
"""

import datetime as dt

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import ChannelConnection, Property
from app.services import channel_queue
from app.services.channel_truth import mappings_of
from app.tenancy.context import TenantContext

# The whole selling window is queued on go-live, resume and pause. Dates beyond the
# calendar horizon cannot hold anything to sell, so this covers "everything".
FULL_SYNC_DAYS = 366


def _horizon(connection: ChannelConnection) -> list[dt.date]:
    timezone_name = str(connection.settings.get("timezone") or "UTC")
    today = today_in(timezone_name)
    return channel_queue.horizon(today, FULL_SYNC_DAYS)


def today_in(timezone_name: str) -> dt.date:
    from app.services.calendar_dates import property_today

    return property_today(timezone_name)


async def _queue_all(
    session: AsyncSession, context: TenantContext, connection: ChannelConnection
) -> None:
    """Queue every mapped room type over the whole selling window."""
    prop = (
        await session.exec(
            select(col(Property.id)).where(
                col(Property.tenant_id) == context.tenant_id,
                col(Property.id) == connection.property_id,
            )
        )
    ).first()
    if prop is None:  # the property is gone; nothing to sell
        return
    mappings = await mappings_of(session, context, connection.id)
    room_type_ids = list({mapping.unit_type_id for mapping in mappings})
    await channel_queue.enqueue(
        session, context, connection.property_id, room_type_ids, _horizon(connection)
    )


async def on_go_live(
    session: AsyncSession, context: TenantContext, connection: ChannelConnection
) -> None:
    """The connection has just gone live: bring the channel up to date."""
    await _queue_all(session, context, connection)


async def on_pause(
    session: AsyncSession, context: TenantContext, connection: ChannelConnection
) -> None:
    """The connection has just been paused: the sender will close it everywhere."""
    await _queue_all(session, context, connection)


async def on_resume(
    session: AsyncSession, context: TenantContext, connection: ChannelConnection
) -> None:
    """The connection has just resumed: send the truth again, everywhere."""
    await _queue_all(session, context, connection)
