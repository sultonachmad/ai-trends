"""Taking a room off sale for a repair, and putting it back.

Off sale means: an active `unitblock` for the nights, one unit of the room type blocked
in the inventory on each of them (so channels and the booking page sell one fewer), the
channels told, and the room out of order while a blocked night has begun. Refused when a
guest is in or booked into that room on those nights, or when there would not be enough
rooms left for the guests already booked.

Back on sale (fixed, cancelled, by hand, or once the last night has passed) gives back
the nights from today on (tonight included: the room can be sold again at once) and
leaves the room needing a clean.

Locks: the property first (like every booking change), then the request, then the room.
"""

import datetime as dt
import logging
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Property, Reservation, ReservationUnit, Unit, UnitBlock, WorkOrder
from app.services import calendar_dates as dates_of
from app.services import channel_queue, inventory, tenant_audit
from app.services import maintenance_errors as errors
from app.services.bookings import lock_property
from app.services.maintenance import LIVE, locked_request
from app.services.room_blocks import ACTIVE, night_window, nights_of
from app.services.stay_status import HOLDS_ROOM
from app.services.unit_status import DIRTY, IN_SERVICE, OUT_OF_ORDER, set_unit_status
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

MAX_NIGHTS = 90
RELEASED = "released"
KIND = "out_of_order"


def _nights(first: dt.date, last: dt.date) -> list[dt.date]:
    return [first + dt.timedelta(days=i) for i in range((last - first).days + 1)]


async def _locked_unit(session: AsyncSession, context: TenantContext, unit_id: UUID) -> Unit:
    return (
        await session.exec(
            select(Unit)
            .where(col(Unit.tenant_id) == context.tenant_id, col(Unit.id) == unit_id)
            .with_for_update()
        )
    ).one()


async def active_block(
    session: AsyncSession, context: TenantContext, order_id: UUID
) -> UnitBlock | None:
    return (
        await session.exec(
            select(UnitBlock)
            .where(
                col(UnitBlock.tenant_id) == context.tenant_id,
                col(UnitBlock.work_order_id) == order_id,
                col(UnitBlock.status) == ACTIVE,
            )
            .with_for_update()
        )
    ).first()


async def has_block(session: AsyncSession, context: TenantContext, order_id: UUID) -> bool:
    return await active_block(session, context, order_id) is not None


async def _other_block(
    session: AsyncSession,
    context: TenantContext,
    unit_id: UUID,
    start: dt.datetime,
    end: dt.datetime,
) -> str | None:
    """The request number of another block on this room in this time, if any."""
    found = await session.exec(
        select(col(WorkOrder.number))
        .join(UnitBlock, col(UnitBlock.work_order_id) == col(WorkOrder.id))
        .where(
            col(UnitBlock.tenant_id) == context.tenant_id,
            col(WorkOrder.tenant_id) == context.tenant_id,
            col(UnitBlock.unit_id) == unit_id,
            col(UnitBlock.status) == ACTIVE,
            col(UnitBlock.start_at) < end,
            col(UnitBlock.end_at) > start,
        )
    )
    return found.first()


async def _booked_in(
    session: AsyncSession,
    context: TenantContext,
    unit_id: UUID,
    start: dt.datetime,
    end: dt.datetime,
) -> list[str]:
    """Booking numbers of guests in, or booked into, this room in this time."""
    rows = await session.exec(
        select(col(Reservation.confirmation_no))
        .join(ReservationUnit, col(ReservationUnit.reservation_id) == col(Reservation.id))
        .where(
            col(ReservationUnit.tenant_id) == context.tenant_id,
            col(Reservation.tenant_id) == context.tenant_id,
            col(ReservationUnit.unit_id) == unit_id,
            col(ReservationUnit.status).in_(HOLDS_ROOM),
            col(ReservationUnit.start_at) < end,
            col(ReservationUnit.blocked_until) > start,
        )
        .distinct()
    )
    return sorted(rows.all())


async def _short_nights(
    session: AsyncSession, context: TenantContext, room_type_id: UUID, nights: list[dt.date]
) -> tuple[list[str], int]:
    """Nights where one more room off sale would leave too few; and the rooms in use."""
    in_use = (await inventory.units_in_use(session, context, [room_type_id])).get(room_type_id, 0)
    taken = await inventory.taken_by_night(session, context, [room_type_id], nights[0], nights[-1])
    short = [n.isoformat() for n in nights if in_use - taken.get((room_type_id, n), 0) < 1]
    return short, in_use


async def _release(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    block: UnitBlock,
    unit: Unit,
    *,
    back_in_service: bool = True,
) -> None:
    """Give back the nights from today on; the room is back in service and needs a clean
    (unless the block is only being replaced by other nights)."""
    today = dates_of.property_today(prop.timezone)
    first, last = nights_of(block, prop.timezone)
    remaining = _nights(max(first, today), last) if last >= today else []
    if remaining:
        await inventory.unblock_units(session, context, unit.unit_type_id, remaining)
        await channel_queue.enqueue(session, context, prop.id, [unit.unit_type_id], remaining)
    block.status, block.updated_by = RELEASED, str(context.user_id)
    session.add(block)
    if back_in_service:  # someone worked in the room: it needs a clean before a guest
        set_unit_status(session, context, unit, service=IN_SERVICE, hk=DIRTY)


