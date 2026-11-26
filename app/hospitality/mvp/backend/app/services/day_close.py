"""Closing and reopening business days.

A day is closed the next morning or later, never while it is still today. Closing a day
also closes the quiet days before it, back to the last closed day, each with its own
snapshot. Blocking items need a reason (and booking rights, checked by the router). A
closed day stays closed in the database unless the reopen action says otherwise; only
the latest closed day can be reopened, with a reason.
"""

import datetime as dt
import logging
from uuid import UUID

from sqlalchemy import text
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import BusinessDay, Property
from app.schemas.end_of_day import DayRead
from app.services import calendar_dates as dates_of
from app.services import cash_drawers as drawers
from app.services import closed_days, tenant_audit
from app.services import end_of_day_errors as errors
from app.services.bookings import lock_property
from app.services.closed_days import CLOSED, last_closed
from app.services.day_checks import BLOCKING, read_checks
from app.services.day_summary import read_summary
from app.services.guest_id_reads import staff_names
from app.tenancy.context import TenantContext
from app.tenancy.timezones import property_zone

log = logging.getLogger(__name__)

OPEN = "open"
ATTENDED = "attended"
ENTITY = "businessday"
MAX_DAYS_AT_ONCE = 92
SETTLE_TIME = dt.timedelta(minutes=5)  # late online payments of the day settle first


async def _row(
    session: AsyncSession, context: TenantContext, property_id: UUID, day: dt.date
) -> BusinessDay | None:
    return (
        await session.exec(
            select(BusinessDay)
            .where(
                col(BusinessDay.tenant_id) == context.tenant_id,
                col(BusinessDay.property_id) == property_id,
                col(BusinessDay.business_date) == day,
            )
            .execution_options(populate_existing=True)
        )
    ).first()


async def read_day(
    session: AsyncSession, context: TenantContext, prop: Property, day: dt.date
) -> DayRead:
    today = dates_of.property_today(prop.timezone)
    row = await _row(session, context, prop.id, day)
    closed = row is not None and row.status == CLOSED
    names = await staff_names(session, context, {row.closed_by or ""} if row else set())
    day_drawers = await drawers.drawers_of_day(session, context, prop.id, day)
    return DayRead(
        date=day,
        today=today,
        status=CLOSED if closed else OPEN,
        closed_at=row.closed_at if closed else None,
        closed_by=names.get(row.closed_by or "", row.closed_by) if closed else None,
        can_close=not closed and day < today,
        checks=[] if closed else await read_checks(session, context, prop, day),
        summary=row.stats if closed else await read_summary(session, context, prop, day),
        drawers=await drawers.read_drawers(session, context, day_drawers),
    )


def _days_to_close(latest: dt.date | None, start_of_use: dt.date, day: dt.date) -> list[dt.date]:
    """From the day after the last close (or the first day) up to `day`.

    The very first close takes at most the last `MAX_DAYS_AT_ONCE` days; after that, days
    are closed in order and a longer backlog needs support.
    """
    if latest is None:
        start = max(start_of_use, day - dt.timedelta(days=MAX_DAYS_AT_ONCE - 1))
    else:
        start = latest + dt.timedelta(days=1)
    count = (day - start).days + 1
    if count > MAX_DAYS_AT_ONCE:
        raise errors.TooManyOpenDaysError
    return [start + dt.timedelta(days=n) for n in range(count)]


def _check_closable(prop: Property, day: dt.date) -> None:
    """Only a past day, from the property's first day, and not in the first minutes
    after midnight, so that online payments of the day before have arrived."""
    if day < closed_days.first_day(prop):
        raise errors.BeforeFirstDayError
    zone = property_zone(prop.timezone)
    settled = dt.datetime.combine(day + dt.timedelta(days=1), dt.time(0), tzinfo=zone)
    if dt.datetime.now(dt.UTC) < settled + SETTLE_TIME:
        raise errors.DayNotOverError


async def _close_one(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    day: dt.date,
    checklist: list,
) -> BusinessDay:
    # Work the figures out first: once the row says closed, the database freezes it.
    stats = await read_summary(session, context, prop, day)
    row = await _row(session, context, prop.id, day) or BusinessDay(
        tenant_id=context.tenant_id, property_id=prop.id, business_date=day
    )
    row.status, row.run_mode = CLOSED, ATTENDED
    row.closed_at, row.closed_by = dt.datetime.now(dt.UTC), str(context.user_id)
    row.checklist = {"items": checklist}
    row.stats = stats
    row.error = None
    session.add(row)
    await session.flush()
    return row


async def close_day(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    day: dt.date,
    override_reason: str | None,
) -> None:
    """Close `day` (and the open days before it). Commits."""
    _check_closable(prop, day)
    await lock_property(session, context, prop.id)
    current = await _row(session, context, prop.id, day)
    if current is not None and current.status == CLOSED:
        raise errors.AlreadyClosedError
    checks = await read_checks(session, context, prop, day)
    blocking = [check for check in checks if check.level == BLOCKING]
    if blocking and not override_reason:
        raise errors.DayBlockedError([check.model_dump(mode="json") for check in checks])
    days = _days_to_close(
        await last_closed(session, context, prop.id), closed_days.first_day(prop), day
    )
    rows = [
        await _close_one(
            session,
            context,
            prop,
            d,
            [c.model_dump(mode="json") for c in checks] if d == day else [],
        )
        for d in days
    ]
    await tenant_audit.record(
        session,
        context,
        "day.closed",
        property_id=prop.id,
        entity_table=ENTITY,
        entity_id=rows[-1].id,
        payload={
            "date": day.isoformat(),
            "days_closed": len(rows),
            "blocking": [check.code for check in blocking],
            "override_reason": override_reason if blocking else None,
        },
    )
    await session.commit()
    log.info("day closed property=%s date=%s days=%d", prop.id, day, len(rows))


async def reopen_day(
    session: AsyncSession, context: TenantContext, prop: Property, day: dt.date, reason: str
) -> None:
    """Open the latest closed day again, with a reason. Commits."""
    await lock_property(session, context, prop.id)
    row = await _row(session, context, prop.id, day)
    if row is None or row.status != CLOSED:
        raise errors.NotClosedError
    if await last_closed(session, context, prop.id) != day:
        raise errors.ReopenLatestFirstError
    # The database keeps a closed day closed unless this transaction names it for reopening.
    await session.execute(
        text("SELECT set_config('app.reopen_day', :row, true)"), {"row": str(row.id)}
    )
    previous = row.stats
    row.status, row.closed_at, row.closed_by = OPEN, None, None
    session.add(row)
    await tenant_audit.record(
        session,
        context,
        "day.reopened",
        property_id=prop.id,
        entity_table=ENTITY,
        entity_id=row.id,
        payload={"date": day.isoformat(), "reason": reason, "previous_stats": previous},
    )
    await session.commit()
    log.info("day reopened property=%s date=%s", prop.id, day)
