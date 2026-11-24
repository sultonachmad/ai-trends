"""Check-in, check-out, no-show and same-day undo.

Each action runs in one transaction under the property lock, then the booking lock, then
the rooms. A multi-room booking moves as a whole.
"""

import datetime as dt
import logging
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Property, Reservation, ReservationUnit, Unit
from app.schemas.front_desk import CheckInRequest, CheckOutRequest, UndoRequest
from app.services import calendar_dates as dates_of
from app.services import front_desk_errors as errors
from app.services import inventory, tenant_audit
from app.services.bookings import (
    BookingNotFoundError,
    _queue_channel_update,
    get_for_update,
    lines_of,
    lock_property,
    occupied_unit_ids,
    stay_of,
)
from app.services.front_desk_reads import is_on_day
from app.services.room_assignment import _locked_units, room_name
from app.services.stay_changes import shorten_stay
from app.services.stay_status import (
    CHECKED_OUT,
    CONFIRMED,
    IN_HOUSE,
    LEFT_EARLY,
    NO_SHOW,
    NO_SHOW_AT,
)
from app.services.unit_status import (
    DIRTY,
    OCCUPIED,
    OUT_OF_ORDER,
    VACANT,
    is_ready,
    set_unit_status,
)
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

ENTITY = "reservation"


async def _locked(
    session: AsyncSession, context: TenantContext, prop: Property, booking_id: UUID
) -> tuple[Reservation, list[ReservationUnit]]:
    await lock_property(session, context, prop.id)
    try:
        booking = await get_for_update(session, context, prop.id, booking_id)
    except BookingNotFoundError:
        raise errors.NotFoundError from None
    return booking, await lines_of(session, context, [booking.id])


def _set_status(booking: Reservation, lines: list[ReservationUnit], status: str) -> None:
    booking.status = status
    for line in lines:
        line.status = status


async def _finish(
    session: AsyncSession,
    context: TenantContext,
    booking: Reservation,
    lines: list[ReservationUnit],
    event: str,
    payload: dict | None = None,
) -> Reservation:
    booking.updated_by = str(context.user_id)
    session.add(booking)
    session.add_all(lines)
    await tenant_audit.record(
        session,
        context,
        event,
        property_id=booking.property_id,
        entity_table=ENTITY,
        entity_id=booking.id,
        payload=payload or {},
    )
    try:
        await session.commit()
    except IntegrityError:  # the database's own guard against a double assignment
        await session.rollback()
        raise errors.RoomTakenError from None
    await session.refresh(booking)
    log.info("%s booking=%s", event, booking.id)
    return booking


def _check_rooms(lines: list[ReservationUnit], units: dict[UUID, Unit], accept: bool) -> None:
    rooms = [units[line.unit_id] for line in lines]
    broken = [room_name(u) for u in rooms if u.service_status == OUT_OF_ORDER]
    if broken:
        raise errors.RoomOutOfOrderError(broken)
    occupied = [room_name(u) for u in rooms if u.fo_status == OCCUPIED]
    if occupied:
        raise errors.RoomOccupiedError(occupied)
    not_ready = [room_name(u) for u in rooms if not is_ready(u)]
    if not_ready and not accept:
        raise errors.RoomNotReadyError(not_ready)


async def check_in(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    booking_id: UUID,
    request: CheckInRequest,
) -> Reservation:
    """Put the guest in their rooms. Commits."""
    today = dates_of.property_today(prop.timezone)
    booking, lines = await _locked(session, context, prop, booking_id)
    if booking.status != CONFIRMED:
        raise errors.NotConfirmedError
    if not booking.arrival_date <= today < booking.departure_date:
        raise errors.OutsideStayError
    if any(line.unit_id is None for line in lines):
        raise errors.RoomsMissingError
    units = await _locked_units(session, context, [line.unit_id for line in lines])
    _check_rooms(lines, units, request.accept_not_ready)
    now = dt.datetime.now(dt.UTC)
    for line in lines:
        line.checked_in_at, line.checked_in_by = now, str(context.user_id)
        set_unit_status(session, context, units[line.unit_id], fo=OCCUPIED)
    _set_status(booking, lines, IN_HOUSE)
    return await _finish(session, context, booking, lines, "booking.checked_in")


async def _leave_early(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    booking: Reservation,
    lines: list[ReservationUnit],
    today: dt.date,
    request: CheckOutRequest,
) -> dict:
    """Shorten the stay; returns what changed, for the history."""
    last_day = max(today, booking.arrival_date + dates_of.ONE_DAY)
    if last_day >= booking.departure_date:
        return {"early": request.early}
    old = stay_of(booking, lines)
    total_before = booking.total_amount
    new = await shorten_stay(
        session,
        context,
        prop,
        booking,
        lines,
        old,
        last_day,
        keep_price=request.early == "keep_price",
    )
    booking.departure_date = last_day
    booking.balance_due = booking.total_amount - booking.paid_amount
    if booking.paid_amount > booking.total_amount:
        booking.source_detail = {**booking.source_detail, "refund_due": True}
    await _queue_channel_update(session, context, prop.id, [old, new])
    return {
        "early": request.early,
        "total_before": str(total_before),
        "total_after": str(booking.total_amount),
        "nights_removed": old.night_count - new.night_count,
    }


