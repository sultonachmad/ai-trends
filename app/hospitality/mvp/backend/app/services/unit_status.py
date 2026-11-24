"""The one writer of a room's status, so every change lands in its history."""

import datetime as dt

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Unit, UnitStatusLog
from app.tenancy.context import TenantContext

VACANT, OCCUPIED = "vacant", "occupied"
DIRTY = "dirty"
READY = ("clean", "inspected")
OUT_OF_ORDER = "out_of_order"


def is_ready(unit: Unit) -> bool:
    return unit.hk_status in READY


def _log(
    session: AsyncSession,
    context: TenantContext,
    unit: Unit,
    field: str,
    old: str,
    new: str,
    now: dt.datetime,
) -> None:
    session.add(
        UnitStatusLog(
            tenant_id=context.tenant_id,
            unit_id=unit.id,
            field=field,
            old_value=old,
            new_value=new,
            source="staff",
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
) -> None:
    """Change the room's status and log what really changed. Does not commit."""
    now = dt.datetime.now(dt.UTC)
    if fo is not None and fo != unit.fo_status:
        _log(session, context, unit, "fo_status", unit.fo_status, fo, now)
        unit.fo_status = fo
    if hk is not None and hk != unit.hk_status:
        _log(session, context, unit, "hk_status", unit.hk_status, hk, now)
        unit.hk_status = hk
        unit.hk_status_changed_at = now
    session.add(unit)
