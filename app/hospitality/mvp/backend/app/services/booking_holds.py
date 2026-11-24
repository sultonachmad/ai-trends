"""Held direct bookings: from "awaiting payment" to confirmed, lapsed or cancelled.

A hold is a `tentative` booking that already owns its units. Lock order everywhere here
starts with the payment link, then the property, then the booking: every flow takes the
link first, so the gateway and proof review cannot deadlock with the lapse loop.

Money that arrives after a hold lapsed confirms the booking only if the room is still
free. Otherwise the booking stays cancelled and the payment is flagged for a staff
refund: a late payment never overbooks.
"""

import asyncio
import datetime as dt
import logging
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.control_plane import Tenant
from app.models.tenant import Payment, PaymentLink, Property, Reservation, ReservationUnit
from app.services import channel_queue, inventory
from app.services.booking_payments import _recompute
from app.services.bookings import (
    CANCELLED,
    CONFIRMED,
    TENTATIVE,
    BookingCancelledError,
    get_for_update,
    lines_of,
    lock_property,
    stay_of,
)
from app.services.calendar_dates import property_today
from app.services.channel_push import _context as worker_context
from app.services.payment_links import NEEDS_REFUND_FLAG, cancel_pending_payments
from app.services.stay_status import STARTED
from app.tenancy.business_settings import resolve_property_settings
from app.tenancy.context import TenantContext
from app.tenancy.session import bind_tenant

log = logging.getLogger(__name__)

BOOKING_PAGE = "booking_page"
LAPSED_NOTE = "Hold expired: payment not received in time"
CONFIRMED_OUTCOME, REFUND_OUTCOME, NOT_A_HOLD = "confirmed", "refund_due", "none"
PENDING_CONFIRMATION = {"status": "pending", "attempts": 0}


def _with_detail(booking: Reservation, **changes: object) -> None:
    """The JSON column is replaced, never changed in place, so the change is saved."""
    booking.source_detail = {**(booking.source_detail or {}), **changes}


async def _set_line_status(
    session: AsyncSession, context: TenantContext, booking_id: UUID, status: str
) -> None:
    await session.exec(
        update(ReservationUnit)
        .where(
            col(ReservationUnit.tenant_id) == context.tenant_id,
            col(ReservationUnit.reservation_id) == booking_id,
        )
        .values(status=status)
    )


async def _confirm(session: AsyncSession, context: TenantContext, booking: Reservation) -> None:
    booking.status = CONFIRMED
    booking.option_expires_at = None
    booking.cancelled_at = None
    booking.cancel_note = None
    _with_detail(booking, lapsed=False, confirmation=dict(PENDING_CONFIRMATION))
    session.add(booking)
    await _set_line_status(session, context, booking.id, CONFIRMED)


async def _retake_units(
    session: AsyncSession, context: TenantContext, booking: Reservation
) -> bool:
    """Take a lapsed booking's units back, only if every night still has them."""
    prop = (
        await session.exec(
            select(Property).where(
                col(Property.tenant_id) == context.tenant_id,
                col(Property.id) == booking.property_id,
            )
        )
    ).one()
    if booking.arrival_date < property_today(prop.timezone):
        return False  # the stay has already started: staff refund it
    stay = stay_of(booking, await lines_of(session, context, [booking.id]))
    room = stay.room_type_id
    units = (await inventory.units_in_use(session, context, [room])).get(room, 0)
    taken = await inventory.taken_by_night(
        session, context, [room], stay.nights[0], stay.nights[-1]
    )
    if any(taken.get((room, night), 0) + stay.units > units for night in stay.nights):
        return False
    await inventory.take_units(
        session, context, booking.property_id, room, stay.nights, stay.units, units
    )
    await channel_queue.enqueue(session, context, booking.property_id, [room], stay.nights)
    return True


