"""Creating, changing and cancelling bookings.

`book` is the single way a booking comes into being, whoever asks: it takes a stay, a
guest and a source, and knows nothing about staff forms. Staff entry (`create_booking`)
is a thin wrapper; channel bookings and the booking page will be others.

Every change runs in one transaction under the property's row lock: the booking, its
room lines, its nightly prices and the units sold per night change together or not at all.
"""

import datetime as dt
import logging
import uuid
from dataclasses import dataclass, replace
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, insert
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.messaging.phone import normalise_phone
from app.models.tenant import (
    Channel,
    Conversation,
    Guest,
    Property,
    Reservation,
    ReservationDailyRate,
    ReservationUnit,
)
from app.schemas.bookings import BookingCreateRequest, BookingUpdateRequest
from app.services import inventory
from app.services import rate_policies as policies
from app.services.booking_guests import find_or_create_guest
from app.services.booking_numbers import new_booking_number
from app.services.booking_pricing import spread_total
from app.services.booking_sources import staff_source
from app.services.booking_stays import CheckedStay, Stay, check_stay, stay_times
from app.tenancy.business_settings import resolve_property_settings
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

CONFIRMED = "confirmed"
CANCELLED = "cancelled"
TENTATIVE = "tentative"  # held for a guest who has not paid yet
NUMBER_ATTEMPTS = 5
PRICE_EDITED = "price_edited"


class BookingNotFoundError(Exception):
    """No such booking on the caller's property."""


class BookingCancelledError(Exception):
    """The booking is cancelled and can no longer be changed."""


class BookingHeldError(Exception):
    """The booking is held for an online payment; it can only be cancelled until then."""


class BookingConversationNotFoundError(Exception):
    """No such conversation on the caller's property."""


class NotEnoughUnitsError(Exception):
    """Some nights have fewer units left than the booking needs."""

    def __init__(self, short_dates: list[dt.date]) -> None:
        super().__init__(f"not enough units on {len(short_dates)} night(s)")
        self.short_dates = short_dates


@dataclass(frozen=True)
class BookingOrder:
    """Everything `book` needs, whatever the source of the booking."""

    stay: Stay
    guest: Guest
    source: Channel
    total_amount: Decimal | None = None  # None = the calendar price
    notes: str | None = None
    allow_overbooking: bool = False
    booked_by: str | None = None
    hold_until: dt.datetime | None = None  # set = a held (tentative) booking
    source_detail: dict[str, object] | None = None
    language: str | None = None


async def lock_property(session: AsyncSession, context: TenantContext, property_id: UUID) -> None:
    """Serialise booking changes of one property (units sold are counted, not constrained)."""
    await session.exec(
        select(col(Property.id))
        .where(col(Property.tenant_id) == context.tenant_id, col(Property.id) == property_id)
        .with_for_update()
    )


async def _unused_number(session: AsyncSession, context: TenantContext, property_name: str) -> str:
    for _ in range(NUMBER_ATTEMPTS):
        number = new_booking_number(property_name)
        taken = (
            await session.exec(
                select(col(Reservation.id)).where(
                    col(Reservation.tenant_id) == context.tenant_id,
                    col(Reservation.confirmation_no) == number,
                )
            )
        ).first()
        if taken is None:
            return number
    raise RuntimeError("could not find an unused booking number")


def _cell_amounts(checked: CheckedStay, total: Decimal | None) -> list[Decimal]:
    """One amount per unit per night (unit by unit), summing to the booking total."""
    calendar_prices = [night.amount for night in checked.nights] * checked.stay.units
    return calendar_prices if total is None else spread_total(total, calendar_prices)


async def _write_lines(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    booking: Reservation,
    checked: CheckedStay,
    cells: list[Decimal],
) -> None:
    """Store one room line per unit with its nightly prices."""
    stay = checked.stay
    start_at, end_at = stay_times(stay, prop.timezone)
    per_unit = len(checked.nights)
    line_rows, rate_rows = [], []
    for index in range(stay.units):
        line_id = uuid.uuid4()
        amounts = cells[index * per_unit : (index + 1) * per_unit]
        line_rows.append(
            {
                "id": line_id,
                "tenant_id": context.tenant_id,
                "reservation_id": booking.id,
                "property_id": prop.id,
                "unit_type_id": stay.room_type_id,
                "rate_plan_id": stay.rate_plan_id,
                "status": booking.status,
                "arrival_date": stay.arrival,
                "departure_date": stay.departure,
                "start_at": start_at,
                "end_at": end_at,
                "blocked_until": end_at,
                "total_amount": sum(amounts, Decimal("0")),
            }
        )
        rate_rows.extend(
            {
                "id": uuid.uuid4(),
                "tenant_id": context.tenant_id,
                "reservation_unit_id": line_id,
                "stay_date": night.date,
                "rate_plan_id": stay.rate_plan_id,
                "unit_type_id": stay.room_type_id,
                "amount": amount,
            }
            for night, amount in zip(checked.nights, amounts, strict=True)
        )
    await session.exec(insert(ReservationUnit), params=line_rows)
    await session.exec(insert(ReservationDailyRate), params=rate_rows)


