"""Rooms to clean.

GET  /api/housekeeping/board                       today's tasks, rooms and staff
POST /api/housekeeping/tasks/{id}/start|done|take  work a task (housekeeping:edit)
POST /api/housekeeping/tasks/{id}/problem          report a problem (housekeeping:edit)
POST /api/housekeeping/tasks/{id}/clear-problem    the desk dealt with it (housekeeping:edit)
POST /api/housekeeping/tasks/{id}/assign|inspect   supervisors (housekeeping:manage)
POST /api/housekeeping/split                       share free rooms (housekeeping:manage)
PUT  /api/housekeeping/rooms/{id}/status           change a room by hand (housekeeping:edit)
POST /api/housekeeping/rooms/{id}/clean-request    clean an occupied room today
PUT  /api/housekeeping/settings                    readiness and stay-overs (manage)
PUT  /api/housekeeping/me/mode                     big buttons on or off

Every action answers with the fresh board, so the phone shows the result at once.
"""

import re
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.rbac.dependencies import _user_has_permission, require_permission
from app.schemas.housekeeping import (
    AssignRequest,
    HkBoard,
    HkSettingsRequest,
    InspectRequest,
    ModeRequest,
    ProblemRequest,
    RoomStatusRequest,
    SplitRequest,
)
from app.services import housekeeping_work as work
from app.services.front_desk_errors import FrontDeskError
from app.services.housekeeping_board import read_board
from app.services.housekeeping_errors import ClearPermissionError
from app.services.housekeeping_tasks import sync_day
from app.services.unit_status import MOBILE, STAFF
from app.services.workspace import find_property
from app.tenancy.context import TenantContext, get_tenant_context
from app.tenancy.session import get_tenant_session

VIEW = require_permission("housekeeping:view", "See the rooms board and cleaning tasks")
EDIT = require_permission(
    "housekeeping:edit", "Work cleaning tasks and change a room's cleaning status"
)
MANAGE = require_permission(
    "housekeeping:manage", "Assign and inspect rooms, and set housekeeping rules"
)
MANAGE_CODE = "housekeeping:manage"
DESK_CODE = "frontdesk:edit"  # the front desk deals with problems housekeepers report
PHONE = re.compile(r"Mobi|Android|iPhone|iPad", re.IGNORECASE)

T = TypeVar("T")

housekeeping_router = APIRouter(prefix="/api/housekeeping", tags=["housekeeping"])


def device_source(request: Request) -> str:
    """`mobile` from a phone or tablet, else `staff` (the desk)."""
    return MOBILE if PHONE.search(request.headers.get("user-agent", "")) else STAFF


async def _guarded(session: AsyncSession, call: Callable[[], Awaitable[T]]) -> T:
    try:
        return await call()
    except FrontDeskError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}
        ) from None


async def _then_board(
    session: AsyncSession,
    context: TenantContext,
    full_guests: bool,
    action: Callable[[Any], Awaitable[Any]],
) -> HkBoard:
    prop = await find_property(session, context)
    await _guarded(session, lambda: action(prop))
    return await read_board(session, context, prop, full_guests=full_guests)


async def _can_manage(user: dict, rbac_session: AsyncSession) -> bool:
    return await _user_has_permission(int(user["user_id"]), MANAGE_CODE, rbac_session)


async def _guest_scope(
    user=VIEW, rbac_session: AsyncSession = Depends(get_session, use_cache=False)
) -> bool:
    return await _sees_all_guests(user, rbac_session)


async def _sees_all_guests(user: dict, rbac_session: AsyncSession) -> bool:
    """Supervisors and the front desk see every room's guest; housekeepers see guest names
    and requests only for their own rooms and rooms nobody has taken yet."""
    user_id = int(user["user_id"])
    return await _user_has_permission(
        user_id, MANAGE_CODE, rbac_session
    ) or await _user_has_permission(user_id, DESK_CODE, rbac_session)


@housekeeping_router.get("/board", response_model=HkBoard)
async def board(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    rbac_session: AsyncSession = Depends(get_session, use_cache=False),
    user=VIEW,
) -> HkBoard:
    full = await _sees_all_guests(user, rbac_session)
    prop = await find_property(session, context)
    await sync_day(session, context, prop)
    return await read_board(session, context, prop, full_guests=full)


@housekeeping_router.post("/tasks/{task_id}/start", response_model=HkBoard)
async def start(
    task_id: UUID,
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    rbac_session: AsyncSession = Depends(get_session, use_cache=False),
    user=EDIT,
    full: bool = Depends(_guest_scope),
) -> HkBoard:
    manage, source = await _can_manage(user, rbac_session), device_source(request)
    return await _then_board(
        session,
        context,
        full,
        lambda prop: work.start(session, context, prop, task_id, can_manage=manage, source=source),
    )