def _flag_refund(session: AsyncSession, booking: Reservation, payment: Payment) -> None:
    payment.metadata_ = {**(payment.metadata_ or {}), NEEDS_REFUND_FLAG: "booking_not_held"}
    session.add(payment)
    _with_detail(booking, refund_due=True)
    session.add(booking)


async def settle_paid_link(
    session: AsyncSession, tenant_id: UUID, link: PaymentLink, payment: Payment
) -> str:
    """Apply a captured payment to the link's booking. The caller holds link and payment."""
    if link.origin != BOOKING_PAGE or link.reservation_id is None:
        return NOT_A_HOLD
    context = worker_context(tenant_id, session)
    await lock_property(session, context, link.property_id)
    booking = await get_for_update(session, context, link.property_id, link.reservation_id)
    if booking.status == CONFIRMED or booking.status in STARTED:
        # A second payment for a booking already paid: never counted, always refunded.
        _flag_refund(session, booking, payment)
        log.error("REFUND REVIEW: extra payment %s for booking %s", payment.id, booking.id)
        return REFUND_OUTCOME
    payment.reservation_id = booking.id
    session.add(payment)
    outcome = CONFIRMED_OUTCOME
    if booking.status == TENTATIVE:
        await _confirm(session, context, booking)
    elif booking.status == CANCELLED:
        lapsed = bool((booking.source_detail or {}).get("lapsed"))
        if lapsed and await _retake_units(session, context, booking):
            await _confirm(session, context, booking)
        else:
            _flag_refund(session, booking, payment)
            outcome = REFUND_OUTCOME
    await _recompute(session, context, booking)
    log.info("Direct booking payment booking=%s outcome=%s", booking.id, outcome)
    return outcome


