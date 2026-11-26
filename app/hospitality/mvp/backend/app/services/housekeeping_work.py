"""What housekeepers and supervisors do with a task, and the room status that follows.

Every room status change goes through `set_unit_status`, with the device it came from
(`mobile` or `staff`) and the task, so the room's history shows who cleaned it and how.
Locks: the task row, then its room.
"""

import datetime as dt
import logging
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Property, StaffMember, Task, Unit
from app.schemas.housekeeping import InspectRequest, ProblemRequest
from app.services import calendar_dates as dates_of
from app.services import housekeeping_errors as errors
from app.services.bookings import lock_property
from app.services.housekeeping_tasks import LIVE, MANUAL, STAYOVER
from app.services.unit_status import (
    CLEAN,
    DIRTY,
    IN_PROGRESS,
    INSPECTED,
    OCCUPIED,
    set_unit_status,
)
from app.tenancy.business_settings import with_property_overrides
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

STARTABLE = ("pending", "assigned", "paused", "failed_inspection")
WORKING = (*STARTABLE, "in_progress")
GUEST_SAID_NO = {"dnd": "skipped_dnd", "refused": "refused"}


def my_staff_id(context: TenantContext) -> UUID:
    if context.staff_member_id is None:
        raise errors.NoStaffProfileError
    return context.staff_member_id


async def locked_task(
    session: AsyncSession, context: TenantContext, prop: Property, task_id: UUID
) -> Task:
    task = (
        await session.exec(
            select(Task)
            .where(
                col(Task.tenant_id) == context.tenant_id,
                col(Task.property_id) == prop.id,
                col(Task.id) == task_id,
            )
            .with_for_update()
        )
    ).first()
    if task is None or task.unit_id is None:
        raise errors.TaskNotFoundError
    return task


async def locked_unit(
    session: AsyncSession, context: TenantContext, prop: Property, unit_id: UUID
) -> Unit:
    unit = (
        await session.exec(
            select(Unit)
            .where(
                col(Unit.tenant_id) == context.tenant_id,
                col(Unit.property_id) == prop.id,
                col(Unit.id) == unit_id,
            )
            .with_for_update()
        )
    ).first()
    if unit is None:
        raise errors.RoomNotFoundError
    return unit


def _claim(task: Task, staff_id: UUID, can_manage: bool) -> None:
    """Work on the task as `staff_id`: theirs, or free (they take it), or a supervisor."""
    if task.status not in WORKING:
        raise errors.TaskClosedError
    if task.assigned_staff_id is None:
        task.assigned_staff_id = staff_id
    elif task.assigned_staff_id != staff_id and not can_manage:
        raise errors.NotYourTaskError


async def _done(session: AsyncSession, task: Task, who: str) -> Task:
    task.updated_by = who
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def start(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    task_id: UUID,
    *,
    can_manage: bool,
    source: str,
) -> Task:
    task = await locked_task(session, context, prop, task_id)
    _claim(task, my_staff_id(context), can_manage)
    if task.status not in STARTABLE:
        raise errors.TaskClosedError
    unit = await locked_unit(session, context, prop, task.unit_id)
    task.status = "in_progress"
    task.started_at = task.started_at or dt.datetime.now(dt.UTC)
    set_unit_status(session, context, unit, hk=IN_PROGRESS, source=source, task_id=task.id)
    return await _done(session, task, str(context.user_id))


async def finish(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    task_id: UUID,
    *,
    can_manage: bool,
    source: str,
) -> Task:
    """Cleaned: the room is clean (and waits for inspection when the property asks)."""
    task = await locked_task(session, context, prop, task_id)
    _claim(task, my_staff_id(context), can_manage)
    unit = await locked_unit(session, context, prop, task.unit_id)
    now = dt.datetime.now(dt.UTC)
    task.status, task.completed_at = "done", now
    task.started_at = task.started_at or now
    task.inspection_result = None
    set_unit_status(session, context, unit, hk=CLEAN, source=source, task_id=task.id)
    return await _done(session, task, str(context.user_id))


