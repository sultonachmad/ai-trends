"""Reading bookings: the list, one booking in detail, and a quote for a stay."""

import datetime as dt
from decimal import Decimal
from uuid import UUID

from sqlalchemy import ColumnElement, func, or_, tuple_
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import (
    Channel,
    Guest,
    Payment,
    Property,
    RatePlan,
    Reservation,
    ReservationDailyRate,
    ReservationUnit,
    UnitType,
)
from app.schemas.bookings import (
    BookingDetail,
    BookingGuest,
    BookingNight,
    BookingPage,
    BookingPayment,
    BookingQuote,
    BookingQuoteRequest,
    BookingRead,
    BookingSource,
    BookingTab,
    BookingTerms,
    NamedRef,
    PaymentState,
    QuoteNight,
)
from app.services import calendar_dates as dates_of
from app.services.booking_pricing import suggested_total
from app.services.booking_stays import Stay, check_stay
from app.services.bookings import (
    CANCELLED,
    CONFIRMED,
    PRICE_EDITED,
    BookingNotFoundError,
    lines_of,
    stay_of,
)
from app.services.inventory import sold_by_night, units_in_use
from app.tenancy.business_settings import resolve_property_settings
from app.tenancy.context import TenantContext
from app.tenancy.timezones import property_zone

DEFAULT_PAGE_SIZE = 30
MAX_PAGE_SIZE = 100
CAPTURED = "captured"
ZERO = Decimal("0")


class InvalidCursorError(Exception):
    """The paging cursor is not one this list handed out."""


def payment_state(total: Decimal, paid: Decimal) -> PaymentState:
    if paid > total:
        return "overpaid"
    if paid == total:
        return "paid" if total > ZERO or paid > ZERO else "unpaid"
    return "partly_paid" if paid > ZERO else "unpaid"


async def _by_id(session: AsyncSession, context: TenantContext, model, ids: set[UUID]) -> dict:  # noqa: ANN001
    if not ids:
        return {}
    rows = await session.exec(
        select(model).where(col(model.tenant_id) == context.tenant_id, col(model.id).in_(ids))
    )
    return {row.id: row for row in rows.all()}


async def _oversold_bookings(
    session: AsyncSession,
    context: TenantContext,
    bookings: list[Reservation],
    stays: dict[UUID, Stay],
    today: dt.date,
) -> set[UUID]:
    """Ids of confirmed bookings with a night, today or later, that has more sold than units."""
    live = [b for b in bookings if b.status == CONFIRMED and b.departure_date > today]
    if not live:
        return set()
    room_ids = list({stays[b.id].room_type_id for b in live})
    first = max(min(b.arrival_date for b in live), today)
    last = max(b.departure_date for b in live)
    sold = await sold_by_night(session, context, room_ids, first, last)
    units = await units_in_use(session, context, room_ids)
    at_risk = set()
    for booking in live:
        stay = stays[booking.id]
        in_use = units.get(stay.room_type_id, 0)
        if any(
            sold.get((stay.room_type_id, night), 0) > in_use
            for night in stay.nights
            if night >= today
        ):
            at_risk.add(booking.id)
    return at_risk


async def read_many(
    session: AsyncSession, context: TenantContext, prop: Property, bookings: list[Reservation]
) -> list[BookingRead]:
    """List rows for stored bookings, in the order given."""
    lines = await lines_of(session, context, [booking.id for booking in bookings])
    by_booking: dict[UUID, list[ReservationUnit]] = {booking.id: [] for booking in bookings}
    for line in lines:
        by_booking[line.reservation_id].append(line)
    stays = {b.id: stay_of(b, by_booking[b.id]) for b in bookings if by_booking[b.id]}
    rooms = await _by_id(session, context, UnitType, {s.room_type_id for s in stays.values()})
    plans = await _by_id(session, context, RatePlan, {s.rate_plan_id for s in stays.values()})
    guests = await _by_id(
        session, context, Guest, {b.booker_guest_id for b in bookings if b.booker_guest_id}
    )
    sources = await _by_id(session, context, Channel, {b.channel_id for b in bookings})
    today = dates_of.property_today(prop.timezone)
    at_risk = await _oversold_bookings(session, context, bookings, stays, today)
    result = []
    for booking in bookings:
        stay = stays[booking.id]
        guest = guests.get(booking.booker_guest_id) if booking.booker_guest_id else None
        source = sources[booking.channel_id]
        result.append(
            BookingRead(
                id=booking.id,
                number=booking.confirmation_no,
                status=CANCELLED if booking.status == CANCELLED else CONFIRMED,
                arrival=stay.arrival,
                departure=stay.departure,
                nights=len(stay.nights),
                room_type=NamedRef(id=stay.room_type_id, name=rooms[stay.room_type_id].name),
                rate_plan=NamedRef(id=stay.rate_plan_id, name=plans[stay.rate_plan_id].name),
                units=stay.units,
                adults=stay.adults,
                children=stay.children,
                guest=BookingGuest(
                    id=guest.id if guest else None,
                    name=guest.full_name if guest else "",
                    phone=guest.whatsapp_phone or guest.phone if guest else None,
                ),
                source=BookingSource(
                    code=source.code, name=source.name, is_direct=source.is_direct
                ),
                total_amount=booking.total_amount,
                paid_amount=booking.paid_amount,
                balance_due=booking.balance_due,
                payment_state=payment_state(booking.total_amount, booking.paid_amount),
                price_edited=bool(booking.source_detail.get(PRICE_EDITED)),
                overbooking_risk=booking.id in at_risk,
                notes=booking.internal_notes,
                cancel_note=booking.cancel_note,
                cancelled_at=booking.cancelled_at,
                created_at=booking.booked_at,
            )
        )
    return result


