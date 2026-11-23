"""Reports.

GET /api/reports/channels?from=&to=   production by booking source for a period
"""

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.rbac.dependencies import require_permission
from app.schemas.reports import ChannelReport
from app.services import channel_report
from app.services.calendar_dates import CalendarDateError, RangeReversedError
from app.services.workspace import find_property
from app.tenancy.context import TenantContext, get_tenant_context
from app.tenancy.session import get_tenant_session

VIEW = require_permission("reports:view", "See revenue and channel reports")

reports_router = APIRouter(prefix="/api/reports", tags=["reports"])


@reports_router.get("/channels", response_model=ChannelReport)
async def channels_report(
    start: dt.date = Query(alias="from"),
    end: dt.date = Query(alias="to"),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view: dict = VIEW,
) -> ChannelReport:
    prop = await find_property(session, context)
    try:
        return await channel_report.read_report(session, context, prop, start, end)
    except RangeReversedError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "The end date is before the start date."
        ) from None
    except CalendarDateError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Choose a period of at most {channel_report.MAX_REPORT_DAYS} days.",
        ) from None
