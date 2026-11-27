"""Repair requests: report, give to someone, being fixed, waiting, fixed or cancelled.

Shown as four steps: Open (`open`, `assigned`), Being fixed (`in_progress`), Waiting
(`waiting_parts`) and Fixed (`completed`); or Cancelled. Numbers are per property
(MT-0001), handed out under a transaction lock so two reports never share one.
"""

import datetime as dt
import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Property, StaffMember, Task, Unit, WorkOrder
from app.services import maintenance_errors as errors
from app.services import tenant_audit
from app.services.bookings import lock_property
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

OPEN, ASSIGNED, FIXING, WAITING = "open", "assigned", "in_progress", "waiting_parts"
FIXED, CANCELLED = "completed", "cancelled"
LIVE = (OPEN, ASSIGNED, FIXING, WAITING)
URGENT, NORMAL = "urgent", "normal"
FROM_STAFF, FROM_HOUSEKEEPING = "staff", "housekeeping"
PREFIX = "MT-"
TITLE_LENGTH = 80
ENTITY = "workorder"
_NUMBER_LOCK = text("SELECT pg_advisory_xact_lock(hashtext(:key))")


async def _next_number(session: AsyncSession, context: TenantContext, property_id: UUID) -> str:
    """The property's next request number. The lock is taken last and held to commit."""
    await session.execute(_NUMBER_LOCK, {"key": f"workorder-number:{property_id}"})
    count = (
        await session.exec(
            select(func.count()).where(
                col(WorkOrder.tenant_id) == context.tenant_id,
                col(WorkOrder.property_id) == property_id,
            )
        )
    ).one()
    return f"{PREFIX}{int(count) + 1:04d}"


async def _room(
    session: AsyncSession, context: TenantContext, prop: Property, unit_id: UUID
) -> Unit:
    unit = (
        await session.exec(
            select(Unit).where(
                col(Unit.tenant_id) == context.tenant_id,
                col(Unit.property_id) == prop.id,
                col(Unit.id) == unit_id,
            )
        )
    ).first()
    if unit is None:
        raise errors.WhereNeededError
    return unit


def new_request(
    context: TenantContext,
    prop: Property,
    number: str,
    *,
    unit_id: UUID | None,
    place: str | None,
    category: str,
    urgent: bool,
    description: str,
) -> WorkOrder:
    return WorkOrder(
        tenant_id=context.tenant_id,
        property_id=prop.id,
        number=number,
        unit_id=unit_id,
        place=place,
        category=category,
        priority=URGENT if urgent else NORMAL,
        status=OPEN,
        title=description[:TITLE_LENGTH],
        description=description,
        source=FROM_STAFF,
        reported_by_staff_id=context.staff_member_id,
        created_by=str(context.user_id),
        updated_by=str(context.user_id),
    )


async def report(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    *,
    unit_id: UUID | None,
    place: str | None,
    category: str,
    urgent: bool,
    description: str,
    photo_id: UUID | None = None,
) -> WorkOrder:
    """A new request. The photo, if any, is already stored. Commits."""
    if unit_id is None and not place:
        raise errors.WhereNeededError
    if unit_id is not None:
        await _room(session, context, prop, unit_id)
    # The property first (as every other writer that adds rows for it), then the number.
    await lock_property(session, context, prop.id)
    number = await _next_number(session, context, prop.id)
    order = new_request(
        context,
        prop,
        number,
        unit_id=unit_id,
        place=place,
        category=category,
        urgent=urgent,
        description=description,
    )
    order.photo_document_ids = [photo_id] if photo_id else []
    session.add(order)
    await session.flush()
    await _audit(session, context, order, "maintenance.reported", {"number": number})
    await session.commit()
    log.info("Repair reported property=%s number=%s", prop.id, number)
    return order


async def from_cleaning(
    session: AsyncSession, context: TenantContext, task: Task, note: str | None
) -> None:
    """A housekeeper's "needs repair" becomes a request (once per task). Does not commit."""
    existing = (
        await session.exec(
            select(WorkOrder.id).where(
                col(WorkOrder.tenant_id) == context.tenant_id, col(WorkOrder.task_id) == task.id
            )
        )
    ).first()
    if existing is not None:
        return
    number = await _next_number(session, context, task.property_id)
    order = WorkOrder(
        tenant_id=context.tenant_id,
        property_id=task.property_id,
        number=number,
        unit_id=task.unit_id,
        category="other",
        priority=NORMAL,
        status=OPEN,
        title=(note or "Reported while cleaning")[:TITLE_LENGTH],
        description=note or "Reported while cleaning",
        source=FROM_HOUSEKEEPING,
        reported_by_staff_id=context.staff_member_id,
        task_id=task.id,
        created_by=str(context.user_id),
        updated_by=str(context.user_id),
    )
    session.add(order)
    await session.flush()
    await _audit(session, context, order, "maintenance.reported", {"number": number})


