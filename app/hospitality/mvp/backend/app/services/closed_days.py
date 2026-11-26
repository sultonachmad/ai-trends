"""Which business days are closed. A closed day's money cannot change.

Used by every writer of money with a date (desk payments, removals, refunds). Bill lines
are always dated today, and today is never closed, so they need no check.
"""

import datetime as dt
from uuid import UUID

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import BusinessDay, Property
from app.services import end_of_day_errors as errors
from app.tenancy.context import TenantContext
from app.tenancy.timezones import property_zone

CLOSED = "closed"


async def is_closed(
    session: AsyncSession, context: TenantContext, property_id: UUID, day: dt.date
) -> bool:
    found = await session.exec(
        select(BusinessDay.id).where(
            col(BusinessDay.tenant_id) == context.tenant_id,
            col(BusinessDay.property_id) == property_id,
            col(BusinessDay.business_date) == day,
            col(BusinessDay.status) == CLOSED,
        )
    )
    return found.first() is not None


async def ensure_open(
    session: AsyncSession, context: TenantContext, property_id: UUID, day: dt.date
) -> None:
    """Refuse a change of money dated on a closed day."""
    if await is_closed(session, context, property_id, day):
        raise errors.DayClosedError


async def last_closed(
    session: AsyncSession, context: TenantContext, property_id: UUID
) -> dt.date | None:
    found = await session.exec(
        select(func.max(col(BusinessDay.business_date))).where(
            col(BusinessDay.tenant_id) == context.tenant_id,
            col(BusinessDay.property_id) == property_id,
            col(BusinessDay.status) == CLOSED,
        )
    )
    return found.one()


def first_day(prop: Property) -> dt.date:
    """The property's first business day: the day it was created, at the property."""
    return prop.created_at.astimezone(property_zone(prop.timezone)).date()


async def oldest_unclosed(
    session: AsyncSession, context: TenantContext, prop: Property, today: dt.date
) -> dt.date | None:
    """The first past day not closed yet: after the last close, else the first day."""
    latest = await last_closed(session, context, prop.id)
    candidate = latest + dt.timedelta(days=1) if latest else first_day(prop)
    return candidate if candidate < today else None
