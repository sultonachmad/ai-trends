"""Cleaning tasks kept in step with the rooms.

Tasks are not made by each front desk action. Instead, the rooms say what is needed, and
`sync_day` brings today's tasks in line every time the board is read:

* a vacant room that is dirty (after a check-out or a room move) needs a departure clean;
* an occupied room whose guest stays tonight, and did not arrive today, needs a stay-over
  clean when the property cleans every day;
* a room whose guest leaves today waits for the check-out;
* a room out of order needs nothing.

Made automatically, a task not yet started is cancelled once the room no longer needs it
(an undone check-out, a guest moved back). Started, finished or requested tasks are never
cancelled. Unfinished tasks of earlier days move to today when the room still needs them,
or when someone started or asked for them; a requested stay-over is dropped once the guest
has left. After taking the property lock, the plan is made again from fresh rows, with
the tasks locked (in id order), so a phone starting a task meanwhile is never overruled.
"""

import datetime as dt
import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Property, Reservation, ReservationUnit, Task, Unit
from app.services import calendar_dates as dates_of
from app.services.bookings import lock_property
from app.services.front_desk_reads import is_on_day
from app.services.stay_status import CONFIRMED, IN_HOUSE
from app.services.unit_status import DIRTY, IN_PROGRESS, OUT_OF_ORDER, VACANT
from app.tenancy.business_settings import resolve_property_settings
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

DEPARTURE, STAYOVER = "departure_clean", "stayover_clean"
AUTO, MANUAL = "auto", "manual"
NOT_STARTED = ("pending", "assigned")
LIVE = ("pending", "assigned", "in_progress", "paused", "failed_inspection")
CANCELLED = "cancelled"
CARRY_DAYS = 14  # unfinished tasks older than this are left alone
MAX_UNITS = 1000


@dataclass(frozen=True)
class Stay:
    line: ReservationUnit
    booking: Reservation


@dataclass(frozen=True)
class Rooms:
    units: list[Unit]
    staying: dict[UUID, Stay]  # in-house guest of each occupied room
    arriving: dict[UUID, Stay]  # confirmed guest arriving today, by assigned room


@dataclass(frozen=True)
class Changes:
    create: list[tuple[Unit, str]]
    cancel: list[Task]
    carry: list[Task]

    @property
    def empty(self) -> bool:
        return not (self.create or self.cancel or self.carry)


async def _stays(
    session: AsyncSession, context: TenantContext, prop: Property, *conditions: object
) -> dict[UUID, Stay]:
    rows = await session.exec(
        select(ReservationUnit, Reservation)
        .join(Reservation, col(Reservation.id) == col(ReservationUnit.reservation_id))
        .where(
            col(ReservationUnit.tenant_id) == context.tenant_id,
            col(Reservation.tenant_id) == context.tenant_id,
            col(Reservation.property_id) == prop.id,
            col(ReservationUnit.unit_id).is_not(None),
            *conditions,
        )
        .order_by(col(Reservation.created_at))
        .execution_options(populate_existing=True)
    )
    found: dict[UUID, Stay] = {}
    for line, booking in rows.all():
        found.setdefault(line.unit_id, Stay(line=line, booking=booking))
    return found


async def read_rooms(
    session: AsyncSession, context: TenantContext, prop: Property, today: dt.date
) -> Rooms:
    units = (
        await session.exec(
            select(Unit)
            .where(
                col(Unit.tenant_id) == context.tenant_id,
                col(Unit.property_id) == prop.id,
                col(Unit.is_active).is_(True),
            )
            .order_by(col(Unit.sort_order), col(Unit.code))
            .limit(MAX_UNITS)
            .execution_options(populate_existing=True)
        )
    ).all()
    staying = await _stays(
        session,
        context,
        prop,
        col(Reservation.status) == IN_HOUSE,  # served by ix_reservation_stay_open
        col(ReservationUnit.status) == IN_HOUSE,
    )
    arriving = await _stays(
        session,
        context,
        prop,
        col(ReservationUnit.status) == CONFIRMED,
        col(Reservation.arrival_date) == today,
    )
    return Rooms(units=list(units), staying=staying, arriving=arriving)


def needed_kind(
    unit: Unit, stay: Stay | None, today: dt.date, timezone: str, stayover: str
) -> str | None:
    """The cleaning the room needs today, if any."""
    if unit.service_status == OUT_OF_ORDER:
        return None
    if unit.fo_status == VACANT:
        return DEPARTURE if unit.hk_status in (DIRTY, IN_PROGRESS) else None
    if stay is None or stay.booking.departure_date <= today:
        return None  # leaving today: cleaned after the check-out
    if is_on_day(stay.line.checked_in_at, timezone, today) or stayover != "daily":
        return None
    return STAYOVER


