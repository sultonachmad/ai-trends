"""The one writer of a room's status, so every change lands in its history.

`source` says where the change was made: `mobile` from a phone, `staff` from a desk
(the PRD measures how many housekeeping updates come from phones).
"""

import datetime as dt
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Unit, UnitStatusLog
from app.tenancy.context import TenantContext

VACANT, OCCUPIED = "vacant", "occupied"
DIRTY = "dirty"
IN_PROGRESS = "in_progress"
CLEAN = "clean"
INSPECTED = "inspected"
READY = (CLEAN, INSPECTED)
STAFF, MOBILE = "staff", "mobile"
OUT_OF_ORDER = "out_of_order"
IN_SERVICE = "in_service"


def is_ready(unit: Unit, ready_when: str = CLEAN) -> bool:
    """Ready for a guest: clean or inspected, or only inspected when the property asks."""
    if ready_when == INSPECTED:
        return unit.hk_status == INSPECTED
    return unit.hk_status in READY


def _log(
    session: AsyncSession,
    context: TenantContext,
    unit: Unit,
    field: str,
    old: str,
    new: str,
    now: dt.datetime,
    source: str,
    task_id: UUID | None,
) -> None:
    session.add(
        UnitStatusLog(
            tenant_id=context.tenant_id,
            unit_id=unit.id,
            field=field,
            old_value=old,
            new_value=new,
            source=source,
            task_id=task_id,
            changed_by=str(context.user_id),
            changed_at=now,
        )
    )


def set_unit_status(
    session: AsyncSession,
    context: TenantContext,
    unit: Unit,
    *,
    fo: str | None = None,
    hk: str | None = None,
    service: str | None = None,
    source: str = STAFF,
    task_id: UUID | None = None,
) -> None:
    """Change the room's status and log what really changed. Does not commit."""
    now = dt.datetime.now(dt.UTC)
    if fo is not None and fo != unit.fo_status:
        _log(session, context, unit, "fo_status", unit.fo_status, fo, now, source, task_id)
        unit.fo_status = fo
    if hk is not None and hk != unit.hk_status:
        _log(session, context, unit, "hk_status", unit.hk_status, hk, now, source, task_id)
        unit.hk_status = hk
        unit.hk_status_changed_at = now
    if service is not None and service != unit.service_status:
        _log(
            session,
            context,
            unit,
            "service_status",
            unit.service_status,
            service,
            now,
            source,
            task_id,
        )
        unit.service_status = service
    session.add(unit)