async def check_out(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    booking_id: UUID,
    request: CheckOutRequest,
) -> Reservation:
    """End the stay; rooms become vacant and dirty. Commits."""
    today = dates_of.property_today(prop.timezone)
    booking, lines = await _locked(session, context, prop, booking_id)
    if booking.status != IN_HOUSE:
        raise errors.NotInHouseError
    leaving_early = today < booking.departure_date
    if leaving_early and request.early is None:
        raise errors.EarlyChoiceNeededError
    payload: dict = {}
    if leaving_early:
        payload = await _leave_early(session, context, prop, booking, lines, today, request)
    units = await _locked_units(session, context, [line.unit_id for line in lines])
    now = dt.datetime.now(dt.UTC)
    for line in lines:
        line.checked_out_at, line.checked_out_by = now, str(context.user_id)
        set_unit_status(session, context, units[line.unit_id], fo=VACANT, hk=DIRTY)
    _set_status(booking, lines, CHECKED_OUT)
    return await _finish(session, context, booking, lines, "booking.checked_out", payload)


async def mark_no_show(
    session: AsyncSession, context: TenantContext, prop: Property, booking_id: UUID
) -> Reservation:
    """The guest never came: their nights go back on sale. Payments stay. Commits."""
    today = dates_of.property_today(prop.timezone)
    booking, lines = await _locked(session, context, prop, booking_id)
    if booking.status != CONFIRMED or booking.arrival_date > today:
        raise errors.CannotNoShowError
    stay = stay_of(booking, lines)
    await inventory.release_units(session, context, stay.room_type_id, stay.nights, stay.units)
    await _queue_channel_update(session, context, prop.id, [stay])
    _set_status(booking, lines, NO_SHOW)
    booking.source_detail = {
        **booking.source_detail,
        NO_SHOW_AT: dt.datetime.now(dt.UTC).isoformat(),
    }
    return await _finish(session, context, booking, lines, "booking.no_show")


async def _undo_check_in(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    lines: list[ReservationUnit],
    booking: Reservation,
    today: dt.date,
) -> None:
    if not all(is_on_day(line.checked_in_at, prop.timezone, today) for line in lines):
        raise errors.UndoNotAllowedError
    units = await _locked_units(session, context, [line.unit_id for line in lines])
    for line in lines:
        line.checked_in_at, line.checked_in_by = None, None
        set_unit_status(session, context, units[line.unit_id], fo=VACANT)
    _set_status(booking, lines, CONFIRMED)


async def _undo_check_out(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    lines: list[ReservationUnit],
    booking: Reservation,
    today: dt.date,
) -> None:
    if booking.source_detail.get(LEFT_EARLY) or not all(
        is_on_day(line.checked_out_at, prop.timezone, today) for line in lines
    ):
        raise errors.UndoNotAllowedError
    unit_ids = [line.unit_id for line in lines]
    units = await _locked_units(session, context, unit_ids)
    if any(unit.fo_status == OCCUPIED for unit in units.values()) or await occupied_unit_ids(
        session, context, unit_ids, lines[0].start_at, lines[0].blocked_until, booking.id
    ):
        raise errors.UndoNotAllowedError
    for line in lines:
        line.checked_out_at, line.checked_out_by = None, None
        set_unit_status(session, context, units[line.unit_id], fo=OCCUPIED)
    _set_status(booking, lines, IN_HOUSE)


async def _undo_no_show(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    lines: list[ReservationUnit],
    booking: Reservation,
    today: dt.date,
) -> None:
    marked = booking.source_detail.get(NO_SHOW_AT)
    if not marked or not is_on_day(dt.datetime.fromisoformat(marked), prop.timezone, today):
        raise errors.UndoNotAllowedError
    stay = stay_of(booking, lines)
    in_use = (await inventory.units_in_use(session, context, [stay.room_type_id])).get(
        stay.room_type_id, 0
    )
    sold = await inventory.take_units(
        session, context, prop.id, stay.room_type_id, stay.nights, stay.units, in_use
    )
    if any(count > in_use for night, count in sold.items() if night >= today):
        await session.rollback()
        raise errors.NoRoomsLeftError
    assigned = [line.unit_id for line in lines if line.unit_id]
    taken = await occupied_unit_ids(
        session, context, assigned, lines[0].start_at, lines[0].blocked_until, booking.id
    )
    for line in lines:
        if line.unit_id in taken:
            line.unit_id = None
    await _queue_channel_update(session, context, prop.id, [stay])
    booking.source_detail = {k: v for k, v in booking.source_detail.items() if k != NO_SHOW_AT}
    _set_status(booking, lines, CONFIRMED)


async def undo(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    booking_id: UUID,
    request: UndoRequest,
) -> Reservation:
    """Take back today's check-in, check-out or no-show, with a reason. Commits."""
    today = dates_of.property_today(prop.timezone)
    booking, lines = await _locked(session, context, prop, booking_id)
    was = booking.status
    if was == IN_HOUSE:
        await _undo_check_in(session, context, prop, lines, booking, today)
    elif was == CHECKED_OUT:
        await _undo_check_out(session, context, prop, lines, booking, today)
    elif was == NO_SHOW:
        await _undo_no_show(session, context, prop, lines, booking, today)
    else:
        raise errors.UndoNotAllowedError
    payload = {"undone": was, "reason": request.reason}
    return await _finish(session, context, booking, lines, "booking.front_desk_undo", payload)
