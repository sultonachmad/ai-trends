"""Giving a booking its real rooms, and moving guests between them."""

import logging
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Property, Reservation, ReservationUnit, Unit
from app.schemas.front_desk import AssignRoomRequest, FreeRoom
from app.services import front_desk_errors as errors
from app.services import tenant_audit
from app.services.bookings import (
    BookingNotFoundError,
    get_for_update,
    lines_of,
    lock_property,
    occupied_unit_ids,
)
from app.services.room_blocks import blocked_unit_ids
from app.services.stay_status import CONFIRMED, IN_HOUSE
from app.services.unit_status import (
    DIRTY,
    OCCUPIED,
    OUT_OF_ORDER,
    VACANT,
    is_ready,
    set_unit_status,
)
from app.tenancy.business_settings import resolve_property_settings
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

ENTITY = "reservation"
ASSIGNABLE = (CONFIRMED, IN_HOUSE)


def room_name(unit: Unit) -> str:
    return unit.name or unit.code


async def free_rooms(
    session: AsyncSession, context: TenantContext, prop: Property, booking_id: UUID
) -> list[FreeRoom]:
    """Rooms of the booked type free for the whole stay, ready ones first."""
    lines = await lines_of(session, context, [booking_id])
    if not lines or lines[0].property_id != prop.id:
        raise errors.NotFoundError
    first = lines[0]
    units = (
        await session.exec(
            select(Unit)
            .where(
                col(Unit.tenant_id) == context.tenant_id,
                col(Unit.unit_type_id) == first.unit_type_id,
                col(Unit.is_active).is_(True),
                col(Unit.is_sellable).is_(True),
                col(Unit.service_status) != OUT_OF_ORDER,
            )
            .order_by(col(Unit.sort_order))
        )
    ).all()
    taken = await occupied_unit_ids(
        session, context, [unit.id for unit in units], first.start_at, first.blocked_until
    )
    off_sale = await blocked_unit_ids(
        session, context, [unit.id for unit in units], first.start_at, first.blocked_until
    )
    in_house = first.status == IN_HOUSE
    free = [
        unit
        for unit in units
        if unit.id not in taken | off_sale and not (in_house and unit.fo_status == OCCUPIED)
    ]
    ready_when = resolve_property_settings(prop.settings).hk_ready_when
    ordered = sorted(free, key=lambda unit: (not is_ready(unit, ready_when), unit.sort_order))
    return [
        FreeRoom(
            id=unit.id,
            name=room_name(unit),
            hk_status=unit.hk_status,
            service_status=unit.service_status,
            ready=is_ready(unit, ready_when),
        )
        for unit in ordered
    ]


async def _locked_line(
    session: AsyncSession, context: TenantContext, prop: Property, line_id: UUID
) -> tuple[Reservation, ReservationUnit]:
    """Property, booking and line, locked in that order."""
    property_id = prop.id
    reservation_id = (
        await session.exec(
            select(col(ReservationUnit.reservation_id)).where(
                col(ReservationUnit.tenant_id) == context.tenant_id,
                col(ReservationUnit.property_id) == property_id,
                col(ReservationUnit.id) == line_id,
            )
        )
    ).first()
    if reservation_id is None:
        raise errors.NotFoundError
    await lock_property(session, context, property_id)
    try:
        booking = await get_for_update(session, context, property_id, reservation_id)
    except BookingNotFoundError:
        raise errors.NotFoundError from None
    line = (
        await session.exec(
            select(ReservationUnit)
            .where(
                col(ReservationUnit.tenant_id) == context.tenant_id,
                col(ReservationUnit.id) == line_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).one()
    return booking, line


async def _locked_units(
    session: AsyncSession, context: TenantContext, unit_ids: list[UUID]
) -> dict[UUID, Unit]:
    if not unit_ids:
        return {}
    rows = await session.exec(
        select(Unit)
        .where(col(Unit.tenant_id) == context.tenant_id, col(Unit.id).in_(unit_ids))
        .order_by(col(Unit.id))
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return {unit.id: unit for unit in rows.all()}


def _check_target(
    unit: Unit | None, line: ReservationUnit, request: AssignRoomRequest, ready_when: str
) -> None:
    if (
        unit is None
        or unit.unit_type_id != line.unit_type_id
        or not unit.is_active
        or not unit.is_sellable
    ):
        raise errors.WrongRoomError
    if unit.service_status == OUT_OF_ORDER:
        raise errors.RoomOutOfOrderError([room_name(unit)])
    if line.status != IN_HOUSE:
        return
    if unit.fo_status == OCCUPIED:
        raise errors.RoomOccupiedError([room_name(unit)])
    if not is_ready(unit, ready_when) and not request.accept_not_ready:
        raise errors.RoomNotReadyError([room_name(unit)])


async def assign_room(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    line_id: UUID,
    request: AssignRoomRequest,
) -> Reservation:
    """Assign, clear or change a line's room; moves an in-house guest. Commits."""
    booking, line = await _locked_line(session, context, prop, line_id)
    if booking.status not in ASSIGNABLE:
        raise errors.NotAssignableError
    if line.unit_id == request.unit_id:
        await session.commit()
        return booking
    if line.is_assignment_locked:
        raise errors.RoomLockedError
    if request.unit_id is None and line.status == IN_HOUSE:
        raise errors.RoomRequiredError
    wanted = [unit for unit in (line.unit_id, request.unit_id) if unit is not None]
    units = await _locked_units(session, context, wanted)
    previous = units.get(line.unit_id) if line.unit_id else None
    if request.unit_id is not None:
        target = units.get(request.unit_id)
        ready_when = resolve_property_settings(prop.settings).hk_ready_when
        _check_target(target, line, request, ready_when)
        if await occupied_unit_ids(
            session, context, [request.unit_id], line.start_at, line.blocked_until
        ):
            raise errors.RoomTakenError([room_name(target)])
        if await blocked_unit_ids(
            session, context, [request.unit_id], line.start_at, line.blocked_until
        ):
            raise errors.RoomOutOfOrderError([room_name(target)])
    if line.status == IN_HOUSE:
        set_unit_status(session, context, previous, fo=VACANT, hk=DIRTY)
        set_unit_status(session, context, units[request.unit_id], fo=OCCUPIED)
    line.unit_id = request.unit_id
    session.add(line)
    await tenant_audit.record(
        session,
        context,
        "booking.room_moved" if line.status == IN_HOUSE else "booking.room_assigned",
        property_id=booking.property_id,
        entity_table=ENTITY,
        entity_id=booking.id,
        payload={
            "from": str(previous.id) if previous else None,
            "to": str(request.unit_id) if request.unit_id else None,
        },
    )
    try:
        await session.commit()
    except IntegrityError:  # the database's own guard against a double assignment
        await session.rollback()
        raise errors.RoomTakenError from None
    log.info("Room assigned booking=%s line=%s", booking.id, line_id)
    return booking


async def lock_room(
    session: AsyncSession, context: TenantContext, prop: Property, line_id: UUID, locked: bool
) -> Reservation:
    """Keep (or stop keeping) this guest in this room. Commits."""
    booking, line = await _locked_line(session, context, prop, line_id)
    if booking.status not in ASSIGNABLE:
        raise errors.NotAssignableError
    line.is_assignment_locked = locked
    session.add(line)
    await tenant_audit.record(
        session,
        context,
        "booking.room_locked" if locked else "booking.room_unlocked",
        property_id=booking.property_id,
        entity_table=ENTITY,
        entity_id=booking.id,
        payload={"unit": str(line.unit_id) if line.unit_id else None},
    )
    await session.commit()
    return booking
