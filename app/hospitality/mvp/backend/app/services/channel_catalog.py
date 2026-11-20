"""Which sales channels exist, which can be connected now, and how many are in use."""

from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.channels.provider import is_connectable
from app.channels.simulator import SIMULATOR_CHANNEL
from app.config import settings
from app.models.control_plane import ChannelCatalog
from app.models.tenant import Channel, ChannelConnection
from app.schemas.channels import CatalogChannel, ChannelsOverview, ChannelUsage
from app.services.channel_quota import DISCONNECTED, read_quota
from app.tenancy.context import TenantContext

# Booking sources staff pick by hand are in the same catalogue but are not connections.
_NOT_CONNECTIONS = ("direct_web", "direct_phone", "walk_in", "messaging")


def can_connect(code: str) -> bool:
    """True when a connection to this channel can be made in this installation."""
    if code == SIMULATOR_CHANNEL and not settings.CHANNEL_SIMULATOR_ENABLED:
        return False
    return is_connectable(code)


async def find_catalog_entry(session: AsyncSession, code: str) -> ChannelCatalog | None:
    return (
        await session.exec(
            select(ChannelCatalog).where(
                col(ChannelCatalog.code) == code, col(ChannelCatalog.is_active).is_(True)
            )
        )
    ).first()


async def _connected_codes(
    session: AsyncSession, context: TenantContext, property_id: UUID
) -> set[str]:
    rows = await session.exec(
        select(col(Channel.code))
        .join(
            ChannelConnection,
            (col(ChannelConnection.tenant_id) == col(Channel.tenant_id))
            & (col(ChannelConnection.channel_id) == col(Channel.id)),
        )
        .where(
            col(ChannelConnection.tenant_id) == context.tenant_id,
            col(ChannelConnection.property_id) == property_id,
            col(ChannelConnection.status) != DISCONNECTED,
        )
    )
    return set(rows.all())


async def overview(
    session: AsyncSession, context: TenantContext, property_id: UUID
) -> ChannelsOverview:
    """Connectable channels first, then those still to come; with usage against the plan."""
    entries = (
        await session.exec(
            select(ChannelCatalog)
            .where(
                col(ChannelCatalog.is_active).is_(True),
                col(ChannelCatalog.kind).not_in(_NOT_CONNECTIONS),
            )
            .order_by(col(ChannelCatalog.name))
        )
    ).all()
    connected = await _connected_codes(session, context, property_id)
    quota = await read_quota(session, context, property_id)
    channels = [
        CatalogChannel(
            code=entry.code,
            name=entry.name,
            kind=entry.kind,
            features=list(entry.features),
            state="connectable" if can_connect(entry.code) else "coming_soon",
            connected=entry.code in connected,
        )
        for entry in entries
        if entry.code != SIMULATOR_CHANNEL or settings.CHANNEL_SIMULATOR_ENABLED
    ]
    return ChannelsOverview(
        usage=ChannelUsage(used=quota.used, limit=quota.limit, limit_reached=quota.limit_reached),
        channels=sorted(channels, key=lambda channel: channel.state != "connectable"),
    )