async def _lock_link_of(
    session: AsyncSession, context: TenantContext, booking_id: UUID
) -> PaymentLink | None:
    return (
        await session.exec(
            select(PaymentLink)
            .where(
                col(PaymentLink.tenant_id) == context.tenant_id,
                col(PaymentLink.reservation_id) == booking_id,
                col(PaymentLink.origin) == BOOKING_PAGE,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).first()


async def _release(
    session: AsyncSession, context: TenantContext, booking: Reservation, note: str
) -> None:
    lines = await lines_of(session, context, [booking.id])
    stay = stay_of(booking, lines)
    await inventory.release_units(session, context, stay.room_type_id, stay.nights, stay.units)
    await _set_line_status(session, context, booking.id, CANCELLED)
    booking.status = CANCELLED
    booking.cancelled_at = dt.datetime.now(dt.UTC)
    booking.cancel_note = note
    booking.option_expires_at = None
    session.add(booking)
    await channel_queue.enqueue(
        session, context, booking.property_id, [stay.room_type_id], stay.nights
    )


async def release_booking(
    session: AsyncSession, context: TenantContext, booking: Reservation, note: str
) -> None:
    """Cancel a locked booking and give back its units. The caller commits."""
    await _release(session, context, booking, note)


async def cancel_hold(
    session: AsyncSession, context: TenantContext, property_id: UUID, booking_id: UUID, note: str
) -> Reservation:
    """Cancel a held booking and close its payment link. Commits."""
    link = await _lock_link_of(session, context, booking_id)
    await lock_property(session, context, property_id)
    booking = await get_for_update(session, context, property_id, booking_id)
    if booking.status != TENTATIVE:
        await session.rollback()
        raise BookingCancelledError
    if link is not None and link.status == "active":
        link.status = "cancelled"
        session.add(link)
        await cancel_pending_payments(session, link)
    await _release(session, context, booking, note)
    await session.commit()
    await session.refresh(booking)
    log.info("Held booking cancelled booking=%s", booking.id)
    return booking


async def _lapse_one(
    session: AsyncSession, context: TenantContext, row_id: UUID, prop_id: UUID
) -> bool:
    link = await _lock_link_of(session, context, row_id)
    await lock_property(session, context, prop_id)
    booking = await get_for_update(session, context, prop_id, row_id)
    now = dt.datetime.now(dt.UTC)
    expires = booking.option_expires_at
    if booking.status != TENTATIVE or expires is None or expires > now:
        await session.commit()  # paid or extended meanwhile
        return False
    if link is not None and link.status == "active":
        link.status = "expired"
        session.add(link)
        await cancel_pending_payments(session, link)
    _with_detail(booking, lapsed=True)
    await _release(session, context, booking, LAPSED_NOTE)
    await session.commit()
    log.info("Hold lapsed booking=%s", row_id)
    return True


async def lapse_due(session: AsyncSession, context: TenantContext) -> int:
    """Release every hold past its time. Returns how many were released."""
    rows = (
        await session.exec(
            select(col(Reservation.id), col(Reservation.property_id))
            .where(
                col(Reservation.tenant_id) == context.tenant_id,
                col(Reservation.status) == TENTATIVE,
                col(Reservation.option_expires_at) <= dt.datetime.now(dt.UTC),
            )
            .limit(200)
        )
    ).all()
    await session.commit()
    lapsed = 0
    for booking_id, property_id in rows:
        try:
            lapsed += await _lapse_one(session, context, booking_id, property_id)
        except Exception:  # noqa: BLE001 — one booking must not stop the others
            await session.rollback()
            log.exception("Lapsing hold failed booking=%s", booking_id)
    return lapsed


async def extend_for_proof(session: AsyncSession, link_id: UUID, tenant_id: UUID) -> None:
    """A transfer screenshot arrived: keep the room while staff decide. Commits."""
    context = worker_context(tenant_id, session)
    link = (
        await session.exec(
            select(PaymentLink)
            .where(col(PaymentLink.tenant_id) == tenant_id, col(PaymentLink.id) == link_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).first()
    if link is None or link.origin != BOOKING_PAGE or link.reservation_id is None:
        await session.commit()
        return
    await lock_property(session, context, link.property_id)
    booking = await get_for_update(session, context, link.property_id, link.reservation_id)
    prop = (
        await session.exec(
            select(Property).where(
                col(Property.tenant_id) == tenant_id, col(Property.id) == link.property_id
            )
        )
    ).one()
    already = bool((booking.source_detail or {}).get("proof_extended"))
    if booking.status == TENTATIVE and booking.option_expires_at is not None and not already:
        # Once per booking: repeated uploads cannot keep a room off sale.
        _with_detail(booking, proof_extended=True)
        hours = resolve_property_settings(prop.settings).direct_proof_hold_hours
        until = max(booking.option_expires_at, dt.datetime.now(dt.UTC) + dt.timedelta(hours=hours))
        booking.option_expires_at = until
        link.expires_at = until
        session.add(booking)
        session.add(link)
    await session.commit()


async def run_hold_loop(
    session_factory: async_sessionmaker[AsyncSession], stop: asyncio.Event, interval_seconds: int
) -> None:
    """The background loop: release lapsed holds and send pending confirmations."""
    from app.services.booking_confirmation import send_pending

    log.info("Direct booking loop started (every %ss)", interval_seconds)
    while not stop.is_set():
        try:
            async with session_factory() as session:
                tenant_ids = list((await session.exec(select(col(Tenant.id)))).all())
            for tenant_id in tenant_ids:
                try:
                    async with session_factory() as session:
                        await bind_tenant(session, tenant_id)
                        context = worker_context(tenant_id, session)
                        await lapse_due(session, context)
                        await send_pending(session, context)
                except Exception:  # noqa: BLE001 — one tenant must not stop the others
                    log.exception("Direct booking loop failed tenant=%s", tenant_id)
        except Exception:  # noqa: BLE001 — the loop must survive anything
            log.exception("Direct booking loop tick failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
        except TimeoutError:
            pass
    log.info("Direct booking loop stopped")