async def locked_request(
    session: AsyncSession, context: TenantContext, prop: Property, order_id: UUID
) -> WorkOrder:
    order = (
        await session.exec(
            select(WorkOrder)
            .where(
                col(WorkOrder.tenant_id) == context.tenant_id,
                col(WorkOrder.property_id) == prop.id,
                col(WorkOrder.id) == order_id,
            )
            .with_for_update()
        )
    ).first()
    if order is None:
        raise errors.RequestNotFoundError
    return order


def _may_work(order: WorkOrder, context: TenantContext, can_manage: bool) -> None:
    """The person it is given to, anyone while nobody has it, or a supervisor."""
    if order.status not in LIVE:
        raise errors.RequestClosedError
    free = order.assigned_staff_id is None and order.vendor_name is None
    mine = free or order.assigned_staff_id == context.staff_member_id
    if not (mine or can_manage):
        raise errors.NotYourRequestError


async def _save(
    session: AsyncSession, context: TenantContext, order: WorkOrder, event: str, payload: dict
) -> WorkOrder:
    order.updated_by = str(context.user_id)
    session.add(order)
    await _audit(session, context, order, event, payload)
    await session.commit()
    await session.refresh(order)
    return order


async def start(
    session: AsyncSession, context: TenantContext, prop: Property, order_id: UUID, can_manage: bool
) -> WorkOrder:
    order = await locked_request(session, context, prop, order_id)
    _may_work(order, context, can_manage)
    if order.assigned_staff_id is None and order.vendor_name is None:
        order.assigned_staff_id = context.staff_member_id
    order.status, order.status_note = FIXING, None
    order.started_at = order.started_at or dt.datetime.now(dt.UTC)
    return await _save(session, context, order, "maintenance.started", {})


async def wait(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    order_id: UUID,
    note: str,
    can_manage: bool,
) -> WorkOrder:
    order = await locked_request(session, context, prop, order_id)
    _may_work(order, context, can_manage)
    order.status, order.status_note = WAITING, note
    return await _save(session, context, order, "maintenance.waiting", {"note": note})


async def fix(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    order_id: UUID,
    *,
    note: str | None,
    cost: Decimal | None,
    can_manage: bool,
) -> WorkOrder:
    """Fixed. A room taken off sale for it goes back on sale (needing a clean). Commits."""
    from app.services.maintenance_blocks import has_block, release_for

    await lock_property(session, context, prop.id)  # as off sale: property, then request
    order = await locked_request(session, context, prop, order_id)
    _may_work(order, context, can_manage)
    if not can_manage and await has_block(session, context, order.id):
        raise errors.SupervisorNeededError  # only supervisors put a room back on sale
    now = dt.datetime.now(dt.UTC)
    order.status, order.status_note, order.parts_cost = FIXED, note, cost
    order.completed_at, order.started_at = now, order.started_at or now
    await release_for(session, context, prop, order)
    payload = {"cost": str(cost) if cost is not None else None}
    return await _save(session, context, order, "maintenance.fixed", payload)


async def cancel(
    session: AsyncSession, context: TenantContext, prop: Property, order_id: UUID, reason: str
) -> WorkOrder:
    from app.services.maintenance_blocks import release_for

    await lock_property(session, context, prop.id)  # as off sale: property, then request
    order = await locked_request(session, context, prop, order_id)
    if order.status not in LIVE:
        raise errors.RequestClosedError
    order.status, order.status_note = CANCELLED, reason
    await release_for(session, context, prop, order)
    return await _save(session, context, order, "maintenance.cancelled", {"reason": reason})


async def assign(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    order_id: UUID,
    *,
    staff_id: UUID | None,
    vendor_name: str | None,
) -> WorkOrder:
    """Give it to a staff member, or to an outside repairer by name, or to nobody."""
    order = await locked_request(session, context, prop, order_id)
    if order.status not in LIVE:
        raise errors.RequestClosedError
    if staff_id is not None and not await _active_staff(session, context, staff_id):
        raise errors.UnknownStaffError
    order.assigned_staff_id, order.vendor_name = staff_id, vendor_name
    if order.status in (OPEN, ASSIGNED):
        order.status = ASSIGNED if (staff_id or vendor_name) else OPEN
    payload = {"staff": str(staff_id) if staff_id else None, "vendor": vendor_name}
    return await _save(session, context, order, "maintenance.assigned", payload)


async def _active_staff(session: AsyncSession, context: TenantContext, staff_id: UUID) -> bool:
    found = await session.exec(
        select(StaffMember.id).where(
            col(StaffMember.tenant_id) == context.tenant_id,
            col(StaffMember.id) == staff_id,
            col(StaffMember.status) == "active",
            col(StaffMember.user_id).is_not(None),
        )
    )
    return found.first() is not None


async def _audit(
    session: AsyncSession, context: TenantContext, order: WorkOrder, event: str, payload: dict
) -> None:
    await tenant_audit.record(
        session,
        context,
        event,
        property_id=order.property_id,
        entity_table=ENTITY,
        entity_id=order.id,
        payload=payload,
    )
