"""Booking routes — staff side.

POST   /api/bookings/quote                     price and availability for a stay
POST   /api/bookings                           enter a booking
GET    /api/bookings?tab=&q=&limit=&cursor=
GET    /api/bookings/{id}
PATCH  /api/bookings/{id}
POST   /api/bookings/{id}/cancel
POST   /api/bookings/{id}/payments             record money received
POST   /api/bookings/{id}/refund-done          note a refund sent to the guest
DELETE /api/bookings/{id}/payments/{payment_id}
"""

from collections.abc import Awaitable, Callable
from typing import TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.messaging.phone import InvalidPhoneError
from app.rbac.dependencies import require_permission
from app.schemas.bookings import (
    BookingCancelRequest,
    BookingCreateRequest,
    BookingDetail,
    BookingPage,
    BookingQuote,
    BookingQuoteRequest,
    BookingTab,
    BookingUpdateRequest,
    ChannelAttentionEntry,
    PaymentRecordRequest,
    RefundDoneRequest,
    SearchText,
)
from app.services import booking_holds as holds
from app.services import booking_payments as payments
from app.services import booking_reads as reads
from app.services import booking_refunds as refunds
from app.services import booking_stays as stays
from app.services import bookings, stay_changes
from app.services.front_desk_errors import FrontDeskError
from app.services.workspace import find_property
from app.tenancy.context import TenantContext, get_tenant_context
from app.tenancy.session import get_tenant_session

VIEW = require_permission("bookings:view", "Browse bookings and their prices")

EDIT = require_permission("bookings:edit", "Enter, change and cancel bookings and record payments")

bookings_router = APIRouter(prefix="/api/bookings", tags=["bookings"])

NOT_FOUND = "Booking not found"
T = TypeVar("T")
UNPROCESSABLE = status.HTTP_422_UNPROCESSABLE_ENTITY

_MESSAGES: dict[type[Exception], tuple[int, str]] = {
    bookings.BookingNotFoundError: (status.HTTP_404_NOT_FOUND, NOT_FOUND),
    bookings.BookingConversationNotFoundError: (
        status.HTTP_404_NOT_FOUND,
        "Conversation not found",
    ),
    payments.PaymentNotFoundError: (status.HTTP_404_NOT_FOUND, "Payment not found"),
    bookings.BookingCancelledError: (
        status.HTTP_409_CONFLICT,
        "This booking is cancelled and can no longer be changed.",
    ),
    bookings.BookingStartedError: (
        status.HTTP_409_CONFLICT,
        "This guest has already arrived. Only the departure date, guests and notes can change.",
    ),
    bookings.BookingFinishedError: (
        status.HTTP_409_CONFLICT,
        "This stay has ended and can no longer be changed.",
    ),
    stay_changes.DepartureInPastError: (
        UNPROCESSABLE,
        "The departure date cannot be before today or the arrival date.",
    ),
    stay_changes.RoomTakenError: (
        status.HTTP_409_CONFLICT,
        "The guest's room is taken on the added nights. Move the guest first.",
    ),
    bookings.BookingHeldError: (
        status.HTTP_409_CONFLICT,
        "This booking is waiting for the guest's payment. It can only be cancelled for now.",
    ),
    stays.DepartureNotAfterArrivalError: (UNPROCESSABLE, "Departure must be after arrival."),
    stays.StayTooLargeError: (
        UNPROCESSABLE,
        "Too many units for a stay this long. Split it into several bookings.",
    ),
    payments.TooManyPaymentsError: (
        status.HTTP_409_CONFLICT,
        "This booking has too many payment entries. Remove wrong ones first.",
    ),
    stays.UnknownRoomTypeError: (UNPROCESSABLE, "The room type does not exist or is switched off."),
    stays.UnknownRatePlanError: (UNPROCESSABLE, "The rate plan does not exist or is switched off."),
    stays.PlanDoesNotSellRoomError: (UNPROCESSABLE, "This rate plan does not sell that room type."),
    payments.PaymentDateError: (
        UNPROCESSABLE,
        "The date received must be today or earlier, within the last year.",
    ),
    InvalidPhoneError: (
        UNPROCESSABLE,
        "Write the number with its country code (+62…) or starting with 0.",
    ),
    reads.InvalidCursorError: (UNPROCESSABLE, "Invalid cursor"),
}


def _dated(exc: Exception) -> HTTPException | None:
    """Answers that carry a number or a date from the error."""
    if isinstance(exc, bookings.NotEnoughUnitsError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Not enough units are left on some nights.",
                "short_dates": [night.isoformat() for night in exc.short_dates],
            },
        )
    if isinstance(exc, stays.StayTooLongError):
        return HTTPException(UNPROCESSABLE, f"A stay can be at most {exc.max_nights} nights.")
    if isinstance(exc, stays.ArrivalTooFarBackError):
        return HTTPException(UNPROCESSABLE, f"Arrival cannot be before {exc.earliest.isoformat()}.")
    if isinstance(exc, stays.ArrivalBeyondHorizonError):
        return HTTPException(UNPROCESSABLE, f"Arrival cannot be after {exc.latest.isoformat()}.")
    if isinstance(exc, stays.TooManyUnitsError):
        return HTTPException(UNPROCESSABLE, f"A booking can hold at most {exc.limit} units.")
    if isinstance(exc, stays.OverCapacityError):
        return HTTPException(
            UNPROCESSABLE, f"At most {exc.max_guests} guests fit in the units booked."
        )
    return None


