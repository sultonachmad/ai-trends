"""Closing business days.

GET  /api/end-of-day/days/{date}          checklist, summary (frozen once closed), drawers
POST /api/end-of-day/days/{date}/close    close it (and the open days before it)
POST /api/end-of-day/days/{date}/reopen   open the latest closed day again, with a reason
"""

import datetime as dt
from collections.abc import Awaitable, Callable
from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.rbac.dependencies import _user_has_permission, require_permission
from app.schemas.end_of_day import CloseDayRequest, DayRead, ReopenDayRequest
from app.services import day_close
from app.services.end_of_day_errors import DayBlockedError, OverridePermissionError
from app.services.front_desk_errors import FrontDeskError
from app.services.workspace import find_property
from app.tenancy.context import TenantContext, get_tenant_context
from app.tenancy.session import get_tenant_session

VIEW = require_permission("endofday:view", "See the day's summary, checklist and cash drawers")

EDIT = require_permission("endofday:edit", "Close and reopen business days")

BOOKING_EDIT = "bookings:edit"  # closing past blocking items needs booking rights

T = TypeVar("T")

end_of_day_router = APIRouter(prefix="/api/end-of-day", tags=["end-of-day"])


def _refused(exc: FrontDeskError) -> HTTPException:
    detail: dict = {"code": exc.code, "message": exc.message}
    if isinstance(exc, DayBlockedError):
        detail["checks"] = exc.checks
    return HTTPException(status_code=exc.status_code, detail=detail)


async def _guarded(session: AsyncSession, call: Callable[[], Awaitable[T]]) -> T:
    try:
        return await call()
    except FrontDeskError as exc:
        await session.rollback()
        raise _refused(exc) from None


@end_of_day_router.get("/days/{day}", response_model=DayRead)
async def read_day(
    day: dt.date,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
) -> DayRead:
    prop = await find_property(session, context)
    return await day_close.read_day(session, context, prop, day)


@end_of_day_router.post("/days/{day}/close", response_model=DayRead)
async def close_day(
    day: dt.date,
    body: CloseDayRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    rbac_session: AsyncSession = Depends(get_session, use_cache=False),
    user: dict = EDIT,
) -> DayRead:
    if body.override_reason is not None and not await _user_has_permission(
        int(user["user_id"]), BOOKING_EDIT, rbac_session
    ):
        raise _refused(OverridePermissionError())
    prop = await find_property(session, context)

    async def run() -> DayRead:
        await day_close.close_day(session, context, prop, day, body.override_reason)
        return await day_close.read_day(session, context, prop, day)

    return await _guarded(session, run)


@end_of_day_router.post("/days/{day}/reopen", response_model=DayRead)
async def reopen_day(
    day: dt.date,
    body: ReopenDayRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> DayRead:
    prop = await find_property(session, context)

    async def run() -> DayRead:
        await day_close.reopen_day(session, context, prop, day, body.reason)
        return await day_close.read_day(session, context, prop, day)

    return await _guarded(session, run)
