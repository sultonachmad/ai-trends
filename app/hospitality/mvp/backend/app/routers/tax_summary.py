"""The monthly tax summary (owner and manager).

GET /api/tax-summary/{YYYY-MM}                  by day and by booking, totals, DRAFT state
GET /api/tax-summary/{YYYY-MM}/days.csv         spreadsheet file by day (in the history)
GET /api/tax-summary/{YYYY-MM}/bookings.csv     spreadsheet file by booking (in the history)
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.rbac.dependencies import require_permission
from app.schemas.tax_summary import TaxMonth
from app.services import tax_export, tax_summary
from app.services.workspace import find_property
from app.tenancy.context import TenantContext, get_tenant_context
from app.tenancy.session import get_tenant_session

VIEW = require_permission("taxes:view", "See and download the monthly tax summary")
NO_STORE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
FIRST_YEAR = 2000

Month = Annotated[str, Path(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]

tax_summary_router = APIRouter(prefix="/api/tax-summary", tags=["tax-summary"])


def _check(month: str) -> None:
    if int(month[:4]) < FIRST_YEAR:
        raise HTTPException(
            status_code=422, detail={"code": "bad_month", "message": "Choose a month from 2000."}
        )


@tax_summary_router.get("/{month}", response_model=TaxMonth)
async def read_month(
    month: Month,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
) -> TaxMonth:
    _check(month)
    prop = await find_property(session, context)
    return await tax_summary.read_month(session, context, prop, month)


@tax_summary_router.get("/{month}/{kind}.csv")
async def download(
    month: Month,
    kind: Literal["days", "bookings"],
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
) -> Response:
    _check(month)
    prop = await find_property(session, context)
    content = await tax_export.export(session, context, prop, month, kind)
    name = f"tax-{month}-{kind}.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={**NO_STORE, "Content-Disposition": f'attachment; filename="{name}"'},
    )