@housekeeping_router.post("/tasks/{task_id}/done", response_model=HkBoard)
async def done(
    task_id: UUID,
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    rbac_session: AsyncSession = Depends(get_session, use_cache=False),
    user=EDIT,
    full: bool = Depends(_guest_scope),
) -> HkBoard:
    manage, source = await _can_manage(user, rbac_session), device_source(request)
    return await _then_board(
        session,
        context,
        full,
        lambda prop: work.finish(session, context, prop, task_id, can_manage=manage, source=source),
    )


@housekeeping_router.post("/tasks/{task_id}/problem", response_model=HkBoard)
async def problem(
    task_id: UUID,
    body: ProblemRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    rbac_session: AsyncSession = Depends(get_session, use_cache=False),
    user=EDIT,
    full: bool = Depends(_guest_scope),
) -> HkBoard:
    manage = await _can_manage(user, rbac_session)
    return await _then_board(
        session,
        context,
        full,
        lambda prop: work.report_problem(session, context, prop, task_id, body, can_manage=manage),
    )


@housekeeping_router.post("/tasks/{task_id}/take", response_model=HkBoard)
async def take(
    task_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
    full: bool = Depends(_guest_scope),
) -> HkBoard:
    return await _then_board(
        session, context, full, lambda prop: work.take(session, context, prop, task_id)
    )


@housekeeping_router.post("/tasks/{task_id}/clear-problem", response_model=HkBoard)
async def clear_problem(
    task_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    rbac_session: AsyncSession = Depends(get_session, use_cache=False),
    user=EDIT,
    full: bool = Depends(_guest_scope),
) -> HkBoard:
    user_id = int(user["user_id"])
    if not (
        await _user_has_permission(user_id, DESK_CODE, rbac_session)
        or await _user_has_permission(user_id, MANAGE_CODE, rbac_session)
    ):
        error = ClearPermissionError()
        raise HTTPException(
            status_code=error.status_code, detail={"code": error.code, "message": error.message}
        )
    return await _then_board(
        session, context, full, lambda prop: work.clear_problem(session, context, prop, task_id)
    )


@housekeeping_router.post("/tasks/{task_id}/assign", response_model=HkBoard)
async def assign(
    task_id: UUID,
    body: AssignRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _manage=MANAGE,
    full: bool = Depends(_guest_scope),
) -> HkBoard:
    return await _then_board(
        session,
        context,
        full,
        lambda prop: work.assign(session, context, prop, task_id, body.staff_id),
    )


@housekeeping_router.post("/tasks/{task_id}/inspect", response_model=HkBoard)
async def inspect(
    task_id: UUID,
    body: InspectRequest,
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _manage=MANAGE,
    full: bool = Depends(_guest_scope),
) -> HkBoard:
    source = device_source(request)
    return await _then_board(
        session,
        context,
        full,
        lambda prop: work.inspect(session, context, prop, task_id, body, source=source),
    )


@housekeeping_router.post("/split", response_model=HkBoard)
async def split(
    body: SplitRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _manage=MANAGE,
    full: bool = Depends(_guest_scope),
) -> HkBoard:
    return await _then_board(
        session,
        context,
        full,
        lambda prop: work.split_evenly(session, context, prop, body.staff_ids),
    )


@housekeeping_router.put("/rooms/{unit_id}/status", response_model=HkBoard)
async def room_status(
    unit_id: UUID,
    body: RoomStatusRequest,
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    rbac_session: AsyncSession = Depends(get_session, use_cache=False),
    user=EDIT,
    full: bool = Depends(_guest_scope),
) -> HkBoard:
    manage, source = await _can_manage(user, rbac_session), device_source(request)
    return await _then_board(
        session,
        context,
        full,
        lambda prop: work.set_room_status(
            session, context, prop, unit_id, body.hk_status, can_manage=manage, source=source
        ),
    )


@housekeeping_router.post("/rooms/{unit_id}/clean-request", response_model=HkBoard)
async def clean_request(
    unit_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
    full: bool = Depends(_guest_scope),
) -> HkBoard:
    return await _then_board(
        session, context, full, lambda prop: work.request_clean(session, context, prop, unit_id)
    )


@housekeeping_router.put("/settings", response_model=HkBoard)
async def settings(
    body: HkSettingsRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _manage=MANAGE,
    full: bool = Depends(_guest_scope),
) -> HkBoard:
    return await _then_board(
        session,
        context,
        full,
        lambda prop: work.save_settings(session, prop, body.ready_when, body.stayover),
    )


@housekeeping_router.put("/me/mode", response_model=HkBoard)
async def mode(
    body: ModeRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
    full: bool = Depends(_guest_scope),
) -> HkBoard:
    return await _then_board(
        session,
        context,
        full,
        lambda _prop: work.set_big_buttons(session, context, body.big_buttons),
    )