async def _nightly(
    session: AsyncSession, context: TenantContext, booking_id: UUID
) -> list[BookingNight]:
    """The booking's price per night, all its units together."""
    rows = await session.exec(
        select(col(ReservationDailyRate.stay_date), func.sum(col(ReservationDailyRate.amount)))
        .join(
            ReservationUnit,
            (col(ReservationUnit.tenant_id) == col(ReservationDailyRate.tenant_id))
            & (col(ReservationUnit.id) == col(ReservationDailyRate.reservation_unit_id)),
        )
        .where(
            col(ReservationDailyRate.tenant_id) == context.tenant_id,
            col(ReservationUnit.reservation_id) == booking_id,
        )
        .group_by(col(ReservationDailyRate.stay_date))
        .order_by(col(ReservationDailyRate.stay_date))
    )
    return [BookingNight(date=night, amount=amount) for night, amount in rows.all()]


async def captured_payments(
    session: AsyncSession, context: TenantContext, booking_id: UUID
) -> list[Payment]:
    """Money received for the booking that still counts (removed entries are left out)."""
    rows = await session.exec(
        select(Payment)
        .where(
            col(Payment.tenant_id) == context.tenant_id,
            col(Payment.reservation_id) == booking_id,
            col(Payment.direction) == "inbound",
            col(Payment.status) == CAPTURED,
        )
        .order_by(col(Payment.captured_at), col(Payment.created_at))
    )
    return list(rows.all())


async def read_detail(
    session: AsyncSession, context: TenantContext, prop: Property, booking: Reservation
) -> BookingDetail:
    [summary] = await read_many(session, context, prop, [booking])
    zone = property_zone(prop.timezone)
    payments = [
        BookingPayment(
            id=payment.id,
            amount=payment.captured_amount,
            method=payment.method,
            received_on=(payment.captured_at or payment.created_at).astimezone(zone).date(),
            note=(payment.metadata_ or {}).get("note"),
            recorded_at=payment.created_at,
        )
        for payment in await captured_payments(session, context, booking.id)
    ]
    snapshot = booking.cancellation_policy_snapshot or {}
    terms = (
        BookingTerms(
            non_refundable=bool(snapshot.get("non_refundable")),
            free_cancellation_days=snapshot.get("free_cancellation_days"),
        )
        if snapshot
        else None
    )
    return BookingDetail(
        **summary.model_dump(),
        nightly=await _nightly(session, context, booking.id),
        payments=payments,
        terms=terms,
    )


async def find_booking(
    session: AsyncSession, context: TenantContext, property_id: UUID, booking_id: UUID
) -> Reservation:
    booking = (
        await session.exec(
            select(Reservation).where(
                col(Reservation.tenant_id) == context.tenant_id,
                col(Reservation.property_id) == property_id,
                col(Reservation.id) == booking_id,
            )
        )
    ).first()
    if booking is None:
        raise BookingNotFoundError
    return booking


# ---- the list ---------------------------------------------------------------------------


def _tab_filter(tab: BookingTab, today: dt.date) -> tuple[list[ColumnElement[bool]], object, bool]:
    """(conditions, sort column, newest first) for a tab."""
    confirmed = col(Reservation.status) != CANCELLED
    arrival, departure = col(Reservation.arrival_date), col(Reservation.departure_date)
    if tab == "upcoming":
        return [confirmed, arrival > today], arrival, False
    if tab == "staying":
        return [confirmed, arrival <= today, departure > today], departure, False
    if tab == "past":
        return [confirmed, departure <= today], departure, True
    return [col(Reservation.status) == CANCELLED], col(Reservation.cancelled_at), True