async def _tasks_since(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    today: dt.date,
    *,
    lock: bool,
) -> list[Task]:
    """Today's tasks, and earlier days' tasks still to do (back to `CARRY_DAYS`)."""
    since = today - dt.timedelta(days=CARRY_DAYS)
    statement = (
        select(Task)
        .where(
            col(Task.tenant_id) == context.tenant_id,
            col(Task.property_id) == prop.id,
            col(Task.unit_id).is_not(None),
            or_(
                col(Task.scheduled_for) == today,
                and_(
                    col(Task.scheduled_for) >= since,
                    col(Task.scheduled_for) < today,
                    col(Task.status).in_(LIVE),
                ),
            ),
            col(Task.status) != CANCELLED,
        )
        .order_by(col(Task.id))  # one lock order for every multi-task writer
        .execution_options(populate_existing=True)  # fresh values after taking a lock
    )
    rows = await session.exec(statement.with_for_update() if lock else statement)
    return list(rows.all())


async def plan_changes(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    today: dt.date,
    *,
    lock: bool = False,
) -> tuple[Rooms, Changes]:
    stayover = resolve_property_settings(prop.settings).hk_stayover
    rooms = await read_rooms(session, context, prop, today)
    tasks = await _tasks_since(session, context, prop, today, lock=lock)
    on_today = [t for t in tasks if t.scheduled_for == today]
    # What already covers a room today: a clean still to do, or today's stay-over in any
    # state (done, or the guest said no). A finished departure clean does not: a room
    # re-let and left again today needs another one.
    todays = {(t.unit_id, t.task_kind) for t in on_today if t.status in LIVE or _is_stayover(t)}
    needed = {
        unit.id: needed_kind(unit, rooms.staying.get(unit.id), today, prop.timezone, stayover)
        for unit in rooms.units
    }
    cancel = [
        t
        for t in on_today
        if t.source == AUTO and t.status in NOT_STARTED and needed.get(t.unit_id) != t.task_kind
    ]
    carry, carried = [], set()
    units = {unit.id: unit for unit in rooms.units}
    for task in sorted((t for t in tasks if t.scheduled_for < today), key=_newest_first):
        if task.status not in LIVE:
            continue
        key = (task.unit_id, task.task_kind)
        free = key not in todays and key not in carried
        if _drop(task, needed.get(task.unit_id), units.get(task.unit_id)):
            cancel.append(task)
        elif free:  # still needed, or started or asked for: it goes on today's list
            carry.append(task)
            carried.add(key)
    create = [
        (unit, needed[unit.id])
        for unit in rooms.units
        if needed[unit.id] is not None
        and (unit.id, needed[unit.id]) not in todays
        and (unit.id, needed[unit.id]) not in carried
    ]
    return rooms, Changes(create=create, cancel=cancel, carry=carry)


def _is_stayover(task: Task) -> bool:
    return task.task_kind == STAYOVER


def _drop(task: Task, needed: str | None, unit: Unit | None) -> bool:
    """An earlier day's task to cancel: made automatically, not started, and not needed
    now; or a stay-over nobody started for a room whose guest has left."""
    if task.status not in NOT_STARTED or needed == task.task_kind:
        return False
    if task.source == AUTO:
        return True
    return task.task_kind == STAYOVER and (unit is None or unit.fo_status == VACANT)


def _newest_first(task: Task) -> tuple:
    return (-task.scheduled_for.toordinal(), str(task.id))


def _new_task(
    context: TenantContext, prop: Property, unit: Unit, kind: str, rooms: Rooms, today: dt.date
) -> Task:
    stay = rooms.staying.get(unit.id) if kind == STAYOVER else None
    return Task(
        tenant_id=context.tenant_id,
        property_id=prop.id,
        task_kind=kind,
        unit_id=unit.id,
        reservation_unit_id=stay.line.id if stay else None,
        scheduled_for=today,
        priority="high" if unit.id in rooms.arriving else "normal",
        status="pending",
        source=AUTO,
        created_by="housekeeping",
        updated_by="housekeeping",
    )


def _apply(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    rooms: Rooms,
    changes: Changes,
    today: dt.date,
) -> None:
    for task in changes.cancel:
        task.status, task.updated_by = CANCELLED, "housekeeping"
        session.add(task)
    for task in changes.carry:
        task.scheduled_for, task.updated_by = today, "housekeeping"
        task.priority = "high" if task.unit_id in rooms.arriving else task.priority
        session.add(task)
    for unit, kind in changes.create:
        session.add(_new_task(context, prop, unit, kind, rooms, today))


async def sync_day(session: AsyncSession, context: TenantContext, prop: Property) -> None:
    """Bring today's tasks in line with the rooms. Commits only when something changed."""
    today = dates_of.property_today(prop.timezone)
    _, changes = await plan_changes(session, context, prop, today)
    if changes.empty:
        return
    # Serialise with the front desk (and other phones) before changing anything, then
    # look again: what was needed a moment ago may have changed or been done.
    await lock_property(session, context, prop.id)
    rooms, changes = await plan_changes(session, context, prop, today, lock=True)
    if changes.empty:
        await session.commit()
        return
    _apply(session, context, prop, rooms, changes, today)
    try:
        await session.commit()
    except IntegrityError:  # a guest request added the same clean meanwhile; next read fixes it
        await session.rollback()
        log.warning("Housekeeping sync lost a race property=%s", prop.id)
        return
    log.info(
        "Housekeeping tasks synced property=%s created=%s cancelled=%s carried=%s",
        prop.id,
        len(changes.create),
        len(changes.cancel),
        len(changes.carry),
    )
