"""Your own cash drawer.

GET  /api/cash-drawers/mine             the open drawer and its totals, or none
POST /api/cash-drawers/mine/open        open with a float
POST /api/cash-drawers/mine/paid-outs   petty cash taken out, with a reason
POST /api/cash-drawers/mine/close       count the cash and close

Drawers belong to the people who take payments, so they need bills:edit.
"""

from collections.abc import Awaitable, Callable
from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.rbac.dependencies import require_permission
from app.schemas.end_of_day import (
    CloseDrawerRequest,
    DrawerRead,
    MyDrawer,
    OpenDrawerRequest,
    PaidOutRequest,
)
from app.services import cash_drawers as drawers
from app.services.front_desk_errors import FrontDeskError
from app.services.workspace import find_property
from app.tenancy.context import TenantContext, get_tenant_context
from app.tenancy.session import get_tenant_session

EDIT = require_permission("bills:edit", "Add charges, discounts and payments to guest bills")

T = TypeVar("T")

cash_drawers_router = APIRouter(prefix="/api/cash-drawers", tags=["cash-drawers"])


async def _guarded(session: AsyncSession, call: Callable[[], Awaitable[T]]) -> T:
    try:
        return await call()
    except FrontDeskError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}
        ) from None


@cash_drawers_router.get("/mine", response_model=MyDrawer)
async def mine(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> MyDrawer:
    prop = await find_property(session, context)
    return MyDrawer(drawer=await drawers.read_mine(session, context, prop))


@cash_drawers_router.post("/mine/open", response_model=DrawerRead)
async def open_drawer(
    body: OpenDrawerRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> DrawerRead:
    prop = await find_property(session, context)
    return await _guarded(
        session, lambda: drawers.open_drawer(session, context, prop, body.opening_float)
    )


@cash_drawers_router.post("/mine/paid-outs", response_model=DrawerRead)
async def paid_out(
    body: PaidOutRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> DrawerRead:
    prop = await find_property(session, context)
    return await _guarded(
        session, lambda: drawers.paid_out(session, context, prop, body.amount, body.reason)
    )


@cash_drawers_router.post("/mine/close", response_model=DrawerRead)
async def close_drawer(
    body: CloseDrawerRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> DrawerRead:
    prop = await find_property(session, context)
    return await _guarded(
        session,
        lambda: drawers.close_drawer(session, context, prop, body.counted_cash, body.note),
    )