async def release_for(
    session: AsyncSession, context: TenantContext, prop: Property, order: WorkOrder
) -> None:
    """Back on sale when the request is fixed or cancelled. The caller holds the locks."""
    block = await active_block(session, context, order.id)
    if block is not None:
        await _release(
            session, context, prop, block, await _locked_unit(session, context, block.unit_id)
        )


def _check_nights(first: dt.date, last: dt.date, today: dt.date) -> None:
    if first < today or last < first or (last - first).days >= MAX_NIGHTS:
        raise errors.BadNightsError


async def _block(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    order: WorkOrder,
    unit: Unit,
    nights: list[dt.date],
) -> None:
    start, end = night_window(nights[0], nights[-1], prop.timezone)
    other = await _other_block(session, context, unit.id, start, end)
    if other is not None:
        raise errors.AlreadyOffSaleError([other])
    booked = await _booked_in(session, context, unit.id, start, end)
    if booked:
        raise errors.RoomBookedError(booked)
    short, in_use = await _short_nights(session, context, unit.unit_type_id, nights)
    if short:
        raise errors.WouldOversellError(short)
    session.add(
        UnitBlock(
            tenant_id=context.tenant_id,
            unit_id=unit.id,
            kind=KIND,
            start_at=start,
            end_at=end,
            reason_text=order.number,
            work_order_id=order.id,
            status=ACTIVE,
            created_by=str(context.user_id),
            updated_by=str(context.user_id),
        )
    )
    await inventory.block_units(session, context, prop.id, unit.unit_type_id, nights, in_use)
    await channel_queue.enqueue(session, context, prop.id, [unit.unit_type_id], nights)
    if start <= dt.datetime.now(dt.UTC):  # as refresh_blocks: once the first night began
        set_unit_status(session, context, unit, service=OUT_OF_ORDER)


async def off_sale(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    order_id: UUID,
    first: dt.date,
    last: dt.date,
) -> WorkOrder:
    """Take the request's room off sale for these nights (replacing any earlier choice)."""
    _check_nights(first, last, dates_of.property_today(prop.timezone))
    await lock_property(session, context, prop.id)
    order = await locked_request(session, context, prop, order_id)
    if order.status not in LIVE:
        raise errors.RequestClosedError
    if order.unit_id is None:
        raise errors.NoRoomError
    current = await active_block(session, context, order.id)
    unit = await _locked_unit(session, context, order.unit_id)
    if current is not None:
        await _release(session, context, prop, current, unit, back_in_service=False)
        await session.flush()  # the old block must be inactive before the new one exists
    await _block(session, context, prop, order, unit, _nights(first, last))
    await _audit(session, context, order, "room.off_sale", {"first": str(first), "last": str(last)})
    await session.commit()
    await session.refresh(order)
    log.info("Room off sale order=%s unit=%s %s..%s", order.id, unit.id, first, last)
    return order


async def on_sale(
    session: AsyncSession, context: TenantContext, prop: Property, order_id: UUID
) -> WorkOrder:
    await lock_property(session, context, prop.id)
    order = await locked_request(session, context, prop, order_id)
    block = await active_block(session, context, order.id)
    if block is None:
        raise errors.NotOffSaleError
    await _release(
        session, context, prop, block, await _locked_unit(session, context, block.unit_id)
    )
    await _audit(session, context, order, "room.on_sale", {})
    await session.commit()
    await session.refresh(order)
    return order


async def _blocks_of_property(
    session: AsyncSession, context: TenantContext, prop: Property, *, lock: bool
) -> list[tuple[UnitBlock, Unit]]:
    statement = (
        select(UnitBlock, Unit)
        .join(Unit, col(Unit.id) == col(UnitBlock.unit_id))
        .where(
            col(UnitBlock.tenant_id) == context.tenant_id,
            col(Unit.tenant_id) == context.tenant_id,
            col(Unit.property_id) == prop.id,
            col(UnitBlock.status) == ACTIVE,
        )
        .order_by(col(Unit.id))
        .execution_options(populate_existing=True)
    )
    rows = await session.exec(statement.with_for_update() if lock else statement)
    return list(rows.all())


def _due(block: UnitBlock, unit: Unit, now: dt.datetime) -> str | None:
    if block.end_at <= now:
        return "end"
    if block.start_at <= now and unit.service_status != OUT_OF_ORDER:
        return "start"
    return None


async def refresh_blocks(session: AsyncSession, context: TenantContext, prop: Property) -> None:
    """Rooms go out of order when their first blocked night begins, and come back when the
    last has passed. Run when boards are read; commits only when something changed."""
    now = dt.datetime.now(dt.UTC)
    if not any(
        _due(b, u, now) for b, u in await _blocks_of_property(session, context, prop, lock=False)
    ):
        return
    await lock_property(session, context, prop.id)
    for block, unit in await _blocks_of_property(session, context, prop, lock=True):
        due = _due(block, unit, now)
        if due == "end":
            await _release(session, context, prop, block, unit)
        elif due == "start":
            set_unit_status(session, context, unit, service=OUT_OF_ORDER)
    await session.commit()


async def _audit(
    session: AsyncSession, context: TenantContext, order: WorkOrder, event: str, payload: dict
) -> None:
    await tenant_audit.record(
        session,
        context,
        event,
        property_id=order.property_id,
        entity_table="workorder",
        entity_id=order.id,
        payload=payload,
    )