async def report_problem(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    task_id: UUID,
    request: ProblemRequest,
    *,
    can_manage: bool,
) -> Task:
    """Something stops the cleaning. Do not disturb and refused end it for today."""
    task = await locked_task(session, context, prop, task_id)
    _claim(task, my_staff_id(context), can_manage)
    if request.kind in GUEST_SAID_NO:
        unit = await locked_unit(session, context, prop, task.unit_id)
        if unit.fo_status != OCCUPIED:
            raise errors.NotOccupiedError
        task.status = GUEST_SAID_NO[request.kind]
    elif task.status == "in_progress":
        task.status = "paused"
    task.problem_kind, task.problem_note = request.kind, request.note
    task.problem_at, task.problem_by = dt.datetime.now(dt.UTC), str(context.user_id)
    task.problem_cleared_at = task.problem_cleared_by = None
    log.info("Housekeeping problem task=%s kind=%s", task.id, request.kind)
    return await _done(session, task, str(context.user_id))


async def clear_problem(
    session: AsyncSession, context: TenantContext, prop: Property, task_id: UUID
) -> Task:
    """The front desk has dealt with the problem."""
    task = await locked_task(session, context, prop, task_id)
    if task.problem_kind is not None and task.problem_cleared_at is None:
        task.problem_cleared_at = dt.datetime.now(dt.UTC)
        task.problem_cleared_by = str(context.user_id)
    return await _done(session, task, str(context.user_id))


async def take(
    session: AsyncSession, context: TenantContext, prop: Property, task_id: UUID
) -> Task:
    task = await locked_task(session, context, prop, task_id)
    if task.status not in WORKING:
        raise errors.TaskClosedError
    staff_id = my_staff_id(context)
    if task.assigned_staff_id not in (None, staff_id):
        raise errors.NotYourTaskError
    task.assigned_staff_id = staff_id
    task.status = "assigned" if task.status == "pending" else task.status
    return await _done(session, task, str(context.user_id))


async def active_staff_ids(
    session: AsyncSession, context: TenantContext, ids: set[UUID]
) -> set[UUID]:
    rows = await session.exec(
        select(StaffMember.id).where(
            col(StaffMember.tenant_id) == context.tenant_id,
            col(StaffMember.id).in_(ids),
            col(StaffMember.status) == "active",
            col(StaffMember.user_id).is_not(None),
        )
    )
    return set(rows.all())


async def _units_of(session: AsyncSession, context: TenantContext, ids: set) -> list[Unit]:
    if not ids:
        return []
    rows = await session.exec(
        select(Unit).where(col(Unit.tenant_id) == context.tenant_id, col(Unit.id).in_(ids))
    )
    return list(rows.all())


def _give(task: Task, staff_id: UUID | None) -> None:
    task.assigned_staff_id = staff_id
    if task.status in ("pending", "assigned"):
        task.status = "assigned" if staff_id else "pending"


async def assign(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    task_id: UUID,
    staff_id: UUID | None,
) -> Task:
    task = await locked_task(session, context, prop, task_id)
    if task.status not in WORKING:
        raise errors.TaskClosedError
    if staff_id is not None and staff_id not in await active_staff_ids(
        session, context, {staff_id}
    ):
        raise errors.UnknownStaffError
    _give(task, staff_id)
    return await _done(session, task, str(context.user_id))


async def split_evenly(
    session: AsyncSession, context: TenantContext, prop: Property, staff_ids: list[UUID]
) -> int:
    """Share today's rooms nobody has yet among `staff_ids`, in board order. Commits."""
    wanted = list(dict.fromkeys(staff_ids))
    if set(wanted) - await active_staff_ids(session, context, set(wanted)):
        raise errors.UnknownStaffError
    today = dates_of.property_today(prop.timezone)
    free = (
        await session.exec(
            select(Task)
            .join(Unit, col(Unit.id) == col(Task.unit_id))
            .where(
                col(Task.tenant_id) == context.tenant_id,
                col(Unit.tenant_id) == context.tenant_id,
                col(Task.property_id) == prop.id,
                col(Task.scheduled_for) == today,
                col(Task.status) == "pending",
                col(Task.assigned_staff_id).is_(None),
            )
            .order_by(col(Task.id))  # one lock order for every multi-task writer
            .with_for_update(of=Task)
        )
    ).all()
    units = {u.id: u for u in await _units_of(session, context, {t.unit_id for t in free})}
    ordered = sorted(
        free,
        key=lambda task: (  # arrivals first, then the board's room order
            task.priority != "high",
            units[task.unit_id].sort_order,
            units[task.unit_id].code,
        ),
    )
    for index, task in enumerate(ordered):
        _give(task, wanted[index % len(wanted)])
        task.updated_by = str(context.user_id)
        session.add(task)
    await session.commit()
    return len(ordered)


