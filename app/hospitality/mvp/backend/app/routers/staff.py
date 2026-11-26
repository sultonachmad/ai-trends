"""The team and join links.

GET  /api/staff                         members and open join links (staff:view)
POST /api/staff/invites                 make a join link (staff:edit)
POST /api/staff/invites/{id}/revoke     cancel a join link (staff:edit)
PUT  /api/staff/{staff_id}/role         change a member's role (staff:edit)
POST /api/staff/{staff_id}/remove       remove a member (staff:edit)
GET  /api/join/{token}                  what a join link is for (public)
POST /api/join/{token}                  join with the signed-in account

Memberships and invitations are control-plane rows, so these routes use the unscoped
session; the services name the tenant in every query.
"""

from collections.abc import Awaitable, Callable
from typing import Annotated, Any, TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.rbac.dependencies import require_permission
from app.schemas.staff import (
    InviteCreated,
    InviteRequest,
    JoinPreview,
    JoinResult,
    RoleRequest,
    TeamRead,
)
from app.services import staff_invites, staff_team
from app.services.front_desk_errors import FrontDeskError
from app.services.workspace import find_property
from app.session.dependencies import get_current_user
from app.tenancy.context import TenantContext, get_tenant_context

VIEW = require_permission("staff:view", "See the team and open join links")
EDIT = require_permission("staff:edit", "Invite staff, change their role and remove them")

Token = Annotated[str, Path(min_length=20, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")]

T = TypeVar("T")

staff_router = APIRouter(prefix="/api/staff", tags=["staff"])
join_router = APIRouter(prefix="/api/join", tags=["staff"])


async def _guarded(session: AsyncSession, call: Callable[[], Awaitable[T]]) -> T:
    try:
        return await call()
    except FrontDeskError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}
        ) from None


@staff_router.get("", response_model=TeamRead)
async def team(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_session),
    _view=VIEW,
) -> TeamRead:
    return await staff_team.read_team(session, context)


@staff_router.post("/invites", response_model=InviteCreated)
async def invite(
    body: InviteRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_session),
    _edit=EDIT,
) -> InviteCreated:
    prop = await find_property(session, context)
    return await _guarded(session, lambda: staff_invites.invite(session, context, prop, body))


@staff_router.post("/invites/{invite_id}/revoke", response_model=TeamRead)
async def revoke(
    invite_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_session),
    _edit=EDIT,
) -> TeamRead:
    prop = await find_property(session, context)
    await _guarded(session, lambda: staff_invites.revoke(session, context, prop, invite_id))
    return await staff_team.read_team(session, context)


@staff_router.put("/{staff_id}/role", response_model=TeamRead)
async def change_role(
    staff_id: UUID,
    body: RoleRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_session),
    _edit=EDIT,
) -> TeamRead:
    prop = await find_property(session, context)
    await _guarded(
        session, lambda: staff_team.change_role(session, context, prop, staff_id, body.role)
    )
    return await staff_team.read_team(session, context)


@staff_router.post("/{staff_id}/remove", response_model=TeamRead)
async def remove(
    staff_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_session),
    _edit=EDIT,
) -> TeamRead:
    prop = await find_property(session, context)
    await _guarded(session, lambda: staff_team.remove(session, context, prop, staff_id))
    return await staff_team.read_team(session, context)


@join_router.get("/{token}", response_model=JoinPreview)
async def preview(token: Token, session: AsyncSession = Depends(get_session)) -> JoinPreview:
    return await _guarded(session, lambda: staff_invites.preview(session, token))


@join_router.post("/{token}", response_model=JoinResult)
async def join(
    token: Token,
    user: dict[str, Any] = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> JoinResult:
    return await _guarded(session, lambda: staff_invites.join(session, int(user["user_id"]), token))
