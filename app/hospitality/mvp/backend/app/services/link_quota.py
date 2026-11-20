"""The plan's monthly payment-link limit: what staff are shown and what is enforced.

One function (`read_quota`) feeds both the workspace summary and the check made when a
link is created, so the screen and the refusal can never disagree.

Every link created in the calendar month counts, whatever became of it: a cancelled or
expired link still used a slot, otherwise create-then-cancel would get around the limit.
The month is the property's local calendar month.

The count relies on links never being deleted. If a delete or purge of payment links is
ever added, count from a separate usage record instead, or the limit reopens.
"""

import datetime as dt
import logging
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, text
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.control_plane import TenantEntitlement
from app.models.tenant import PaymentLink
from app.tenancy.business_settings import PlanLimits, resolve_plan_limits
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

PAYMENTS_MODULE = "payments"
# Payments not enabled for the tenant: no links at all.
NO_PAYMENTS_MODULE = PlanLimits(payment_links_per_month=0)
PERCENT = 100
DAYS_INTO_NEXT_MONTH = 32  # from the 1st, always lands in the following month

# Serialises link creation per tenant, so two requests cannot both take the last slot.
# The limit itself lives in a control-plane row the app role may only read, which
# therefore cannot be row-locked; an advisory lock needs no privilege on it.
_LOCK_QUOTA = text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))")


class PaymentLinkLimitReachedError(Exception):
    """This month's payment links are used up (or the plan allows none)."""

    def __init__(self, quota: "LinkQuota") -> None:
        super().__init__(f"payment link limit reached ({quota.used}/{quota.limit})")
        self.quota = quota


@dataclass(frozen=True)
class LinkQuota:
    """Links used this month against the plan limit (`limit` None = unlimited)."""

    used: int
    limit: int | None
    warning_percent: int
    resets_at: dt.datetime
    resets_on: dt.date  # the same moment as a calendar date in the property's timezone

    @property
    def limit_reached(self) -> bool:
        return self.limit is not None and self.used >= self.limit

    @property
    def warning(self) -> bool:
        """Close to the limit but not there yet."""
        if self.limit is None or self.limit_reached:
            return False
        return self.used * PERCENT >= self.limit * self.warning_percent


def _zone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        log.warning("Unknown property timezone %r; counting the month in UTC", timezone_name)
        return ZoneInfo("UTC")


def month_start_utc(now: dt.datetime, timezone_name: str) -> dt.datetime:
    """Start of the current calendar month in the property's timezone, as UTC."""
    local = now.astimezone(_zone(timezone_name))
    return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(dt.UTC)


def next_month_start_utc(now: dt.datetime, timezone_name: str) -> dt.datetime:
    """Start of the next calendar month in the property's timezone, as UTC."""
    local = now.astimezone(_zone(timezone_name))
    first = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    in_next_month = first + dt.timedelta(days=DAYS_INTO_NEXT_MONTH)
    # rebuild from the calendar date so a daylight-saving change cannot shift the hour
    start = dt.datetime(in_next_month.year, in_next_month.month, 1, tzinfo=local.tzinfo)
    return start.astimezone(dt.UTC)


async def plan_limits(session: AsyncSession, context: TenantContext) -> PlanLimits:
    """This tenant's payments limits; a tenant without the module gets no links."""
    entitlement = (
        await session.exec(
            select(TenantEntitlement).where(
                col(TenantEntitlement.tenant_id) == context.tenant_id,
                col(TenantEntitlement.module_code) == PAYMENTS_MODULE,
                col(TenantEntitlement.enabled).is_(True),
            )
        )
    ).first()
    if entitlement is None:
        return NO_PAYMENTS_MODULE
    return resolve_plan_limits(entitlement.limits)


async def payment_links_used_this_month(
    session: AsyncSession, context: TenantContext, timezone_name: str
) -> int:
    since = month_start_utc(dt.datetime.now(dt.UTC), timezone_name)
    statement = (
        select(func.count())
        .select_from(PaymentLink)
        .where(
            col(PaymentLink.tenant_id) == context.tenant_id,
            col(PaymentLink.created_at) >= since,
        )
    )
    return int((await session.exec(statement)).one())


async def read_quota(
    session: AsyncSession, context: TenantContext, timezone_name: str
) -> LinkQuota:
    limits = await plan_limits(session, context)
    resets_at = next_month_start_utc(dt.datetime.now(dt.UTC), timezone_name)
    return LinkQuota(
        used=await payment_links_used_this_month(session, context, timezone_name),
        limit=limits.payment_links_per_month,
        warning_percent=limits.usage_warning_percent,
        resets_at=resets_at,
        resets_on=resets_at.astimezone(_zone(timezone_name)).date(),
    )


async def reserve_link_slot(
    session: AsyncSession, context: TenantContext, timezone_name: str
) -> LinkQuota:
    """Make sure one more link fits this month; call in the transaction that inserts it.

    Holds a per-tenant lock until that transaction ends, so the count read here stays
    true until the new link is committed.
    """
    await session.execute(_LOCK_QUOTA, {"key": f"payment-link-quota:{context.tenant_id}"})
    quota = await read_quota(session, context, timezone_name)
    if quota.limit_reached:
        await session.rollback()  # release the lock; nothing was written
        log.info("Payment link refused: limit reached used=%s limit=%s", quota.used, quota.limit)
        raise PaymentLinkLimitReachedError(quota)
    return quota
