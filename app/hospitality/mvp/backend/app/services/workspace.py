"""Workspace summary: the caller's property, plan and usage.

Every query filters on `tenant_id` explicitly, on top of row-level security, so the
result is right whether the session is tenant-scoped or elevated (provisioning).
"""

import datetime as dt
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.control_plane import Plan, Tenant, TenantEntitlement, TenantSubscription
from app.models.tenant import PaymentLink, Property, StaffMember
from app.schemas.workspace import (
    PlanSummary,
    PropertySummary,
    StaffSummary,
    TenantSummary,
    UsageSummary,
    WorkspaceRead,
)
from app.tenancy.business_settings import resolve_plan_limits, resolve_property_settings
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

PAYMENTS_MODULE = "payments"
NO_PAYMENTS_MODULE_LIMIT = 0  # payments not enabled for the tenant: no links at all
_ACTIVE_SUBSCRIPTION_STATES = ("trialing", "active", "past_due")


class WorkspaceNotReadyError(RuntimeError):
    """The membership exists but the workspace data is incomplete."""


def month_start_utc(now: dt.datetime, timezone_name: str) -> dt.datetime:
    """Start of the current calendar month in the property's timezone, as UTC."""
    try:
        zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        log.warning("Unknown property timezone %r; counting the month in UTC", timezone_name)
        zone = ZoneInfo("UTC")
    local = now.astimezone(zone)
    return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(dt.UTC)


async def _find_property(session: AsyncSession, context: TenantContext) -> Property:
    statement = select(Property).where(col(Property.tenant_id) == context.tenant_id)
    if context.last_property_id is not None:
        preferred = (
            await session.exec(statement.where(col(Property.id) == context.last_property_id))
        ).first()
        if preferred is not None:
            return preferred
    first = (await session.exec(statement.order_by(col(Property.created_at)).limit(1))).first()
    if first is None:
        raise WorkspaceNotReadyError("workspace has no property")
    return first


async def _find_plan(session: AsyncSession, context: TenantContext) -> Plan:
    statement = (
        select(Plan)
        .join(TenantSubscription, col(TenantSubscription.plan_id) == col(Plan.id))
        .where(
            col(TenantSubscription.tenant_id) == context.tenant_id,
            col(TenantSubscription.status).in_(_ACTIVE_SUBSCRIPTION_STATES),
        )
        .order_by(col(TenantSubscription.started_on).desc())
        .limit(1)
    )
    plan = (await session.exec(statement)).first()
    if plan is None:
        raise WorkspaceNotReadyError("workspace has no active subscription")
    return plan


async def payment_link_limit(session: AsyncSession, context: TenantContext) -> int | None:
    """This tenant's monthly payment-link limit (None = unlimited)."""
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
        return NO_PAYMENTS_MODULE_LIMIT
    return resolve_plan_limits(entitlement.limits).payment_links_per_month


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


async def _find_staff(session: AsyncSession, context: TenantContext) -> StaffSummary:
    staff = None
    if context.staff_member_id is not None:
        staff = (
            await session.exec(
                select(StaffMember).where(
                    col(StaffMember.tenant_id) == context.tenant_id,
                    col(StaffMember.id) == context.staff_member_id,
                )
            )
        ).first()
    if staff is None:
        return StaffSummary(display_name=context.email, email=context.email or None)
    return StaffSummary(display_name=staff.display_name, email=staff.email)


async def get_workspace(session: AsyncSession, context: TenantContext) -> WorkspaceRead:
    """Assemble the workspace summary for `context`."""
    tenant = (await session.exec(select(Tenant).where(col(Tenant.id) == context.tenant_id))).one()
    prop = await _find_property(session, context)
    plan = await _find_plan(session, context)
    used = await payment_links_used_this_month(session, context, prop.timezone)
    limit = await payment_link_limit(session, context)
    staff = await _find_staff(session, context)
    return WorkspaceRead(
        tenant=TenantSummary(id=tenant.id, code=tenant.code, name=tenant.name),
        property=PropertySummary(
            id=prop.id,
            code=prop.code,
            name=prop.name,
            property_type=prop.property_type,
            city=(prop.address or {}).get("city"),
            timezone=prop.timezone,
            currency=prop.currency,
        ),
        plan=PlanSummary(code=plan.code, name=plan.name),
        usage=UsageSummary(payment_links_used=used, payment_links_limit=limit),
        is_owner=context.is_owner,
        staff=staff,
        settings=resolve_property_settings(prop.settings),
    )