async def _guarded(call: Callable[[], Awaitable[T]]) -> T:
    """Run a booking service call, turning its domain errors into HTTP answers."""
    try:
        return await call()
    except (bookings.NotEnoughUnitsError, stays.StayError) as exc:
        answer = _dated(exc)
        if answer is None:
            code, detail = _MESSAGES[type(exc)]
            answer = HTTPException(status_code=code, detail=detail)
        raise answer from None
    except tuple(_MESSAGES) as exc:
        code, detail = _MESSAGES[type(exc)]
        raise HTTPException(status_code=code, detail=detail) from None
    except FrontDeskError as exc:  # for example a payment dated on a closed day
        raise HTTPException(
            status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}
        ) from None


@bookings_router.post("/quote", response_model=BookingQuote)
async def quote_booking(
    body: BookingQuoteRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
) -> BookingQuote:
    prop = await find_property(session, context)
    return await _guarded(lambda: reads.quote(session, context, prop, body))


@bookings_router.post("", response_model=BookingDetail, status_code=status.HTTP_201_CREATED)
async def create_booking(
    body: BookingCreateRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> BookingDetail:
    prop = await find_property(session, context)
    booking = await _guarded(lambda: bookings.create_booking(session, context, prop, body))
    return await reads.read_detail(session, context, prop, booking)


@bookings_router.get("", response_model=BookingPage)
async def list_bookings(
    tab: BookingTab = Query(default="upcoming"),
    q: SearchText | None = Query(default=None),
    limit: int = Query(default=reads.DEFAULT_PAGE_SIZE, ge=1, le=reads.MAX_PAGE_SIZE),
    cursor: str | None = Query(default=None, max_length=100),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
) -> BookingPage:
    prop = await find_property(session, context)
    return await _guarded(
        lambda: reads.list_bookings(session, context, prop, tab, q, limit, cursor)
    )


@bookings_router.get("/channel-attention", response_model=list[ChannelAttentionEntry])
async def channel_attention_list(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view: dict = VIEW,
) -> list[ChannelAttentionEntry]:
    """Channel bookings that need a person (unmapped rooms, overbooking, price mismatch)."""
    prop = await find_property(session, context)
    entries = await reads.channel_attention(session, context, prop.id)
    return [
        ChannelAttentionEntry(
            id=row.id,
            external_booking_id=row.external_booking_id,
            version=int(row.external_version),
            kind=row.event_kind,
            reason=row.attention_reason,
            reservation_id=row.reservation_id,
            connection_id=row.channel_connection_id,
            received_at=row.received_at,
        )
        for row in entries
    ]


@bookings_router.get("/{booking_id}", response_model=BookingDetail)
async def read_booking(
    booking_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
) -> BookingDetail:
    prop = await find_property(session, context)
    booking = await _guarded(lambda: reads.find_booking(session, context, prop.id, booking_id))
    return await reads.read_detail(session, context, prop, booking)


@bookings_router.patch("/{booking_id}", response_model=BookingDetail)
async def update_booking(
    booking_id: UUID,
    body: BookingUpdateRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> BookingDetail:
    prop = await find_property(session, context)
    booking = await _guarded(
        lambda: bookings.update_booking(session, context, prop, booking_id, body)
    )
    return await reads.read_detail(session, context, prop, booking)


@bookings_router.post("/{booking_id}/cancel", response_model=BookingDetail)
async def cancel_booking(
    booking_id: UUID,
    body: BookingCancelRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> BookingDetail:
    prop = await find_property(session, context)
    current = await _guarded(lambda: reads.find_booking(session, context, prop.id, booking_id))
    if current.status == bookings.TENTATIVE:  # its payment link must close with it
        booking = await _guarded(
            lambda: holds.cancel_hold(session, context, prop.id, booking_id, body.reason or "")
        )
    else:
        booking = await _guarded(
            lambda: bookings.cancel_booking(session, context, prop, booking_id, body.reason)
        )
    return await reads.read_detail(session, context, prop, booking)


@bookings_router.post(
    "/{booking_id}/payments", response_model=BookingDetail, status_code=status.HTTP_201_CREATED
)
async def record_payment(
    booking_id: UUID,
    body: PaymentRecordRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> BookingDetail:
    prop = await find_property(session, context)
    booking = await _guarded(
        lambda: payments.record_payment(session, context, prop, booking_id, body)
    )
    return await reads.read_detail(session, context, prop, booking)


@bookings_router.post("/{booking_id}/refund-done", response_model=BookingDetail)
async def mark_refund_done(
    booking_id: UUID,
    body: RefundDoneRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> BookingDetail:
    prop = await find_property(session, context)
    try:
        booking = await _guarded(
            lambda: refunds.mark_refund_done(session, context, prop, booking_id, body)
        )
    except refunds.NoRefundDueError:
        raise HTTPException(status.HTTP_409_CONFLICT, "This booking has no refund due.") from None
    except refunds.RefundDateError:
        raise HTTPException(UNPROCESSABLE, "The refund date cannot be in the future.") from None
    except refunds.RefundAmountError:
        raise HTTPException(
            UNPROCESSABLE, "Refunds cannot add up to more than the guest paid."
        ) from None
    return await reads.read_detail(session, context, prop, booking)


@bookings_router.delete("/{booking_id}/payments/{payment_id}", response_model=BookingDetail)
async def remove_payment(
    booking_id: UUID,
    payment_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> BookingDetail:
    prop = await find_property(session, context)
    booking = await _guarded(
        lambda: payments.remove_payment(session, context, prop, booking_id, payment_id)
    )
    return await reads.read_detail(session, context, prop, booking)
