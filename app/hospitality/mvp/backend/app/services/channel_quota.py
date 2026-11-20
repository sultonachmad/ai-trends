"""The plan's limit on connected channels: what staff are shown and what is enforced."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.control_plane import TenantEntitlement
from app.models.tenant import ChannelConnection
from app.tenancy.business_settings import resolve_plan_limits
from app.tenancy.context import TenantContext

CHANNEL_MODULE = "channel_manager"
DISCONNECTED = "disconnected"
NOT_IN_PLAN = 0


class ChannelLimitReachedError(Exception):
    """The property has as many connected channels as its plan allows."""

    def __init__(self, quota: "ChannelQuota") -> None:
        super().__init__(f"channel limit reached ({quota.used}/{quota.limit})")
        self.quota = quota


@dataclass(frozen=True)
class ChannelQuota:
    used: int
    limit: int | None  # None = unlimited

    @property
    def limit_reached(self) -> bool:
        return self.limit is not None and self.used >= self.limit


async def _limit(session: AsyncSession, context: TenantContext) -> int | None:
    entitlement = (
        await session.exec(
            select(TenantEntitlement).where(
                col(TenantEntitlement.tenant_id) == context.tenant_id,
                col(TenantEntitlement.module_code) == CHANNEL_MODULE,
                col(TenantEntitlement.enabled).is_(True),
            )
        )
    ).first()
    if entitlement is None:
        return NOT_IN_PLAN
    return resolve_plan_limits(entitlement.limits).connected_channels


async def read_quota(
    session: AsyncSession, context: TenantContext, property_id: UUID
) -> ChannelQuota:
    """Every connection that has not been disconnected counts, drafts included."""
    used = (
        await session.exec(
            select(func.count())
            .select_from(ChannelConnection)
            .where(
                col(ChannelConnection.tenant_id) == context.tenant_id,
                col(ChannelConnection.property_id) == property_id,
                col(ChannelConnection.status) != DISCONNECTED,
            )
        )
    ).one()
    return ChannelQuota(used=int(used), limit=await _limit(session, context))


async def reserve_connection_slot(
    session: AsyncSession, context: TenantContext, property_id: UUID
) -> None:
    """Make sure one more connection fits. The caller holds the property's row lock."""
    quota = await read_quota(session, context, property_id)
    if quota.limit_reached:
        await session.rollback()
        raise ChannelLimitReachedError(quota)
