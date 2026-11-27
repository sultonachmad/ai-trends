"""Rooms off sale (an active `unitblock`), as the front desk and room assignment see them.

A block covers whole nights. It uses the same check-in and check-out times as a stay,
so a guest leaving on the morning of the first night, or arriving the afternoon after the
last, does not collide with it.
"""

import datetime as dt
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import UnitBlock
from app.services.booking_stays import CHECK_IN_TIME, CHECK_OUT_TIME
from app.tenancy.context import TenantContext
from app.tenancy.timezones import property_zone

ACTIVE = "active"


def night_window(first: dt.date, last: dt.date, timezone: str) -> tuple[dt.datetime, dt.datetime]:
    """From check-in on the first night to check-out after the last, in UTC."""
    zone = property_zone(timezone)
    start = dt.datetime.combine(first, CHECK_IN_TIME, tzinfo=zone)
    end = dt.datetime.combine(last + dt.timedelta(days=1), CHECK_OUT_TIME, tzinfo=zone)
    return start.astimezone(dt.UTC), end.astimezone(dt.UTC)


def nights_of(block: UnitBlock, timezone: str) -> tuple[dt.date, dt.date]:
    """The first and last night a block covers."""
    zone = property_zone(timezone)
    first = block.start_at.astimezone(zone).date()
    last = block.end_at.astimezone(zone).date() - dt.timedelta(days=1)
    return first, last


async def blocked_unit_ids(
    session: AsyncSession,
    context: TenantContext,
    unit_ids: list[UUID],
    start_at: dt.datetime,
    end_at: dt.datetime,
) -> set[UUID]:
    """Which of these rooms are off sale for any part of this time."""
    if not unit_ids:
        return set()
    rows = await session.exec(
        select(col(UnitBlock.unit_id)).where(
            col(UnitBlock.tenant_id) == context.tenant_id,
            col(UnitBlock.unit_id).in_(unit_ids),
            col(UnitBlock.status) == ACTIVE,
            col(UnitBlock.start_at) < end_at,
            col(UnitBlock.end_at) > start_at,
        )
    )
    return set(rows.all())
