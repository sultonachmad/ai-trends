"""Which tenant a signed-in request acts for."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models.control_plane import Tenant, TenantMembership
from app.session.dependencies import get_current_user

# A tenant in one of these states cannot be worked in.
_CLOSED_TENANT_STATES = ("suspended", "cancelled", "deleted")
NO_WORKSPACE_DETAIL = "This account has no workspace yet"


@dataclass(frozen=True)
class TenantContext:
    """The caller's active membership."""

    tenant_id: UUID
    user_id: int
    email: str
    is_owner: bool
    staff_member_id: UUID | None
    last_property_id: UUID | None


async def find_tenant_context(
    session: AsyncSession, user_id: int, email: str
) -> TenantContext | None:
    """The user's active membership, oldest first (one workspace per account for now)."""
    statement = (
        select(TenantMembership)
        .join(Tenant, col(Tenant.id) == col(TenantMembership.tenant_id))
        .where(
            col(TenantMembership.user_id) == user_id,
            col(TenantMembership.status) == "active",
            col(Tenant.status).not_in(_CLOSED_TENANT_STATES),
        )
        .order_by(col(TenantMembership.created_at))
        .limit(1)
    )
    membership = (await session.exec(statement)).first()
    if membership is None:
        return None
    return TenantContext(
        tenant_id=membership.tenant_id,
        user_id=user_id,
        email=email,
        is_owner=membership.is_tenant_owner,
        staff_member_id=membership.staff_member_id,
        last_property_id=membership.last_property_id,
    )


async def get_tenant_context(
    user: dict[str, Any] = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TenantContext:
    """FastAPI dependency: the caller's tenant, or 403 when they have none."""
    context = await find_tenant_context(session, int(user["user_id"]), str(user.get("email", "")))
    if context is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=NO_WORKSPACE_DETAIL)
    return context
