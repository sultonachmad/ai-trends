"""What the front desk sees today, in the property's time zone."""

import datetime as dt
import logging
from uuid import UUID

from sqlalchemy import and_, or_
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Channel, Guest, Property, Reservation, ReservationUnit, Unit, UnitType
from app.schemas.apoa import ApoaCounts
from app.schemas.end_of_day import DayCloseState
from app.schemas.front_desk import FrontDeskEntry, FrontDeskRoom, FrontDeskToday, RoomToday
from app.services import calendar_dates as dates_of
from app.services.bill_taxes import with_tax
from app.services.booking_reads import _by_id
from app.services.bookings import balance_to_collect, lines_of
from app.services.closed_days import oldest_unclosed
from app.services.room_assignment import room_name
from app.services.stay_status import (
    CHECKED_OUT,
    CONFIRMED,
    IN_HOUSE,
    LEFT_EARLY,
    NO_SHOW,
    NO_SHOW_AT,
)
from app.tenancy.business_settings import resolve_property_settings
from app.tenancy.context import TenantContext
from app.tenancy.timezones import property_zone

log = logging.getLogger(__name__)

ATTENTION_DAYS = 7  # unprocessed arrivals older than this are left alone
MAX_ROWS = 500


def _entry_room(line: ReservationUnit, units: dict[UUID, Unit]) -> FrontDeskRoom:
    unit = units.get(line.unit_id) if line.unit_id else None
    return FrontDeskRoom(
        line_id=line.id,
        unit_id=line.unit_id,
        name=room_name(unit) if unit else None,
        hk_status=unit.hk_status if unit else None,
        service_status=unit.service_status if unit else None,
        locked=line.is_assignment_locked,
    )


def is_on_day(moment: dt.datetime | None, timezone: str, day: dt.date) -> bool:
    """Whether this moment falls on `day` at the property."""
    return moment is not None and moment.astimezone(property_zone(timezone)).date() == day


def _is_overdue(booking: Reservation, today: dt.date) -> bool:
    if booking.status == CONFIRMED:
        return booking.arrival_date < today
    return booking.status == IN_HOUSE and booking.departure_date < today


async def read_entries(
    session: AsyncSession,
    context: TenantContext,
    bookings: list[Reservation],
    today: dt.date,
    timezone: str,
) -> list[FrontDeskEntry]:
    lines = await lines_of(session, context, [booking.id for booking in bookings])
    by_booking: dict[UUID, list[ReservationUnit]] = {booking.id: [] for booking in bookings}
    for line in lines:
        by_booking[line.reservation_id].append(line)
    units = await _by_id(session, context, Unit, {line.unit_id for line in lines if line.unit_id})
    types = await _by_id(session, context, UnitType, {line.unit_type_id for line in lines})
    guests = await _by_id(
        session, context, Guest, {b.booker_guest_id for b in bookings if b.booker_guest_id}
    )
    sources = await _by_id(session, context, Channel, {b.channel_id for b in bookings})
    result = []
    for booking in bookings:
        own = by_booking[booking.id]
        guest = guests.get(booking.booker_guest_id) if booking.booker_guest_id else None
        result.append(
            FrontDeskEntry(
                id=booking.id,
                number=booking.confirmation_no,
                status=booking.status,
                guest_name=guest.full_name if guest else "",
                guest_phone=(guest.whatsapp_phone or guest.phone) if guest else None,
                arrival=booking.arrival_date,
                departure=booking.departure_date,
                nights=(booking.departure_date - booking.arrival_date).days,
                room_type=types[own[0].unit_type_id].name,
                units=len(own),
                adults=booking.adults,
                children=booking.children,
                source=sources[booking.channel_id].name,
                total_amount=booking.total_amount,
                total_with_tax=with_tax(booking),
                balance_due=balance_to_collect(booking),
                overdue=_is_overdue(booking, today),
                can_undo=booking.status == IN_HOUSE
                and all(is_on_day(line.checked_in_at, timezone, today) for line in own),
                rooms=[_entry_room(line, units) for line in own],
            )
        )
    return result


async def _bookings(
    session: AsyncSession, context: TenantContext, property_id: UUID, *conditions: object
) -> list[Reservation]:
    rows = await session.exec(
        select(Reservation)
        .where(
            col(Reservation.tenant_id) == context.tenant_id,
            col(Reservation.property_id) == property_id,
            *conditions,
        )
        .order_by(col(Reservation.arrival_date), col(Reservation.id))
        .limit(MAX_ROWS)
    )
    return list(rows.all())


