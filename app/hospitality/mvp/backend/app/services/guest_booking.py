"""What the guest can do with their private link: see the booking and cancel it.

Refunds stay manual: a cancellation inside the free period is flagged "refund due" for
staff. A non-refundable booking is only cancelled once the guest confirms they accept it.
"""

import datetime as dt
import logging
from decimal import Decimal

from sqlmodel import col, select

from app.models.tenant import Property, RatePlan, Reservation, UnitType
from app.schemas.booking_page import GuestBookingView, GuestCancelRequest
from app.services import booking_holds as holds
from app.services import booking_tokens as tokens
from app.services.bookings import (
    CANCELLED,
    TENTATIVE,
    BookingCancelledError,
    balance_to_collect,
    get_for_update,
    lines_of,
    lock_property,
    stay_of,
)
from app.services.calendar_dates import property_today
from app.services.payment_links import money, pay_url
from app.tenancy.public_booking import GuestBookingScope

log = logging.getLogger(__name__)

GUEST_CANCEL_NOTE = "Cancelled by the guest"


class CannotCancelError(Exception):
    """This booking can no longer be cancelled by the guest."""


class NoRefundNotAcceptedError(Exception):
    """The guest must confirm that nothing is returned."""


def _hint(phone: str | None) -> str | None:
    return f"•••• {phone[-4:]}" if phone and len(phone) >= 4 else None


def refund_applies(booking: Reservation, today: dt.date) -> bool:
    """True when money was paid and the free-cancellation period is still open."""
    terms = booking.cancellation_policy_snapshot or {}
    if booking.paid_amount <= Decimal("0") or terms.get("non_refundable"):
        return False
    free_days = terms.get("free_cancellation_days")
    return free_days is not None and (booking.arrival_date - today).days >= int(free_days)


async def _property(scope: GuestBookingScope) -> Property:
    return (
        await scope.session.exec(
            select(Property).where(
                col(Property.tenant_id) == scope.context.tenant_id,
                col(Property.id) == scope.prop_id,
            )
        )
    ).one()


async def _booking(scope: GuestBookingScope) -> Reservation:
    return (
        await scope.session.exec(
            select(Reservation)
            .where(
                col(Reservation.tenant_id) == scope.context.tenant_id,
                col(Reservation.id) == scope.link.reservation_id,
            )
            .execution_options(populate_existing=True)
        )
    ).one()


def _public_status(booking: Reservation) -> str:
    if booking.status == TENTATIVE:
        return "awaiting_payment"
    return "cancelled" if booking.status == CANCELLED else "confirmed"


async def read_view(scope: GuestBookingScope) -> GuestBookingView:
    session, context = scope.session, scope.context
    prop = await _property(scope)
    booking = await _booking(scope)
    stay = stay_of(booking, await lines_of(session, context, [booking.id]))
    room = await session.get(UnitType, stay.room_type_id)
    plan = await session.get(RatePlan, stay.rate_plan_id)
    from app.models.tenant import Guest

    guest = await session.get(Guest, booking.booker_guest_id) if booking.booker_guest_id else None
    today = property_today(prop.timezone)
    terms = booking.cancellation_policy_snapshot or {}
    detail = booking.source_detail or {}
    open_booking = booking.status == TENTATIVE or (
        booking.status != CANCELLED and booking.arrival_date > today
    )
    return GuestBookingView(
        property_name=prop.name,
        property_whatsapp=prop.whatsapp_phone,
        number=booking.confirmation_no,
        status=_public_status(booking),  # type: ignore[arg-type]
        arrival=booking.arrival_date,
        departure=booking.departure_date,
        nights=(booking.departure_date - booking.arrival_date).days,
        room_name=room.name if room else "",
        plan_name=plan.name if plan else "",
        adults=booking.adults,
        children=booking.children,
        guest_name=str(detail.get("booker_name") or (guest.full_name if guest else "")),
        phone_hint=_hint(guest.whatsapp_phone if guest else None),
        total=money(booking.total_amount),
        paid=money(booking.paid_amount),
        balance=money(balance_to_collect(booking)),
        non_refundable=bool(terms.get("non_refundable")),
        free_cancellation_days=terms.get("free_cancellation_days"),
        hold_expires_at=booking.option_expires_at if booking.status == TENTATIVE else None,
        pay_url=pay_url(tokens.derive(scope.link.token_seed, tokens.PAY))
        if booking.status == TENTATIVE
        else None,
        can_cancel=open_booking,
        refund_if_cancelled=refund_applies(booking, today),
        refund_due=bool(detail.get("refund_due")),
        language=booking.language,
    )


async def cancel(scope: GuestBookingScope, request: GuestCancelRequest) -> GuestBookingView:
    """Cancel from the private link. Commits."""
    session, context = scope.session, scope.context
    prop = await _property(scope)
    booking_id, property_id = scope.link.reservation_id, scope.prop_id
    today = property_today(prop.timezone)
    current = await _booking(scope)
    if current.status == CANCELLED:
        raise CannotCancelError
    if current.status == TENTATIVE:  # nothing paid: may be dropped even on arrival day
        try:
            await holds.cancel_hold(session, context, property_id, booking_id, GUEST_CANCEL_NOTE)
        except BookingCancelledError:  # a payment confirmed it a moment ago
            raise CannotCancelError from None
        return await read_view(scope)
    if current.arrival_date <= today:
        raise CannotCancelError
    await session.commit()
    await lock_property(session, context, property_id)
    booking = await get_for_update(session, context, property_id, booking_id)
    if booking.status == CANCELLED:
        await session.rollback()
        raise CannotCancelError
    refund = refund_applies(booking, today)
    if not refund and booking.paid_amount > 0 and not request.accept_no_refund:
        await session.rollback()
        raise NoRefundNotAcceptedError
    booking.source_detail = {**(booking.source_detail or {}), "refund_due": refund}
    await holds.release_booking(session, context, booking, GUEST_CANCEL_NOTE)
    await session.commit()
    log.info("Guest cancelled booking=%s refund_due=%s", booking_id, refund)
    return await read_view(scope)