async def _take(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    checked: CheckedStay,
    allow_overbooking: bool,
    sold_before: dict[dt.date, int] | None = None,
) -> None:
    """Sell the stay's units; refuse (and undo everything) when short and not allowed.

    When a booking is being changed, `sold_before` holds what each night had sold before
    the change: a night that was already oversold and did not get worse is not held
    against it, so correcting a price or freeing a unit never needs consent.
    """
    in_use = checked.nights[0].units
    sold = await inventory.take_units(
        session,
        context,
        prop.id,
        checked.stay.room_type_id,
        checked.stay.nights,
        checked.stay.units,
        in_use,
    )
    before = sold_before or {}
    short = sorted(
        night for night, count in sold.items() if count > in_use and count > before.get(night, 0)
    )
    if short and not allow_overbooking:
        await session.rollback()
        raise NotEnoughUnitsError(short)


async def _terms_snapshot(
    session: AsyncSession, context: TenantContext, checked: CheckedStay
) -> dict[str, object]:
    """The cancellation terms as they were when the booking was made."""
    policy_id = checked.plan.cancellation_policy_id
    terms = policies.terms_of(
        (await policies.policies_by_id(session, context, {policy_id}))[policy_id]
    )
    return {"non_refundable": terms.non_refundable, "free_cancellation_days": terms.free_days}


async def book(
    session: AsyncSession, context: TenantContext, prop: Property, order: BookingOrder
) -> Reservation:
    """Create a confirmed booking and take its units off sale. Commits."""
    booking = await book_in_transaction(session, context, prop, order)
    number, units = booking.confirmation_no, order.stay.units
    await session.commit()
    await session.refresh(booking)  # amounts and times as the database stores them
    log.info("Booking created booking=%s number=%s units=%s", booking.id, number, units)
    return booking


async def book_in_transaction(
    session: AsyncSession, context: TenantContext, prop: Property, order: BookingOrder
) -> Reservation:
    """Create the booking and take its units, leaving the commit to the caller."""
    settings = resolve_property_settings(prop.settings)
    property_id, property_name = prop.id, prop.name
    await lock_property(session, context, property_id)
    checked = await check_stay(session, context, prop, settings, order.stay)
    number = await _unused_number(session, context, property_name)
    terms = await _terms_snapshot(session, context, checked)
    guest_id, source_id = order.guest.id, order.source.id
    await _take(session, context, prop, checked, order.allow_overbooking)
    cells = _cell_amounts(checked, order.total_amount)
    total = sum(cells, Decimal("0"))
    booking = Reservation(
        tenant_id=context.tenant_id,
        property_id=property_id,
        confirmation_no=number,
        status=TENTATIVE if order.hold_until else CONFIRMED,
        option_expires_at=order.hold_until,
        language=order.language,
        booker_guest_id=guest_id,
        channel_id=source_id,
        source_detail={
            PRICE_EDITED: order.total_amount is not None,
            **(order.source_detail or {}),
        },
        arrival_date=order.stay.arrival,
        departure_date=order.stay.departure,
        adults=order.stay.adults,
        children=order.stay.children,
        currency=prop.currency,
        total_amount=total,
        balance_due=total,
        cancellation_policy_snapshot=terms,
        internal_notes=order.notes,
        booked_by=order.booked_by,
        created_by=order.booked_by,
    )
    session.add(booking)
    await session.flush()
    await _write_lines(session, context, prop, booking, checked, cells)
    await _queue_channel_update(session, context, prop.id, [checked.stay])
    return booking


def _phone(raw: str | None) -> str | None:
    return None if raw is None else normalise_phone(raw)


async def _conversation_guest(
    session: AsyncSession, context: TenantContext, property_id: UUID, conversation_id: UUID
) -> Guest | None:
    conversation = (
        await session.exec(
            select(Conversation).where(
                col(Conversation.tenant_id) == context.tenant_id,
                col(Conversation.property_id) == property_id,
                col(Conversation.id) == conversation_id,
            )
        )
    ).first()
    if conversation is None:
        raise BookingConversationNotFoundError
    if conversation.guest_id is None:
        return None
    return (
        await session.exec(
            select(Guest).where(
                col(Guest.tenant_id) == context.tenant_id, col(Guest.id) == conversation.guest_id
            )
        )
    ).first()