async def inspect(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    task_id: UUID,
    request: InspectRequest,
    *,
    source: str,
) -> Task:
    """A supervisor passes the room, or sends it back to be cleaned again."""
    task = await locked_task(session, context, prop, task_id)
    if task.status != "done":
        raise errors.NotDoneYetError
    if not request.passed and not request.reason:
        raise errors.ReasonNeededError
    unit = await locked_unit(session, context, prop, task.unit_id)
    task.inspected_by_staff_id = context.staff_member_id
    if request.passed:
        task.status, task.inspection_result = "inspected", "pass"
        set_unit_status(session, context, unit, hk=INSPECTED, source=source, task_id=task.id)
    else:
        task.status, task.inspection_result = "failed_inspection", "fail"
        task.notes = request.reason
        set_unit_status(session, context, unit, hk=DIRTY, source=source, task_id=task.id)
    return await _done(session, task, str(context.user_id))


async def _live_today(
    session: AsyncSession, context: TenantContext, prop: Property, unit_id: UUID
) -> list[Task]:
    today = dates_of.property_today(prop.timezone)
    rows = await session.exec(
        select(Task)
        .where(
            col(Task.tenant_id) == context.tenant_id,
            col(Task.property_id) == prop.id,
            col(Task.unit_id) == unit_id,
            col(Task.scheduled_for) == today,
            col(Task.status).in_(LIVE),
        )
        .order_by(col(Task.id))
        .with_for_update()
    )
    return list(rows.all())


async def set_room_status(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    unit_id: UUID,
    hk_status: str,
    *,
    can_manage: bool,
    source: str,
) -> None:
    """Change a room's status by hand. Marking it clean finishes today's open tasks.

    Only a supervisor may mark a room inspected. Locks the tasks first, then the room,
    like start and done, so the two never wait on each other.
    """
    if hk_status == INSPECTED and not can_manage:
        raise errors.InspectPermissionError
    tasks = await _live_today(session, context, prop, unit_id) if hk_status != DIRTY else []
    unit = await locked_unit(session, context, prop, unit_id)
    now = dt.datetime.now(dt.UTC)
    for task in tasks:
        task.status = "inspected" if hk_status == INSPECTED else "done"
        task.completed_at, task.started_at = now, task.started_at or now
        task.notes = task.notes or "Marked by hand"
        task.updated_by = str(context.user_id)
        session.add(task)
    set_unit_status(session, context, unit, hk=hk_status, source=source)
    await session.commit()


async def request_clean(
    session: AsyncSession, context: TenantContext, prop: Property, unit_id: UUID
) -> Task:
    """Clean an occupied room today, on the guest's request.

    Takes the property lock first, like the daily task sync, so the two cannot both add
    the same stay-over."""
    await lock_property(session, context, prop.id)
    unit = await locked_unit(session, context, prop, unit_id)
    if unit.fo_status != OCCUPIED:
        raise errors.NotOccupiedError
    today = dates_of.property_today(prop.timezone)
    existing = (
        await session.exec(
            select(Task.id).where(
                col(Task.tenant_id) == context.tenant_id,
                col(Task.unit_id) == unit_id,
                col(Task.scheduled_for) == today,
                col(Task.task_kind) == STAYOVER,
                col(Task.status) != "cancelled",
            )
        )
    ).first()
    if existing is not None:
        raise errors.TaskExistsError
    task = Task(
        tenant_id=context.tenant_id,
        property_id=prop.id,
        task_kind=STAYOVER,
        unit_id=unit.id,
        scheduled_for=today,
        priority="normal",
        status="pending",
        source=MANUAL,
        created_by=str(context.user_id),
    )
    try:
        return await _done(session, task, str(context.user_id))
    except IntegrityError:  # the database's own guard: one live stay-over a day
        await session.rollback()
        raise errors.TaskExistsError from None


async def set_big_buttons(session: AsyncSession, context: TenantContext, on: bool) -> bool:
    staff = (
        await session.exec(
            select(StaffMember)
            .where(
                col(StaffMember.tenant_id) == context.tenant_id,
                col(StaffMember.id) == my_staff_id(context),
            )
            .with_for_update()
        )
    ).first()
    if staff is None:
        raise errors.NoStaffProfileError
    staff.ui_mode = "guided" if on else "classic"
    session.add(staff)
    await session.commit()
    return on


async def save_settings(
    session: AsyncSession, prop: Property, ready_when: str, stayover: str
) -> None:
    prop.settings = with_property_overrides(
        prop.settings, {"hk_ready_when": ready_when, "hk_stayover": stayover}
    )
    session.add(prop)
    await session.commit()
