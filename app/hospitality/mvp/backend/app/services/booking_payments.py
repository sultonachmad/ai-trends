"""Money staff received for a booking outside the product (cash, transfer, other).

Each entry is a `payment` record tied to the booking. The booking's paid amount and
balance are always recomputed from the entries that still count, never adjusted by hand.
"""

import datetime as dt
import logging
import uuid
from decimal import Decimal
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Payment, Property, Reservation
from app.schemas.bookings import PaymentRecordRequest
from app.services import calendar_dates as dates_of
from app.services.bill_balance import refresh_balance
from app.services.booking_reads import CAPTURED, captured_payments
from app.services.bookings import TENTATIVE, BookingHeldError, get_for_update, lock_property
from app.tenancy.context import TenantContext
from app.tenancy.timezones import property_zone

log = logging.getLogger(__name__)

REMOVED = "cancelled"
MAX_DAYS_BACK = 366
MAX_PAYMENTS_PER_BOOKING = 100
STAFF_METHODS = ("cash", "bank_transfer", "other")
NOON = dt.time(12, 0)


class PaymentNotFoundError(Exception):
    """No such recorded payment on that booking."""


class TooManyPaymentsError(Exception):
    """The booking already has as many payment entries as it may."""


class PaymentDateError(Exception):
    """The received date is in the future or too far in the past."""


async def _recompute(session: AsyncSession, context: TenantContext, booking: Reservation) -> None:
    await session.flush()
    paid = sum(
        (p.captured_amount for p in await captured_payments(session, context, booking.id)),
        Decimal("0"),
    )
    booking.paid_amount = paid
    await refresh_balance(session, context.tenant_id, booking)


async def record_payment(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    booking_id: UUID,
    request: PaymentRecordRequest,
) -> Reservation:
    """Note money received for a booking. Commits."""
    today = dates_of.property_today(prop.timezone)
    if not today - dt.timedelta(days=MAX_DAYS_BACK) <= request.received_on <= today:
        raise PaymentDateError
    received_at = dt.datetime.combine(
        request.received_on, NOON, tzinfo=property_zone(prop.timezone)
    ).astimezone(dt.UTC)
    await lock_property(session, context, prop.id)
    booking = await get_for_update(session, context, prop.id, booking_id)
    if booking.status == TENTATIVE:
        await session.rollback()
        raise BookingHeldError
    if len(await captured_payments(session, context, booking.id)) >= MAX_PAYMENTS_PER_BOOKING:
        raise TooManyPaymentsError
    session.add(
        Payment(
            tenant_id=context.tenant_id,
            property_id=prop.id,
            reservation_id=booking.id,
            direction="inbound",
            method=request.method,
            status=CAPTURED,
            amount=request.amount,
            currency=booking.currency,
            captured_amount=request.amount,
            captured_at=received_at,
            idempotency_key=f"booking-payment:{uuid.uuid4()}",
            metadata_={"note": request.note or None, "recorded_by": str(context.user_id)},
            created_by=str(context.user_id),
        )
    )
    await _recompute(session, context, booking)
    await session.commit()
    await session.refresh(booking)  # amounts as the database stores them
    log.info("Booking payment recorded booking=%s method=%s", booking.id, request.method)
    return booking


async def remove_payment(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    booking_id: UUID,
    payment_id: UUID,
) -> Reservation:
    """Take back a wrongly entered payment (the record is kept, marked removed). Commits."""
    await lock_property(session, context, prop.id)
    booking = await get_for_update(session, context, prop.id, booking_id)
    payment = (
        await session.exec(
            select(Payment).where(
                col(Payment.tenant_id) == context.tenant_id,
                col(Payment.reservation_id) == booking.id,
                col(Payment.id) == payment_id,
                col(Payment.status) == CAPTURED,
                # only entries staff typed: gateway payments and refunds are never removed here
                col(Payment.direction) == "inbound",
                col(Payment.method).in_(STAFF_METHODS),
                col(Payment.payment_link_id).is_(None),
            )
        )
    ).first()
    if payment is None:
        raise PaymentNotFoundError
    payment.status = REMOVED
    payment.failure_reason = "entered_by_mistake"
    payment.updated_by = str(context.user_id)
    session.add(payment)
    await _recompute(session, context, booking)
    await session.commit()
    await session.refresh(booking)  # amounts as the database stores them
    log.info("Booking payment removed booking=%s payment=%s", booking.id, payment.id)
    return booking
