"""Room types: what a property sells and how many units of each it has.

A room type owns its units. Staff give a number; the units are created (and later
retired or brought back) to match it. Nothing is deleted: a room type that is no
longer sold is switched off, a unit that is no longer counted is retired, so history
that points at them stays readable.
"""

import logging
import uuid
from uuid import UUID

from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Property, Unit, UnitType
from app.schemas.rooms import (
    RoomTypeCreateRequest,
    RoomTypeRead,
    RoomTypeUpdateRequest,
    UnitRead,
)
from app.tenancy.business_settings import PropertySettings, resolve_property_settings
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

DEFAULT_BASE_OCCUPANCY = 2


class RoomTypeNotFoundError(Exception):
    """No such room type on the caller's property."""


class UnitNotFoundError(Exception):
    """No such unit in use on that room type."""


class RoomTypeNameTakenError(Exception):
    """Another active room type of the property already has this name."""


class TooManySwitchedOffError(Exception):
    """So many switched-off records that a new one may not be added; reuse an old one."""


class RoomTypeLimitError(Exception):
    """The property has as many active room types as it may."""

    def __init__(self, limit: int) -> None:
        super().__init__(f"room type limit reached ({limit})")
        self.limit = limit


class TooManyUnitsError(Exception):
    """More units than one room type may have."""

    def __init__(self, limit: int) -> None:
        super().__init__(f"unit limit exceeded ({limit})")
        self.limit = limit


def _default_unit_name(type_name: str, number: int) -> str:
    return f"{type_name} {number}"


async def _lock_property(session: AsyncSession, context: TenantContext, prop: Property) -> None:
    """Serialise changes to a property's room types (names and limits are checked by count)."""
    await session.exec(
        select(col(Property.id))
        .where(col(Property.tenant_id) == context.tenant_id, col(Property.id) == prop.id)
        .with_for_update()
    )


async def _units_of(
    session: AsyncSession, context: TenantContext, unit_type_ids: list[UUID]
) -> dict[UUID, list[Unit]]:
    """Every unit (in use or retired) of the given room types, in order."""
    grouped: dict[UUID, list[Unit]] = {unit_type_id: [] for unit_type_id in unit_type_ids}
    if not unit_type_ids:
        return grouped
    rows = await session.exec(
        select(Unit)
        .where(
            col(Unit.tenant_id) == context.tenant_id,
            col(Unit.unit_type_id).in_(unit_type_ids),
        )
        .order_by(col(Unit.sort_order), col(Unit.created_at))
    )
    for unit in rows.all():
        grouped[unit.unit_type_id].append(unit)
    return grouped


def _read(room: UnitType, units: list[Unit]) -> RoomTypeRead:
    return RoomTypeRead(
        id=room.id,
        name=room.name,
        kind=room.category,
        max_guests=room.max_occupancy,
        is_active=room.is_active,
        units=[
            UnitRead(id=unit.id, name=unit.name or unit.code) for unit in units if unit.is_active
        ],
    )


async def find_room_types(
    session: AsyncSession, context: TenantContext, property_id: UUID, *, active_only: bool = False
) -> list[UnitType]:
    """The property's room types in creation order."""
    statement = select(UnitType).where(
        col(UnitType.tenant_id) == context.tenant_id, col(UnitType.property_id) == property_id
    )
    if active_only:
        statement = statement.where(col(UnitType.is_active).is_(True))
    rows = await session.exec(
        statement.order_by(col(UnitType.sort_order), col(UnitType.created_at), col(UnitType.id))
    )
    return list(rows.all())


async def list_room_types(
    session: AsyncSession, context: TenantContext, property_id: UUID
) -> list[RoomTypeRead]:
    rooms = await find_room_types(session, context, property_id)
    units = await _units_of(session, context, [room.id for room in rooms])
    return [_read(room, units[room.id]) for room in rooms]


async def _get(
    session: AsyncSession, context: TenantContext, property_id: UUID, room_type_id: UUID
) -> UnitType:
    room = (
        await session.exec(
            select(UnitType)
            .where(
                col(UnitType.tenant_id) == context.tenant_id,
                col(UnitType.property_id) == property_id,
                col(UnitType.id) == room_type_id,
            )
            .with_for_update()
        )
    ).first()
    if room is None:
        raise RoomTypeNotFoundError
    return room


async def _check_name_free(
    session: AsyncSession, context: TenantContext, property_id: UUID, name: str, own_id: UUID | None
) -> None:
    statement = select(col(UnitType.id)).where(
        col(UnitType.tenant_id) == context.tenant_id,
        col(UnitType.property_id) == property_id,
        col(UnitType.is_active).is_(True),
        func.lower(col(UnitType.name)) == name.lower(),
    )
    if own_id is not None:
        statement = statement.where(col(UnitType.id) != own_id)
    if (await session.exec(statement)).first() is not None:
        raise RoomTypeNameTakenError


async def _check_room_type_limit(
    session: AsyncSession, context: TenantContext, property_id: UUID, settings: PropertySettings
) -> None:
    active = (
        await session.exec(
            select(func.count())
            .select_from(UnitType)
            .where(
                col(UnitType.tenant_id) == context.tenant_id,
                col(UnitType.property_id) == property_id,
                col(UnitType.is_active).is_(True),
            )
        )
    ).one()
    if int(active) >= settings.max_room_types:
        raise RoomTypeLimitError(settings.max_room_types)


