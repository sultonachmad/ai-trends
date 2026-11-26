"""Recording that a refund owed to a guest has been sent.

The money itself moves outside the product. This clears the "refund due" flag on the
booking and on its payments, and keeps who, when and how much in the booking's history.
"""

import datetime as dt
import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Payment, Property, Reservation
from app.schemas.bookings import RefundDoneRequest
from app.services import calendar_dates as dates_of
from app.services import tenant_audit
from app.services.booking_holds import _lock_link_of
from app.services.bookings import get_for_update, lock_property
from app.services.cash_drawers import REFUND, cash_movement, drawer_for_entry
from app.services.closed_days import ensure_open
from app.services.payment_links import NEEDS_REFUND_FLAG
from app.tenancy.context import TenantContext
from app.tenancy.timezones import property_zone

log = logging.getLogger(__name__)
NOON = dt.time(12)  # a refund dated without a time is shown at midday

ENTITY = "reservation"


class NoRefundDueError(Exception):
    """This booking has no refund waiting."""


class RefundDateError(Exception):
    """A refund cannot be dated in the future."""


class RefundAmountError(Exception):
    """The refunds would add up to more than the guest paid."""


def _refunded_so_far(detail: dict) -> tuple[list[dict], Decimal]:
    """Earlier refund records, oldest first, and what they add up to."""
    earlier = [*detail.get("refund_history", [])]
    if detail.get("refund_done"):
        earlier = [*earlier, detail["refund_done"]]
    return earlier, sum((Decimal(entry["amount"]) for entry in earlier), Decimal(0))


async def _money_received(
    session: AsyncSession, context: TenantContext, booking_id: UUID, link_id: UUID | None
) -> Decimal:
    """Captured on this booking or on its payment link, counting each payment once."""
    belongs = col(Payment.reservation_id) == booking_id
    if link_id is not None:
        belongs = or_(belongs, col(Payment.payment_link_id) == link_id)
    total = await session.exec(
        select(func.coalesce(func.sum(Payment.captured_amount), 0)).where(
            col(Payment.tenant_id) == context.tenant_id,
            col(Payment.status) == "captured",
            col(Payment.direction) != "refund",
            belongs,
        )
    )
    return Decimal(total.one())


async def _clear_payment_flags(
    session: AsyncSession, context: TenantContext, link_id: UUID, done_at: str
) -> None:
    rows = await session.exec(
        select(Payment)
        .where(col(Payment.tenant_id) == context.tenant_id, col(Payment.payment_link_id) == link_id)
        .with_for_update()
    )
    for payment in rows.all():
        metadata = payment.metadata_ or {}
        if NEEDS_REFUND_FLAG in metadata:
            kept = {key: value for key, value in metadata.items() if key != NEEDS_REFUND_FLAG}
            payment.metadata_ = {**kept, "refund_done_at": done_at}
            session.add(payment)


async def _ledger(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    booking: Reservation,
    request: RefundDoneRequest,
) -> None:
    """The refund as a cash movement: the cash book and daily totals see it, and what
    the booking owes is not changed a second time."""
    drawer_id = await drawer_for_entry(
        session,
        context,
        prop,
        method=request.method,
        on=request.refunded_on,
        cash_leaves_now=True,  # the cash comes out of today's drawer, whatever the date
    )
    on = dt.datetime.combine(request.refunded_on, NOON, tzinfo=property_zone(prop.timezone))
    session.add(
        cash_movement(
            context,
            prop,
            amount=Decimal(request.amount),
            method=request.method,
            kind=REFUND,
            on=on.astimezone(dt.UTC),
            drawer_id=drawer_id,
            reservation_id=booking.id,
            reason=request.note or None,
        )
    )


async def mark_refund_done(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    booking_id: UUID,
    request: RefundDoneRequest,
) -> Reservation:
    """Record the refund and clear the flag. Commits."""
    if request.refunded_on > dates_of.property_today(prop.timezone):
        raise RefundDateError
    property_id = prop.id
    link = await _lock_link_of(session, context, booking_id)  # link first, as everywhere
    await lock_property(session, context, property_id)
    booking = await get_for_update(session, context, property_id, booking_id)
    if not (booking.source_detail or {}).get("refund_due"):
        await session.rollback()
        raise NoRefundDueError
    earlier, refunded = _refunded_so_far(booking.source_detail)
    received = await _money_received(session, context, booking.id, link.id if link else None)
    if refunded + Decimal(request.amount) > received:
        await session.rollback()
        raise RefundAmountError
    await ensure_open(session, context, property_id, request.refunded_on)
    await _ledger(session, context, prop, booking, request)
    done_at = dt.datetime.now(dt.UTC).isoformat()
    if link is not None:
        await _clear_payment_flags(session, context, link.id, done_at)
    record = {
        "amount": str(Decimal(request.amount)),
        "refunded_on": request.refunded_on.isoformat(),
        "method": request.method,
        "note": request.note or None,
        "recorded_by": str(context.user_id),
        "recorded_at": done_at,
    }
    booking.source_detail = {
        **booking.source_detail,
        "refund_due": False,
        "refund_done": record,
        "refund_history": earlier,
    }
    booking.updated_by = str(context.user_id)
    session.add(booking)
    await tenant_audit.record(
        session,
        context,
        "booking.refund_done",
        property_id=property_id,
        entity_table=ENTITY,
        entity_id=booking.id,
        payload={"amount": record["amount"], "refunded_on": record["refunded_on"]},
    )
    await session.commit()
    await session.refresh(booking)
    log.info("Refund recorded booking=%s", booking.id)
    return booking
