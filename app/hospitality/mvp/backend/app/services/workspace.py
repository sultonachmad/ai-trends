"""Workspace summary: the caller's property, plan and usage.

Every query filters on `tenant_id` explicitly, on top of row-level security, so the
result is right whether the session is tenant-scoped or elevated (provisioning).
"""

import logging
from uuid import UUID

from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import settings as app_settings
from app.models.control_plane import Plan, Tenant, TenantSubscription
from app.models.tenant import (
    Conversation,
    Property,
    StaffMember,
    TransferProof,
)
from app.schemas.workspace import (
    PlanSummary,
    PropertySummary,
    StaffSummary,
    TenantSummary,
    UsageSummary,
    WorkspaceRead,
)
from app.services.link_quota import read_quota
from app.tenancy.business_settings import resolve_property_settings
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

_ACTIVE_SUBSCRIPTION_STATES = ("trialing", "active", "past_due")


class WorkspaceNotReadyError(RuntimeError):
    """The membership exists but the workspace data is incomplete."""


async def find_property(session: AsyncSession, context: TenantContext) -> Property:
    """The property the caller is working in (their last one, else the first)."""
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


async def unread_conversation_count(
    session: AsyncSession, context: TenantContext, property_id: UUID
) -> int:
    """Open conversations of the property that have unread guest messages."""
    statement = (
        select(func.count())
        .select_from(Conversation)
        .where(
            col(Conversation.tenant_id) == context.tenant_id,
            col(Conversation.property_id) == property_id,
            col(Conversation.status).not_in(("resolved", "spam")),
            col(Conversation.unread_count) > 0,
        )
    )
    return int((await session.exec(statement)).one())


async def _proofs_awaiting(session: AsyncSession, context: TenantContext, property_id: UUID) -> int:
    statement = (
        select(func.count())
        .select_from(TransferProof)
        .where(
            col(TransferProof.tenant_id) == context.tenant_id,
            col(TransferProof.property_id) == property_id,
            col(TransferProof.match_status) == "pending",
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
    prop = await find_property(session, context)
    plan = await _find_plan(session, context)
    quota = await read_quota(session, context, prop.timezone)
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
        usage=UsageSummary(
            payment_links_used=quota.used,
            payment_links_limit=quota.limit,
            payment_links_resets_at=quota.resets_at,
            payment_links_resets_on=quota.resets_on,
            payment_links_warning=quota.warning,
            payment_links_limit_reached=quota.limit_reached,
        ),
        is_owner=context.is_owner,
        staff=staff,
        settings=resolve_property_settings(prop.settings),
        unread_conversations=await unread_conversation_count(session, context, prop.id),
        proofs_awaiting_review=await _proofs_awaiting(session, context, prop.id),
        simulator_enabled=app_settings.MESSAGING_SIMULATOR_ENABLED,
    )
