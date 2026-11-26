"""The rooms board: today's cleaning tasks in the order to do them, and every room.

Order on the phone: rooms with a guest arriving today, then rooms left by departing
guests, then stay-overs, then the rest; finished tasks last.
"""

import datetime as dt
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Guest, Property, StaffMember, Task, Unit, UnitType
from app.schemas.housekeeping import HkBoard, HkGuest, HkProblem, HkRoom, HkStaff, HkTask
from app.services import calendar_dates as dates_of
from app.services.booking_reads import _by_id
from app.services.housekeeping_tasks import DEPARTURE, LIVE, STAYOVER, Rooms, Stay, read_rooms
from app.services.room_assignment import room_name
from app.tenancy.business_settings import resolve_property_settings
from app.tenancy.context import TenantContext

KIND_ORDER = {DEPARTURE: 1, STAYOVER: 2}
PROBLEM_DAYS = 2  # problems older than this are no longer shown at the desk
MAX_PROBLEMS = 100


async def _tasks_today(
    session: AsyncSession, context: TenantContext, prop: Property, today: dt.date
) -> list[Task]:
    rows = await session.exec(
        select(Task).where(
            col(Task.tenant_id) == context.tenant_id,
            col(Task.property_id) == prop.id,
            col(Task.scheduled_for) == today,
            col(Task.unit_id).is_not(None),
            col(Task.status) != "cancelled",
        )
    )
    return list(rows.all())


async def active_staff(session: AsyncSession, context: TenantContext) -> list[StaffMember]:
    rows = await session.exec(
        select(StaffMember)
        .where(
            col(StaffMember.tenant_id) == context.tenant_id,
            col(StaffMember.status) == "active",
            col(StaffMember.user_id).is_not(None),
        )
        .order_by(col(StaffMember.display_name))
    )
    return list(rows.all())


def _guest(stay: Stay | None, guests: dict[UUID, Guest]) -> HkGuest | None:
    if stay is None:
        return None
    booking = stay.booking
    guest = guests.get(booking.booker_guest_id) if booking.booker_guest_id else None
    return HkGuest(
        name=guest.full_name if guest else "",
        adults=stay.line.adults,
        children=stay.line.children,
        arrival=booking.arrival_date,
        departure=booking.departure_date,
        eta=booking.eta,
        special_requests=booking.special_requests,
    )


def _order(task: Task, rooms: Rooms, units: dict[UUID, Unit]) -> tuple:
    unit = units[task.unit_id]
    return (
        task.status not in LIVE,
        task.unit_id not in rooms.arriving,
        KIND_ORDER.get(task.task_kind, 3),
        unit.sort_order,
        unit.code,
    )


def _private(guest: HkGuest | None) -> HkGuest | None:
    if guest is None:
        return None
    return guest.model_copy(update={"name": "", "special_requests": None})


def _task_read(
    task: Task,
    unit: Unit,
    type_name: str,
    rooms: Rooms,
    names: dict[UUID, str],
    guests: dict[UUID, Guest],
    me: UUID | None,
    inspecting: bool,
    full_guests: bool,
) -> HkTask:
    shown = full_guests or task.assigned_staff_id is None or task.assigned_staff_id == me
    arriving = _guest(rooms.arriving.get(unit.id), guests)
    staying = _guest(rooms.staying.get(unit.id), guests)
    return HkTask(
        id=task.id,
        unit_id=unit.id,
        room_name=room_name(unit),
        room_type=type_name,
        kind=task.task_kind,
        status=task.status,
        priority=task.priority,
        assigned_staff_id=task.assigned_staff_id,
        assigned_name=names.get(task.assigned_staff_id) if task.assigned_staff_id else None,
        mine=me is not None and task.assigned_staff_id == me,
        arriving=arriving if shown else _private(arriving),
        staying=staying if shown else _private(staying),
        started_at=task.started_at,
        completed_at=task.completed_at,
        awaiting_inspection=task.status == "done" and inspecting,
        inspection_result=task.inspection_result,
        notes=task.notes,
        problem_kind=task.problem_kind if task.problem_cleared_at is None else None,
        problem_note=task.problem_note if task.problem_cleared_at is None else None,
        problem_at=task.problem_at if task.problem_cleared_at is None else None,
    )


