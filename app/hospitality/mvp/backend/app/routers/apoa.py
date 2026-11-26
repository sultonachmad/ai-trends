"""Foreign guests and APOA (Imigrasi) reporting.

GET  /api/apoa                  to report, to check out, done, guests not registered
POST /api/apoa/marks            checked in to / out of APOA (optional receipt reference)
POST /api/apoa/not-required     this step does not apply, with a reason
POST /api/apoa/undo             take back a mark, with a reason
GET  /api/apoa/register         CSV register for an immigration officer (masked)

The passport photo for APOA's manual check-in is the guest ID photo route, which needs
guestid:edit and is logged.
"""

import datetime as dt
from collections.abc import Awaitable, Callable
from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Property
from app.rbac.dependencies import require_permission
from app.schemas.apoa import ApoaList, MarkRequest, ReasonRequest
from app.services import apoa, apoa_reads, apoa_register
from app.services import calendar_dates as dates_of
from app.services.front_desk_errors import FrontDeskError
from app.services.workspace import find_property
from app.tenancy.context import TenantContext, get_tenant_context
from app.tenancy.session import get_tenant_session

VIEW = require_permission("apoa:view", "See which foreign guests still need reporting to APOA")

EDIT = require_permission("apoa:edit", "Record APOA check-ins and check-outs of foreign guests")

T = TypeVar("T")
NO_STORE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}


def _no_store(response: Response) -> None:
    """Guest names and passport details must not be kept by browsers or proxies."""
    response.headers.update(NO_STORE)


apoa_router = APIRouter(prefix="/api/apoa", tags=["apoa"], dependencies=[Depends(_no_store)])


async def _guarded(session: AsyncSession, call: Callable[[], Awaitable[T]]) -> T:
    try:
        return await call()
    except FrontDeskError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}
        ) from None


async def _then_list(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    change: Callable[[], Awaitable[None]],
) -> ApoaList:
    async def run() -> ApoaList:
        await change()
        return await apoa_reads.read_worklist(session, context, prop)

    return await _guarded(session, run)


@apoa_router.get("", response_model=ApoaList)
async def worklist(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
) -> ApoaList:
    prop = await find_property(session, context)
    return await apoa_reads.read_worklist(session, context, prop)


@apoa_router.post("/marks", response_model=ApoaList)
async def mark(
    body: MarkRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> ApoaList:
    prop = await find_property(session, context)
    return await _then_list(session, context, prop, lambda: apoa.mark(session, context, prop, body))


@apoa_router.post("/not-required", response_model=ApoaList)
async def not_required(
    body: ReasonRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> ApoaList:
    prop = await find_property(session, context)
    return await _then_list(
        session, context, prop, lambda: apoa.not_required(session, context, prop, body)
    )


@apoa_router.post("/undo", response_model=ApoaList)
async def undo(
    body: ReasonRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> ApoaList:
    prop = await find_property(session, context)
    return await _then_list(session, context, prop, lambda: apoa.undo(session, context, prop, body))


@apoa_router.get("/register")
async def register(
    start: dt.date | None = Query(default=None, alias="from"),
    end: dt.date | None = Query(default=None, alias="to"),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
) -> Response:
    prop = await find_property(session, context)
    today = dates_of.property_today(prop.timezone)
    start, end = start or today.replace(day=1), end or today
    text = await _guarded(
        session, lambda: apoa_register.register_csv(session, context, prop, start, end)
    )
    name = f"apoa-register-{start.isoformat()}-{end.isoformat()}.csv"
    return Response(
        content=text,
        media_type="text/csv; charset=utf-8",
        headers={**NO_STORE, "Content-Disposition": f'attachment; filename="{name}"'},
    )
