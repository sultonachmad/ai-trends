"""The direct booking page.

Staff:   GET / PUT /api/booking-page
Public:  GET  /api/book/{slug}                the page
         GET  /api/book/{slug}/calendar       per-date availability and lowest price
         GET  /api/book/{slug}/availability   rooms and rates for a stay
         POST /api/book/{slug}/checkout       hold the room, get the payment link
         GET  /api/guest-booking/{token}      the guest's booking
         POST /api/guest-booking/{token}/cancel

Public errors carry a short code that the guest's page translates.
"""

import datetime as dt
import logging
import re
from collections.abc import Awaitable, Callable
from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.rbac.dependencies import require_permission
from app.schemas.booking_page import (
    BookingPageSaveRequest,
    BookingPageSetup,
    CheckoutRequest,
    CheckoutResult,
    GuestBookingView,
    GuestCancelRequest,
    PublicAvailability,
    PublicCalendar,
    PublicPage,
)
from app.services import booking_page as pages
from app.services import booking_search as search
from app.services import booking_stays as stays
from app.services import direct_checkout, guest_booking
from app.services.bookings import NotEnoughUnitsError
from app.services.workspace import find_property
from app.tenancy.context import TenantContext, get_tenant_context
from app.tenancy.public_booking import (
    GuestBookingScope,
    PublicBookingScope,
    get_booking_page_scope,
    get_guest_booking_scope,
)
from app.tenancy.session import get_tenant_session

VIEW = require_permission("booking_page:view", "See the booking page setup")
EDIT = require_permission("booking_page:edit", "Set up and publish the booking page")

booking_page_router = APIRouter(prefix="/api/booking-page", tags=["booking page"])
public_book_router = APIRouter(prefix="/api/book", tags=["booking page"])
guest_booking_router = APIRouter(prefix="/api/guest-booking", tags=["booking page"])

T = TypeVar("T")
UNPROCESSABLE = status.HTTP_422_UNPROCESSABLE_ENTITY
_STAY_CODES: list[tuple[type[Exception], str]] = [
    (stays.DepartureNotAfterArrivalError, "invalid_dates"),
    (stays.StayTooLongError, "stay_too_long"),
    (stays.ArrivalTooFarBackError, "past_arrival"),
    (stays.ArrivalBeyondHorizonError, "too_far_ahead"),
    (stays.OverCapacityError, "too_many_guests"),
    (search.PastArrivalError, "past_arrival"),
    (search.CalendarRangeError, "invalid_dates"),
]


class _RedactGuestTokens(logging.Filter):
    """The guest's private token is in the path: keep it out of access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            record.args = (*args[:2], _TOKEN_IN_PATH.sub(r"\1***", args[2]), *args[3:])
        return True


_TOKEN_IN_PATH = re.compile(r"(/api/guest-booking/)[^/?\s]+")
logging.getLogger("uvicorn.access").addFilter(_RedactGuestTokens())


async def _public(call: Callable[[], Awaitable[T]]) -> T:
    try:
        return await call()
    except direct_checkout.CheckoutError as exc:
        detail = {"code": exc.code, **exc.details}
        raise HTTPException(status_code=exc.status, detail=detail) from None
    except NotEnoughUnitsError:
        raise HTTPException(status.HTTP_409_CONFLICT, {"code": "sold_out"}) from None
    except guest_booking.CannotCancelError:
        raise HTTPException(status.HTTP_409_CONFLICT, {"code": "cannot_cancel"}) from None
    except guest_booking.NoRefundNotAcceptedError:
        raise HTTPException(status.HTTP_409_CONFLICT, {"code": "accept_no_refund"}) from None
    except stays.StayError as exc:
        code = next((c for kind, c in _STAY_CODES if isinstance(exc, kind)), "not_for_sale")
        raise HTTPException(UNPROCESSABLE, {"code": code}) from None
    except (search.PastArrivalError, search.CalendarRangeError) as exc:
        code = next(c for kind, c in _STAY_CODES if isinstance(exc, kind))
        raise HTTPException(UNPROCESSABLE, {"code": code}) from None


@booking_page_router.get("", response_model=BookingPageSetup)
async def read_setup(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view: dict = VIEW,
) -> BookingPageSetup:
    prop = await find_property(session, context)
    return await pages.read_setup(session, context, prop)


@booking_page_router.put("", response_model=BookingPageSetup)
async def save_setup(
    body: BookingPageSaveRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit: dict = EDIT,
) -> BookingPageSetup:
    prop = await find_property(session, context)
    try:
        return await pages.save_setup(session, context, prop, body)
    except pages.SlugTakenError:
        raise HTTPException(status.HTTP_409_CONFLICT, "That page name is taken.") from None
    except pages.NothingToSellError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Choose at least one rate plan before publishing."
        ) from None
    except pages.UnknownPlanError:
        raise HTTPException(UNPROCESSABLE, "A chosen rate plan is not in use.") from None


@public_book_router.get("/{slug}", response_model=PublicPage)
async def read_page(
    scope: PublicBookingScope = Depends(get_booking_page_scope),
) -> PublicPage:
    return await search.read_page(scope.session, scope.context, scope.prop)


@public_book_router.get("/{slug}/calendar", response_model=PublicCalendar)
async def read_calendar(
    start: dt.date = Query(alias="from"),
    end: dt.date = Query(alias="to"),
    scope: PublicBookingScope = Depends(get_booking_page_scope),
) -> PublicCalendar:
    return await _public(
        lambda: search.read_public_calendar(scope.session, scope.context, scope.prop, start, end)
    )


@public_book_router.get("/{slug}/availability", response_model=PublicAvailability)
async def availability(
    arrival: dt.date,
    departure: dt.date,
    adults: int = Query(default=2, ge=1, le=50),
    children: int = Query(default=0, ge=0, le=50),
    scope: PublicBookingScope = Depends(get_booking_page_scope),
) -> PublicAvailability:
    return await _public(
        lambda: search.search(
            scope.session, scope.context, scope.prop, arrival, departure, adults, children
        )
    )


@public_book_router.post(
    "/{slug}/checkout", response_model=CheckoutResult, status_code=status.HTTP_201_CREATED
)
async def checkout(
    body: CheckoutRequest,
    request: Request,
    response: Response,
    scope: PublicBookingScope = Depends(get_booking_page_scope),
) -> CheckoutResult:
    response.headers["Cache-Control"] = "no-store"
    address = request.client.host if request.client else None
    return await _public(
        lambda: direct_checkout.checkout(scope.session, scope.context, scope.prop, body, address)
    )


@guest_booking_router.get("/{token}", response_model=GuestBookingView)
async def read_guest_booking(
    response: Response,
    scope: GuestBookingScope = Depends(get_guest_booking_scope),
) -> GuestBookingView:
    response.headers["Cache-Control"] = "no-store"
    return await guest_booking.read_view(scope)


@guest_booking_router.post("/{token}/cancel", response_model=GuestBookingView)
async def cancel_guest_booking(
    body: GuestCancelRequest,
    response: Response,
    scope: GuestBookingScope = Depends(get_guest_booking_scope),
) -> GuestBookingView:
    response.headers["Cache-Control"] = "no-store"
    return await _public(lambda: guest_booking.cancel(scope, body))