def _room_read(
    unit: Unit, type_name: str, rooms: Rooms, task: Task | None, names: dict[UUID, str]
) -> HkRoom:
    return HkRoom(
        id=unit.id,
        name=room_name(unit),
        room_type=type_name,
        hk_status=unit.hk_status,
        fo_status=unit.fo_status,
        service_status=unit.service_status,
        arrival_today=unit.id in rooms.arriving,
        task_id=task.id if task else None,
        task_status=task.status if task else None,
        assigned_name=names.get(task.assigned_staff_id)
        if task and task.assigned_staff_id
        else None,
    )


async def _guests(session: AsyncSession, context: TenantContext, rooms: Rooms) -> dict:
    ids = {
        stay.booking.booker_guest_id
        for stay in (*rooms.staying.values(), *rooms.arriving.values())
        if stay.booking.booker_guest_id
    }
    return await _by_id(session, context, Guest, ids)


async def _my_mode(session: AsyncSession, context: TenantContext, staff: list) -> bool:
    mine = next((s for s in staff if s.id == context.staff_member_id), None)
    return mine is not None and mine.ui_mode == "guided"


async def read_board(
    session: AsyncSession, context: TenantContext, prop: Property, *, full_guests: bool = False
) -> HkBoard:
    """`full_guests`: the guest's name and requests on every room (supervisors, front
    desk); otherwise only on the person's own rooms and rooms nobody has taken."""
    today = dates_of.property_today(prop.timezone)
    rooms = await read_rooms(session, context, prop, today)
    units = {unit.id: unit for unit in rooms.units}
    tasks = [t for t in await _tasks_today(session, context, prop, today) if t.unit_id in units]
    tasks.sort(key=lambda task: _order(task, rooms, units))
    types = await _by_id(session, context, UnitType, {u.unit_type_id for u in rooms.units})
    staff = await active_staff(session, context)
    names = {member.id: member.display_name for member in staff}
    guests = await _guests(session, context, rooms)
    settings = resolve_property_settings(prop.settings)
    by_unit: dict[UUID, Task] = {}
    for task in tasks:  # live first, so a room shows what is still to do
        by_unit.setdefault(task.unit_id, task)
    me = context.staff_member_id
    return HkBoard(
        date=today,
        tasks=[
            _task_read(
                t,
                units[t.unit_id],
                types[units[t.unit_id].unit_type_id].name,
                rooms,
                names,
                guests,
                me,
                settings.hk_ready_when == "inspected",
                full_guests,
            )
            for t in tasks
        ],
        rooms=[
            _room_read(u, types[u.unit_type_id].name, rooms, by_unit.get(u.id), names)
            for u in rooms.units
        ],
        staff=[HkStaff(id=member.id, name=member.display_name) for member in staff],
        my_staff_id=me,
        big_buttons=await _my_mode(session, context, staff),
        ready_when=settings.hk_ready_when,
        stayover=settings.hk_stayover,
        poll_seconds=settings.hk_poll_seconds,
    )


async def open_problems(
    session: AsyncSession, context: TenantContext, prop: Property
) -> list[HkProblem]:
    """Problems housekeepers reported that the front desk has not dealt with yet."""
    since = dates_of.property_today(prop.timezone) - dt.timedelta(days=PROBLEM_DAYS)
    rows = (
        await session.exec(
            select(Task, Unit)
            .join(Unit, col(Unit.id) == col(Task.unit_id))
            .where(
                col(Task.tenant_id) == context.tenant_id,
                col(Unit.tenant_id) == context.tenant_id,
                col(Task.property_id) == prop.id,
                col(Task.problem_kind).is_not(None),
                col(Task.problem_cleared_at).is_(None),
                col(Task.scheduled_for) >= since,
            )
            .order_by(col(Task.problem_at).desc())
            .limit(MAX_PROBLEMS)
        )
    ).all()
    reporters = {task.problem_by for task, _ in rows if task.problem_by}
    names = await _names_by_user(session, context, reporters)
    return [
        HkProblem(
            task_id=task.id,
            unit_id=unit.id,
            room_name=room_name(unit),
            kind=task.problem_kind,
            note=task.problem_note,
            at=task.problem_at,
            by_name=names.get(task.problem_by) if task.problem_by else None,
        )
        for task, unit in rows
    ]


async def _names_by_user(
    session: AsyncSession, context: TenantContext, user_ids: set[str]
) -> dict[str, str]:
    numbers = {int(u) for u in user_ids if u.isdigit()}
    if not numbers:
        return {}
    rows = await session.exec(
        select(StaffMember.user_id, StaffMember.display_name).where(
            col(StaffMember.tenant_id) == context.tenant_id, col(StaffMember.user_id).in_(numbers)
        )
    )
    return {str(user_id): name for user_id, name in rows.all()}