def _new_unit(room: UnitType, number: int) -> Unit:
    return Unit(
        tenant_id=room.tenant_id,
        property_id=room.property_id,
        unit_type_id=room.id,
        code=f"{room.code}-{number:04d}",
        name=_default_unit_name(room.name, number),
        sort_order=number,
    )


def _resize(session: AsyncSession, room: UnitType, units: list[Unit], wanted: int) -> list[Unit]:
    """Bring the number of units in use to `wanted`: retire the last, or restore and add."""
    in_use = [unit for unit in units if unit.is_active]
    for unit in in_use[wanted:]:
        unit.is_active = False
        unit.is_sellable = False
        session.add(unit)
    missing = wanted - len(in_use)
    retired = [unit for unit in units if not unit.is_active]
    for unit in retired[: max(missing, 0)]:
        unit.is_active = True
        unit.is_sellable = True
        session.add(unit)
    created = [
        _new_unit(room, number)
        for number in range(len(units) + 1, len(units) + 1 + max(missing - len(retired), 0))
    ]
    session.add_all(created)
    return sorted([*units, *created], key=lambda unit: unit.sort_order)


async def create_room_type(
    session: AsyncSession, context: TenantContext, prop: Property, request: RoomTypeCreateRequest
) -> RoomTypeRead:
    """Create a room type with its units. Commits."""
    settings = resolve_property_settings(prop.settings)
    if request.units > settings.max_units_per_room_type:
        raise TooManyUnitsError(settings.max_units_per_room_type)
    property_id = prop.id
    await _lock_property(session, context, prop)
    await _check_room_type_limit(session, context, property_id, settings)
    await _check_name_free(session, context, property_id, request.name, None)
    existing = len(await find_room_types(session, context, property_id))
    if existing >= settings.max_room_types * settings.switched_off_allowance:
        raise TooManySwitchedOffError
    room = UnitType(
        tenant_id=context.tenant_id,
        property_id=property_id,
        code=f"rt-{uuid.uuid4().hex[:10]}",
        name=request.name,
        category=request.kind,
        base_occupancy=min(DEFAULT_BASE_OCCUPANCY, request.max_guests),
        max_adults=request.max_guests,
        max_occupancy=request.max_guests,
        sort_order=existing + 1,
        created_by=str(context.user_id),
    )
    session.add(room)
    await session.flush()
    units = _resize(session, room, [], request.units)
    await session.commit()
    log.info("Room type created room_type=%s units=%s", room.id, request.units)
    return _read(room, units)


def _rename_untouched_units(
    session: AsyncSession, units: list[Unit], old_name: str, new_name: str
) -> None:
    """Units still carrying their automatic name follow the room type's new name."""
    for unit in units:
        if unit.name == _default_unit_name(old_name, unit.sort_order):
            unit.name = _default_unit_name(new_name, unit.sort_order)
            session.add(unit)


async def update_room_type(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    room_type_id: UUID,
    request: RoomTypeUpdateRequest,
) -> RoomTypeRead:
    """Change the fields that were sent. Commits."""
    settings = resolve_property_settings(prop.settings)
    property_id = prop.id
    changes = request.model_dump(exclude_unset=True, exclude_none=True)
    if changes.get("units", 0) > settings.max_units_per_room_type:
        raise TooManyUnitsError(settings.max_units_per_room_type)
    await _lock_property(session, context, prop)
    room = await _get(session, context, property_id, room_type_id)
    units = (await _units_of(session, context, [room.id]))[room.id]
    switching_on = changes.get("is_active") is True and not room.is_active
    if switching_on:
        await _check_room_type_limit(session, context, property_id, settings)
    new_name = changes.get("name", room.name)
    if (new_name.lower() != room.name.lower() or switching_on) and changes.get(
        "is_active", room.is_active
    ):
        await _check_name_free(session, context, property_id, new_name, room.id)
    if new_name != room.name:
        _rename_untouched_units(session, units, room.name, new_name)
        room.name = new_name
    if "kind" in changes:
        room.category = changes["kind"]
    if "max_guests" in changes:
        room.max_adults = changes["max_guests"]
        room.max_occupancy = changes["max_guests"]
        room.base_occupancy = min(room.base_occupancy, changes["max_guests"])
    if "is_active" in changes:
        room.is_active = changes["is_active"]
    if "units" in changes:
        units = _resize(session, room, units, changes["units"])
    room.updated_by = str(context.user_id)
    session.add(room)
    await session.commit()
    log.info("Room type updated room_type=%s fields=%s", room.id, sorted(changes))
    return _read(room, units)


async def rename_unit(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    room_type_id: UUID,
    unit_id: UUID,
    name: str,
) -> RoomTypeRead:
    """Give one unit its own name (e.g. a villa's name or a room number). Commits."""
    room = await _get(session, context, property_id, room_type_id)
    units = (await _units_of(session, context, [room.id]))[room.id]
    unit = next((unit for unit in units if unit.id == unit_id and unit.is_active), None)
    if unit is None:
        raise UnitNotFoundError
    unit.name = name
    session.add(unit)
    await session.commit()
    return _read(room, units)
