"""Units sold per room type per night — the one place that number changes.

A booking takes units for each of its nights and gives them back when it is cancelled
or moved. Callers run these inside the transaction that saves the booking, after
locking the property row, so the count and the booking can never disagree.

`inventoryday` has a row only for nights that have ever had something sold. Availability
is always "units in use minus units sold"; a negative result means the night is oversold.
"""

import datetime as dt
from uuid import UUID

from sqlalchemy import func, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import InventoryDay, Unit
from app.tenancy.context import TenantContext

_NIGHT_KEY = ["tenant_id", "unit_type_id", "stay_date"]


async def units_in_use(
    session: AsyncSession, context: TenantContext, room_type_ids: list[UUID]
) -> dict[UUID, int]:
    """Units in use and for sale, per room type — what "sold" is measured against."""
    if not room_type_ids:
        return {}
    rows = await session.exec(
        select(col(Unit.unit_type_id), func.count())
        .where(
            col(Unit.tenant_id) == context.tenant_id,
            col(Unit.unit_type_id).in_(room_type_ids),
            col(Unit.is_active).is_(True),
            col(Unit.is_sellable).is_(True),
        )
        .group_by(col(Unit.unit_type_id))
    )
    return {room_type_id: int(count) for room_type_id, count in rows.all()}


async def take_units(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    room_type_id: UUID,
    nights: list[dt.date],
    count: int,
    units_in_use: int,
) -> dict[dt.date, int]:
    """Sell `count` units on each night. Returns units sold per night after the change."""
    if not nights or count <= 0:
        return {}
    rows = [
        {
            "tenant_id": context.tenant_id,
            "property_id": property_id,
            "unit_type_id": room_type_id,
            "stay_date": night,
            "physical": units_in_use,
            "sold": count,
        }
        for night in sorted(nights)  # one order for everyone: no two bookings can deadlock
    ]
    statement = pg_insert(InventoryDay).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=_NIGHT_KEY,
        set_={
            "sold": InventoryDay.sold + statement.excluded.sold,
            "physical": statement.excluded.physical,
            "version": InventoryDay.version + 1,
        },
    ).returning(col(InventoryDay.stay_date), col(InventoryDay.sold))
    result = await session.exec(statement)
    return {night: int(sold) for night, sold in result.all()}


async def release_units(
    session: AsyncSession,
    context: TenantContext,
    room_type_id: UUID,
    nights: list[dt.date],
    count: int,
) -> None:
    """Give `count` units back on each night (never below zero)."""
    if not nights or count <= 0:
        return
    await session.exec(
        update(InventoryDay)
        .where(
            col(InventoryDay.tenant_id) == context.tenant_id,
            col(InventoryDay.unit_type_id) == room_type_id,
            col(InventoryDay.stay_date).in_(nights),
        )
        .values(sold=func.greatest(InventoryDay.sold - count, 0), version=InventoryDay.version + 1)
    )


async def sold_by_night(
    session: AsyncSession,
    context: TenantContext,
    room_type_ids: list[UUID],
    start: dt.date,
    end: dt.date,
) -> dict[tuple[UUID, dt.date], int]:
    """Units sold for the nights from `start` to `end` inclusive that have any."""
    if not room_type_ids:
        return {}
    rows = await session.exec(
        select(
            col(InventoryDay.unit_type_id), col(InventoryDay.stay_date), col(InventoryDay.sold)
        ).where(
            col(InventoryDay.tenant_id) == context.tenant_id,
            col(InventoryDay.unit_type_id).in_(room_type_ids),
            col(InventoryDay.stay_date) >= start,
            col(InventoryDay.stay_date) <= end,
            col(InventoryDay.sold) > 0,
        )
    )
    return {(room_type_id, night): int(sold) for room_type_id, night, sold in rows.all()}


async def sync_units_in_use(
    session: AsyncSession,
    context: TenantContext,
    room_type_id: UUID,
    units_in_use: int,
    from_date: dt.date,
) -> list[dt.date]:
    """Record a room type's new unit count on its future nights; returns nights now oversold."""
    result = await session.exec(
        update(InventoryDay)
        .where(
            col(InventoryDay.tenant_id) == context.tenant_id,
            col(InventoryDay.unit_type_id) == room_type_id,
            col(InventoryDay.stay_date) >= from_date,
        )
        .values(physical=units_in_use)
        .returning(col(InventoryDay.stay_date), col(InventoryDay.sold))
    )
    return sorted(night for night, sold in result.all() if sold > units_in_use)
