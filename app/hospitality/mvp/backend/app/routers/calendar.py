"""Calendar routes.

GET  /api/calendar?from=&to=      availability, closed dates, minimum stay, prices
POST /api/calendar/changes        one change to a date range and room types
"""

import datetime as dt
from collections.abc import Awaitable, Callable
from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.routers.rate_plans import rate_out_of_range
from app.schemas.calendar import CalendarChangeRequest, CalendarChangeResult, CalendarRead
from app.services import calendar
from app.services import calendar_dates as dates_of
from app.services.rate_plans import RateOutOfRangeError
from app.services.workspace import find_property
from app.tenancy.context import TenantContext, get_tenant_context
from app.tenancy.session import get_tenant_session

calendar_router = APIRouter(prefix="/api/calendar", tags=["calendar"])

T = TypeVar("T")
UNPROCESSABLE = status.HTTP_422_UNPROCESSABLE_ENTITY

_MESSAGES: dict[type[Exception], str] = {
    dates_of.RangeReversedError: "The end date is before the start date.",
    dates_of.PastDateError: "Past dates cannot be changed.",
    calendar.NothingToChangeError: "No dates in this range fall on the chosen weekdays.",
    calendar.ChangeTooLargeError: (
        "This change covers too many dates and room types at once. Split it into smaller ones."
    ),
    calendar.UnknownRoomTypeError: "A room type does not exist or is switched off.",
    calendar.UnknownRatePlanError: "The rate plan does not exist or is switched off.",
    calendar.PlanDoesNotSellRoomError: "This rate plan does not sell every chosen room type.",
}


async def _guarded(call: Callable[[], Awaitable[T]]) -> T:
    """Run a calendar service call, turning its domain errors into HTTP answers."""
    try:
        return await call()
    except dates_of.BeyondHorizonError as exc:
        raise HTTPException(
            status_code=UNPROCESSABLE,
            detail=f"Dates after {exc.last_date.isoformat()} cannot be changed yet.",
        ) from None
    except dates_of.RangeTooLongError as exc:
        raise HTTPException(
            status_code=UNPROCESSABLE,
            detail=f"A date range can cover at most {exc.max_days} days.",
        ) from None
    except RateOutOfRangeError as exc:
        raise rate_out_of_range(exc) from None
    except tuple(_MESSAGES) as exc:
        raise HTTPException(status_code=UNPROCESSABLE, detail=_MESSAGES[type(exc)]) from None


@calendar_router.get("", response_model=CalendarRead)
async def read_calendar(
    start: dt.date = Query(alias="from"),
    end: dt.date = Query(alias="to"),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> CalendarRead:
    prop = await find_property(session, context)
    return await _guarded(lambda: calendar.read_calendar(session, context, prop, start, end))


@calendar_router.post("/changes", response_model=CalendarChangeResult)
async def change_calendar(
    body: CalendarChangeRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> CalendarChangeResult:
    prop = await find_property(session, context)
    applied = await _guarded(lambda: calendar.apply_calendar_change(session, context, prop, body))
    return CalendarChangeResult(dates=len(applied.dates), room_types=len(applied.room_type_ids))