def _parse_cursor(cursor: str, tab: BookingTab) -> tuple[object, UUID]:
    try:
        value, booking_id = cursor.split("|")
        parsed = (
            dt.datetime.fromisoformat(value) if tab == "cancelled" else dt.date.fromisoformat(value)
        )
        if isinstance(parsed, dt.datetime) and parsed.tzinfo is None:
            raise ValueError("cursor time has no timezone")
        return parsed, UUID(booking_id)
    except ValueError as exc:
        raise InvalidCursorError from exc


def _search(query: str) -> ColumnElement[bool]:
    """Guest name or booking number containing the text (wildcards taken literally)."""
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    return or_(
        col(Guest.full_name).ilike(pattern, escape="\\"),
        col(Reservation.confirmation_no).ilike(pattern, escape="\\"),
    )


async def list_bookings(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    tab: BookingTab,
    query: str | None,
    limit: int,
    cursor: str | None,
) -> BookingPage:
    today = dates_of.property_today(prop.timezone)
    conditions, sort_column, newest_first = _tab_filter(tab, today)
    statement = (
        select(Reservation)
        .outerjoin(
            Guest,
            (col(Guest.tenant_id) == col(Reservation.tenant_id))
            & (col(Guest.id) == col(Reservation.booker_guest_id)),
        )
        .where(
            col(Reservation.tenant_id) == context.tenant_id,
            col(Reservation.property_id) == prop.id,
            *conditions,
        )
    )
    if query:
        statement = statement.where(_search(query))
    if cursor:
        key = tuple_(sort_column, col(Reservation.id))
        after = tuple_(*_parse_cursor(cursor, tab))
        statement = statement.where(key < after if newest_first else key > after)
    order = (
        (sort_column.desc(), col(Reservation.id).desc())
        if newest_first
        else (sort_column.asc(), col(Reservation.id).asc())
    )
    rows = list((await session.exec(statement.order_by(*order).limit(limit + 1))).all())
    page, more = rows[:limit], len(rows) > limit
    next_cursor = None
    if more:
        last = page[-1]
        value = {
            "upcoming": last.arrival_date,
            "staying": last.departure_date,
            "past": last.departure_date,
            "cancelled": last.cancelled_at,
        }[tab]
        # a cancelled booking without a time (imported data) cannot anchor a next page
        next_cursor = f"{value.isoformat()}|{last.id}" if value is not None else None
    return BookingPage(items=await read_many(session, context, prop, page), next_cursor=next_cursor)


# ---- quoting ----------------------------------------------------------------------------


async def _own_units(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    booking_id: UUID | None,
    room_type_id: UUID,
) -> dict[dt.date, int]:
    """Units a confirmed booking already holds per night, so changing it does not count them."""
    if booking_id is None:
        return {}
    booking = (
        await session.exec(
            select(Reservation).where(
                col(Reservation.tenant_id) == context.tenant_id,
                col(Reservation.property_id) == property_id,
                col(Reservation.id) == booking_id,
                col(Reservation.status) != CANCELLED,
            )
        )
    ).first()
    if booking is None:
        return {}
    stay = stay_of(booking, await lines_of(session, context, [booking.id]))
    if stay.room_type_id != room_type_id:
        return {}
    return {night: stay.units for night in stay.nights}


async def quote(
    session: AsyncSession, context: TenantContext, prop: Property, request: BookingQuoteRequest
) -> BookingQuote:
    """Price and availability for a stay. Saves nothing."""
    settings = resolve_property_settings(prop.settings)
    stay = Stay(
        arrival=request.arrival,
        departure=request.departure,
        room_type_id=request.room_type_id,
        rate_plan_id=request.rate_plan_id,
        units=request.units,
        adults=request.adults,
        children=request.children,
    )
    checked = await check_stay(session, context, prop, settings, stay)
    own = await _own_units(session, context, prop.id, request.exclude_booking_id, stay.room_type_id)
    nights = [
        QuoteNight(
            date=night.date,
            amount=night.amount,
            available=night.available + own.get(night.date, 0),
            closed=night.closed,
        )
        for night in checked.nights
    ]
    arrival_rule = checked.nights[0].min_stay
    return BookingQuote(
        nights=nights,
        total_amount=suggested_total([night.amount for night in checked.nights], units=stay.units),
        # Short only where this booking would add to a full night: nights it already holds
        # (when changing a booking) are not held against it, as in `bookings._take`.
        short_dates=[
            night.date
            for night in nights
            if night.available < stay.units and stay.units > own.get(night.date, 0)
        ],
        closed_dates=[night.date for night in nights if night.closed],
        min_stay=arrival_rule if arrival_rule and arrival_rule > len(nights) else None,
        max_guests=checked.max_guests,
    )