async def create_booking(
    session: AsyncSession, context: TenantContext, prop: Property, request: BookingCreateRequest
) -> Reservation:
    """A booking entered by staff for a WhatsApp, phone or walk-in guest. Commits."""
    phone = _phone(request.guest_phone)
    property_id = prop.id
    await lock_property(session, context, property_id)
    guest = None
    if request.conversation_id is not None:
        guest = await _conversation_guest(session, context, property_id, request.conversation_id)
    if guest is None:
        guest = await find_or_create_guest(session, context.tenant_id, request.guest_name, phone)
    source = await staff_source(session, context, request.source)
    order = BookingOrder(
        stay=Stay(
            arrival=request.arrival,
            departure=request.departure,
            room_type_id=request.room_type_id,
            rate_plan_id=request.rate_plan_id,
            units=request.units,
            adults=request.adults,
            children=request.children,
        ),
        guest=guest,
        source=source,
        total_amount=request.total_amount,
        notes=request.notes or None,
        allow_overbooking=request.allow_overbooking,
        booked_by=str(context.user_id),
    )
    return await book(session, context, prop, order)


async def _queue_channel_update(
    session: AsyncSession, context: TenantContext, property_id: UUID, stays: list[Stay]
) -> None:
    """Every night a stay held (before or after a change) is a date channels must hear about."""
    from app.services.channel_queue import enqueue as enqueue_channels

    room_type_ids = list({stay.room_type_id for stay in stays})
    dates = [night for stay in stays for night in stay.nights]
    await enqueue_channels(session, context, property_id, room_type_ids, dates)


# ---- changing ---------------------------------------------------------------------------


async def get_for_update(
    session: AsyncSession, context: TenantContext, property_id: UUID, booking_id: UUID
) -> Reservation:
    booking = (
        await session.exec(
            select(Reservation)
            .where(
                col(Reservation.tenant_id) == context.tenant_id,
                col(Reservation.property_id) == property_id,
                col(Reservation.id) == booking_id,
            )
            .with_for_update()
            # the row as it is now, even if this session read it before the lock
            .execution_options(populate_existing=True)
        )
    ).first()
    if booking is None:
        raise BookingNotFoundError
    return booking


async def lines_of(
    session: AsyncSession, context: TenantContext, booking_ids: list[UUID]
) -> list[ReservationUnit]:
    if not booking_ids:
        return []
    rows = await session.exec(
        select(ReservationUnit)
        .where(
            col(ReservationUnit.tenant_id) == context.tenant_id,
            col(ReservationUnit.reservation_id).in_(booking_ids),
        )
        .order_by(col(ReservationUnit.created_at), col(ReservationUnit.id))
    )
    return list(rows.all())


def stay_of(booking: Reservation, lines: list[ReservationUnit]) -> Stay:
    """The stay a stored booking holds (all its lines share room type, plan and dates)."""
    first = lines[0]
    return Stay(
        arrival=booking.arrival_date,
        departure=booking.departure_date,
        room_type_id=first.unit_type_id,
        rate_plan_id=first.rate_plan_id,
        units=len(lines),
        adults=booking.adults,
        children=booking.children,
    )


def _changed_stay(current: Stay, request: BookingUpdateRequest) -> Stay:
    sent = request.model_dump(exclude_unset=True, exclude_none=True)
    fields = ("arrival", "departure", "room_type_id", "rate_plan_id", "units", "adults", "children")
    return replace(current, **{name: sent[name] for name in fields if name in sent})


async def _replace_lines(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    booking: Reservation,
    old: Stay,
    checked: CheckedStay,
    total: Decimal | None,
    allow_overbooking: bool,
) -> None:
    """Give back the old nights, take the new ones and rewrite lines and nightly prices."""
    new = checked.stay
    before = {
        night: count
        for (_room, night), count in (
            await inventory.taken_by_night(
                session, context, [new.room_type_id], new.arrival, new.departure
            )
        ).items()
    }
    await inventory.release_units(session, context, old.room_type_id, old.nights, old.units)
    await session.flush()
    await _take(session, context, prop, checked, allow_overbooking, before)
    line_ids = select(col(ReservationUnit.id)).where(
        col(ReservationUnit.tenant_id) == context.tenant_id,
        col(ReservationUnit.reservation_id) == booking.id,
    )
    await session.exec(
        delete(ReservationDailyRate).where(
            col(ReservationDailyRate.tenant_id) == context.tenant_id,
            col(ReservationDailyRate.reservation_unit_id).in_(line_ids),
        )
    )
    await session.exec(
        delete(ReservationUnit).where(
            col(ReservationUnit.tenant_id) == context.tenant_id,
            col(ReservationUnit.reservation_id) == booking.id,
        )
    )
    cells = _cell_amounts(checked, total)
    await _write_lines(session, context, prop, booking, checked, cells)
    booking.total_amount = sum(cells, Decimal("0"))


