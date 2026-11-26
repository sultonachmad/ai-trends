"""What still needs attention before a day is closed.

Blocking: confirmed guests not checked in or marked no-show, guests still in house after
their departure, cash drawers still open from that day or before. Warnings: transfer
proofs waiting, APOA overdue, guests who left unpaid that day. A blocking item can be
overridden with a reason by someone who can edit bookings.
"""

import datetime as dt
import logging
from uuid import UUID

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import (
    CashierShift,
    Guest,
    Property,
    Reservation,
    StaffMember,
    TransferProof,
)
from app.schemas.end_of_day import CheckItem, DayCheck
from app.services.cash_drawers import OPEN
from app.services.day_summary import day_bounds, left_unpaid
from app.services.stay_status import CONFIRMED, GUARANTEED, IN_HOUSE
from app.services.transfer_proofs import PENDING as PROOF_PENDING
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

BLOCKING, WARNING = "blocking", "warning"
MAX_ITEMS = 20  # names shown per check; the count is always complete


async def _bookings(
    session: AsyncSession, context: TenantContext, property_id: UUID, *conditions
) -> list[CheckItem]:  # noqa: ANN002 — SQL conditions
    rows = await session.exec(
        select(Reservation.id, Reservation.confirmation_no, Guest.full_name)
        .outerjoin(
            Guest,
            (col(Guest.tenant_id) == col(Reservation.tenant_id))
            & (col(Guest.id) == col(Reservation.booker_guest_id)),
        )
        .where(
            col(Reservation.tenant_id) == context.tenant_id,
            col(Reservation.property_id) == property_id,
            *conditions,
        )
        .order_by(col(Reservation.arrival_date), col(Reservation.confirmation_no))
    )
    return [CheckItem(booking_id=b, label=f"{n} · {g or '-'}") for b, n, g in rows.all()]


async def _open_drawers(
    session: AsyncSession, context: TenantContext, property_id: UUID, day: dt.date
) -> list[CheckItem]:
    rows = await session.exec(
        select(StaffMember.display_name, CashierShift.business_date)
        .join(
            StaffMember,
            (col(StaffMember.tenant_id) == col(CashierShift.tenant_id))
            & (col(StaffMember.id) == col(CashierShift.staff_member_id)),
        )
        .where(
            col(CashierShift.tenant_id) == context.tenant_id,
            col(CashierShift.property_id) == property_id,
            col(CashierShift.status) == OPEN,
            col(CashierShift.business_date) <= day,
        )
    )
    return [CheckItem(label=f"{name} · {opened.isoformat()}") for name, opened in rows.all()]


async def _proofs_waiting(session: AsyncSession, context: TenantContext, property_id: UUID) -> int:
    found = await session.exec(
        select(func.count(col(TransferProof.id))).where(
            col(TransferProof.tenant_id) == context.tenant_id,
            col(TransferProof.property_id) == property_id,
            col(TransferProof.match_status) == PROOF_PENDING,
        )
    )
    return found.one()


async def _apoa_overdue(session: AsyncSession, context: TenantContext, prop: Property) -> int:
    # Imported here: the APOA list builds on the front desk modules that import this one.
    from app.services.apoa_reads import counts

    try:
        async with session.begin_nested():  # a failure must not spoil the transaction
            return (await counts(session, context, prop)).overdue
    except Exception:  # noqa: BLE001 — a warning must never stop the day being read
        log.exception("APOA overdue count failed property=%s", prop.id)
        return 0


def _check(code: str, level: str, items: list[CheckItem], count: int | None = None) -> DayCheck:
    total = len(items) if count is None else count
    return DayCheck(code=code, level=level, count=total, items=items[:MAX_ITEMS])


async def read_checks(
    session: AsyncSession, context: TenantContext, prop: Property, day: dt.date
) -> list[DayCheck]:
    """The checks for `day` that are not clear; an empty list means nothing is in the way."""
    found = [
        _check(
            "arrivals_pending",
            BLOCKING,
            await _bookings(
                session,
                context,
                prop.id,
                col(Reservation.status).in_((CONFIRMED, GUARANTEED)),
                col(Reservation.arrival_date) <= day,
            ),
        ),
        _check(
            "departures_pending",
            BLOCKING,
            await _bookings(
                session,
                context,
                prop.id,
                col(Reservation.status) == IN_HOUSE,
                col(Reservation.departure_date) <= day,
            ),
        ),
        _check("drawers_open", BLOCKING, await _open_drawers(session, context, prop.id, day)),
        _check("proofs_waiting", WARNING, [], await _proofs_waiting(session, context, prop.id)),
        _check("apoa_overdue", WARNING, [], await _apoa_overdue(session, context, prop)),
    ]
    unpaid = await left_unpaid(session, context, prop, day_bounds(day, prop.timezone))
    found.append(_check("left_unpaid", WARNING, [], unpaid["count"]))
    return [check for check in found if check.count]