async def _rooms_today(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    in_house: list[FrontDeskEntry],
) -> list[RoomToday]:
    units = (
        await session.exec(
            select(Unit)
            .where(
                col(Unit.tenant_id) == context.tenant_id,
                col(Unit.property_id) == property_id,
                col(Unit.is_active).is_(True),
            )
            .order_by(col(Unit.sort_order), col(Unit.code))
            .limit(MAX_ROWS)
        )
    ).all()
    types = await _by_id(session, context, UnitType, {unit.unit_type_id for unit in units})
    occupant = {room.unit_id: entry for entry in in_house for room in entry.rooms if room.unit_id}
    return [
        RoomToday(
            id=unit.id,
            name=room_name(unit),
            room_type=types[unit.unit_type_id].name,
            hk_status=unit.hk_status,
            fo_status=unit.fo_status,
            service_status=unit.service_status,
            guest_name=occupant[unit.id].guest_name if unit.id in occupant else None,
            booking_id=occupant[unit.id].id if unit.id in occupant else None,
            departure=occupant[unit.id].departure if unit.id in occupant else None,
        )
        for unit in units
    ]


async def _done_today(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    timezone: str,
    today: dt.date,
) -> list[Reservation]:
    """Stays checked out or marked no-show today that can still be undone."""
    start = dt.datetime.combine(today, dt.time.min, property_zone(timezone)).astimezone(dt.UTC)
    left_today = select(col(ReservationUnit.reservation_id)).where(
        col(ReservationUnit.tenant_id) == context.tenant_id,
        col(ReservationUnit.checked_out_at) >= start,
    )
    detail = col(Reservation.source_detail)
    found = await _bookings(
        session,
        context,
        property_id,
        or_(
            and_(col(Reservation.status) == CHECKED_OUT, col(Reservation.id).in_(left_today)),
            and_(
                col(Reservation.status) == NO_SHOW,
                detail[NO_SHOW_AT].astext >= start.isoformat(),
            ),
        ),
    )
    return [booking for booking in found if not booking.source_detail.get(LEFT_EARLY)]


async def read_today(
    session: AsyncSession, context: TenantContext, prop: Property, *, with_apoa: bool = False
) -> FrontDeskToday:
    property_id, timezone = prop.id, prop.timezone
    today = dates_of.property_today(timezone)
    earliest = today - dt.timedelta(days=ATTENTION_DAYS)
    arriving = await _bookings(
        session,
        context,
        property_id,
        col(Reservation.status) == CONFIRMED,
        col(Reservation.arrival_date) >= earliest,
        col(Reservation.arrival_date) <= today,
    )
    staying = await _bookings(session, context, property_id, col(Reservation.status) == IN_HOUSE)
    done = await _done_today(session, context, property_id, timezone, today)
    entries = await read_entries(session, context, [*arriving, *staying, *done], today, timezone)
    arrivals = entries[: len(arriving)]
    in_house = entries[len(arriving) : len(arriving) + len(staying)]
    return FrontDeskToday(
        date=today,
        arrivals=arrivals,
        in_house=in_house,
        departures=[entry for entry in in_house if entry.departure <= today],
        done_today=entries[len(arriving) + len(staying) :],
        rooms=await _rooms_today(session, context, property_id, in_house),
        apoa=await _apoa_counts(session, context, prop) if with_apoa else ApoaCounts(),
        day_close=DayCloseState(unclosed=await oldest_unclosed(session, context, prop, today)),
        problems=await _problems(session, context, prop),
        poll_seconds=resolve_property_settings(prop.settings).hk_poll_seconds,
    )


async def _problems(session: AsyncSession, context: TenantContext, prop: Property) -> list:
    # Imported here: the housekeeping board builds on this module (stays, rooms).
    from app.services.housekeeping_board import open_problems

    return await open_problems(session, context, prop)


async def _apoa_counts(session: AsyncSession, context: TenantContext, prop: Property) -> ApoaCounts:
    # Imported here: the APOA list builds on this module's neighbours (bookings, rooms).
    from app.services.apoa_reads import counts

    try:
        return await counts(session, context, prop)
    except Exception:  # noqa: BLE001 — the banner must never take the front desk down
        log.exception("APOA counts failed property=%s", prop.id)
        return ApoaCounts()