async def _change_guest(
    session: AsyncSession,
    context: TenantContext,
    booking: Reservation,
    request: BookingUpdateRequest,
) -> None:
    """Follow a changed number to that number's guest; otherwise correct the name in place."""
    sent = request.model_fields_set
    if not sent & {"guest_name", "guest_phone"}:
        return
    current = (
        await session.exec(
            select(Guest).where(
                col(Guest.tenant_id) == context.tenant_id, col(Guest.id) == booking.booker_guest_id
            )
        )
    ).first()
    name = request.guest_name or (current.full_name if current else "")
    known_phone = current.whatsapp_phone if current else None
    phone = _phone(request.guest_phone) if "guest_phone" in sent else known_phone
    if current is not None and phone == known_phone:
        current.full_name = name  # same person: staff are correcting the name
        session.add(current)
        return
    guest = await find_or_create_guest(session, context.tenant_id, name, phone)
    booking.booker_guest_id = guest.id


def _price_decision(
    booking: Reservation, old: Stay, new: Stay, request: BookingUpdateRequest
) -> tuple[bool, Decimal | None]:
    """(is the total hand-set afterwards, the total to spread or None for the calendar price).

    A hand-set total survives a change of dates or guests. It is dropped when staff ask
    for the calendar price again, or when the room type, rate plan or number of units
    changes — the old figure was for something else.
    """
    if request.total_amount is not None:
        return True, request.total_amount
    sold_differently = (old.room_type_id, old.rate_plan_id, old.units) != (
        new.room_type_id,
        new.rate_plan_id,
        new.units,
    )
    if request.reset_price or sold_differently or not booking.source_detail.get(PRICE_EDITED):
        return False, None
    return True, booking.total_amount


async def _change_stay_and_price(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    booking: Reservation,
    old: Stay,
    request: BookingUpdateRequest,
) -> Stay:
    """Apply changes to the stay and the price; returns the stay the booking now holds."""
    settings = resolve_property_settings(prop.settings)
    new = _changed_stay(old, request)
    edited, total = _price_decision(booking, old, new, request)
    price_changes = request.total_amount is not None or request.reset_price
    if new == old and not price_changes:
        return old
    dates_changed = (new.arrival, new.departure) != (old.arrival, old.departure)
    checked = await check_stay(session, context, prop, settings, new, dates_changed=dates_changed)
    only_guest_counts = replace(new, adults=old.adults, children=old.children) == old
    if not only_guest_counts or price_changes:
        await _replace_lines(
            session, context, prop, booking, old, checked, total, request.allow_overbooking
        )
    booking.source_detail = {**booking.source_detail, PRICE_EDITED: edited}
    return new


async def update_booking(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    booking_id: UUID,
    request: BookingUpdateRequest,
) -> Reservation:
    """Change the fields that were sent; availability moves with the stay. Commits."""
    await lock_property(session, context, prop.id)
    booking = await get_for_update(session, context, prop.id, booking_id)
    if booking.status == CANCELLED:
        raise BookingCancelledError
    if booking.status == TENTATIVE:
        await session.rollback()
        raise BookingHeldError
    old = stay_of(booking, await lines_of(session, context, [booking.id]))
    new = await _change_stay_and_price(session, context, prop, booking, old, request)
    await _change_guest(session, context, booking, request)
    if request.source is not None:
        booking.channel_id = (await staff_source(session, context, request.source)).id
    if "notes" in request.model_fields_set:
        booking.internal_notes = request.notes or None
    booking.arrival_date, booking.departure_date = new.arrival, new.departure
    booking.adults, booking.children = new.adults, new.children
    booking.balance_due = booking.total_amount - booking.paid_amount
    booking.updated_by = str(context.user_id)
    session.add(booking)
    await _queue_channel_update(session, context, prop.id, [old, new])
    await session.commit()
    await session.refresh(booking)  # amounts as the database stores them
    log.info("Booking updated booking=%s", booking.id)
    return booking


async def cancel_booking(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    booking_id: UUID,
    reason: str | None,
) -> Reservation:
    """Cancel a booking and put its units back on sale. The record and payments stay. Commits."""
    await lock_property(session, context, prop.id)
    booking = await get_for_update(session, context, prop.id, booking_id)
    if booking.status == CANCELLED:
        raise BookingCancelledError
    lines = await lines_of(session, context, [booking.id])
    stay = stay_of(booking, lines)
    await inventory.release_units(session, context, stay.room_type_id, stay.nights, stay.units)
    for line in lines:
        line.status = CANCELLED
        session.add(line)
    booking.status = CANCELLED
    booking.cancelled_at = dt.datetime.now(dt.UTC)
    booking.cancel_note = reason or None
    booking.updated_by = str(context.user_id)
    session.add(booking)
    await _queue_channel_update(session, context, prop.id, [stay])
    await session.commit()
    await session.refresh(booking)  # amounts as the database stores them
    log.info("Booking cancelled booking=%s", booking.id)
    return booking
