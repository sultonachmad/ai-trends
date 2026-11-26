"""Cash drawers: one per staff member and shift.

A drawer opens with a float. Desk payments and refunds a person records for today go to
their open drawer (one opens with no float if none is open). Paid-outs (petty cash) are
outgoing cash with a reason. Refunds and paid-outs are cash movements, not payments, so
they never change what a booking owes or the booking figures. Closing a drawer stores the
count; the difference is worked out by the database and needs a note when not zero.
"""

import datetime as dt
import logging
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import CashierShift, CashMovement, Payment, Property, StaffMember
from app.schemas.end_of_day import DrawerRead, MethodTotal
from app.services import calendar_dates as dates_of
from app.services import end_of_day_errors as errors
from app.services import tenant_audit
from app.services.bookings import lock_property
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

OPEN, CLOSED = "open", "closed"
CASH = "cash"
CAPTURED = "captured"
INBOUND = "inbound"
PAID_OUT, REFUND = "paid_out", "refund"  # kinds of cash movement
ZERO = Decimal("0")
FRONT_DESK = "front_desk"
ENTITY = "cashiershift"


async def _open_drawer_of(
    session: AsyncSession, context: TenantContext, property_id: UUID, *, lock: bool = True
) -> CashierShift | None:
    if context.staff_member_id is None:
        return None
    query = select(CashierShift).where(
        col(CashierShift.tenant_id) == context.tenant_id,
        col(CashierShift.property_id) == property_id,
        col(CashierShift.staff_member_id) == context.staff_member_id,
        col(CashierShift.status) == OPEN,
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    return (await session.exec(query)).first()


def _new_drawer(context: TenantContext, prop: Property, opening_float: Decimal) -> CashierShift:
    if context.staff_member_id is None:
        raise errors.NoStaffProfileError
    return CashierShift(
        tenant_id=context.tenant_id,
        property_id=prop.id,
        staff_member_id=context.staff_member_id,
        outlet_code=FRONT_DESK,
        business_date=dates_of.property_today(prop.timezone),
        opening_float=opening_float,
        status=OPEN,
        created_by=str(context.user_id),
    )


async def current_or_open(
    session: AsyncSession, context: TenantContext, prop: Property
) -> CashierShift:
    """The caller's open drawer, opened with no float if there is none. Flushed.

    Callers hold the property lock, so two payments at once cannot open two drawers.
    """
    drawer = await _open_drawer_of(session, context, prop.id)
    if drawer is not None and drawer.business_date < dates_of.property_today(prop.timezone):
        raise errors.StaleDrawerError  # yesterday's cash and today's must not mix
    if drawer is None:
        drawer = _new_drawer(context, prop, Decimal("0"))
        session.add(drawer)
        await session.flush()
        log.info("cash drawer opened automatically drawer=%s", drawer.id)
    return drawer


async def drawer_for_entry(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    *,
    method: str,
    on: dt.date,
    cash_leaves_now: bool = False,
) -> UUID | None:
    """The drawer a desk entry belongs to.

    Cash taken today goes to the person's drawer (opened if needed). Cash handed out now
    (a refund, whatever date it is for) leaves the drawer it is in. Other methods are
    noted on an open drawer for its totals by method, but never open one.
    """
    if context.staff_member_id is None:
        return None
    today = dates_of.property_today(prop.timezone)
    if method == CASH and (on == today or cash_leaves_now):
        return (await current_or_open(session, context, prop)).id
    if method == CASH or on != today:
        return None  # cash received earlier is not in today's drawer
    drawer = await _open_drawer_of(session, context, prop.id)
    return drawer.id if drawer is not None and drawer.business_date == today else None


async def ensure_drawer_open(
    session: AsyncSession, context: TenantContext, drawer_id: UUID | None
) -> None:
    """A payment in a counted drawer cannot change: the count would no longer match."""
    if drawer_id is None:
        return
    drawer = await session.get(CashierShift, drawer_id)
    if drawer is not None and drawer.tenant_id == context.tenant_id and drawer.status != OPEN:
        raise errors.DrawerClosedError


def cash_movement(
    context: TenantContext,
    prop: Property,
    *,
    amount: Decimal,
    method: str,
    kind: str,
    on: dt.datetime,
    drawer_id: UUID | None,
    reservation_id: UUID | None = None,
    reason: str | None = None,
) -> CashMovement:
    """Money out that is not a booking payment: a refund or a paid-out."""
    return CashMovement(
        tenant_id=context.tenant_id,
        property_id=prop.id,
        cashier_shift_id=drawer_id,
        reservation_id=reservation_id,
        kind=kind,
        method=method,
        amount=amount,
        occurred_at=on,
        reason=reason,
        recorded_by=str(context.user_id),
    )


# ---- totals -----------------------------------------------------------------------------


async def _staff_names(session: AsyncSession, context: TenantContext, ids: set) -> dict:
    if not ids:
        return {}
    rows = await session.exec(
        select(StaffMember.id, StaffMember.display_name).where(
            col(StaffMember.tenant_id) == context.tenant_id, col(StaffMember.id).in_(ids)
        )
    )
    return dict(rows.all())


@dataclass(frozen=True)
class _Flows:
    payments: list[Payment]
    moves: list[CashMovement]


async def _flows_of(
    session: AsyncSession, context: TenantContext, drawer_ids: list[UUID]
) -> dict[UUID, _Flows]:
    if not drawer_ids:
        return {}
    payments = await session.exec(
        select(Payment).where(
            col(Payment.tenant_id) == context.tenant_id,
            col(Payment.cashier_shift_id).in_(drawer_ids),
            col(Payment.status) == CAPTURED,
        )
    )
    moves = await session.exec(
        select(CashMovement).where(
            col(CashMovement.tenant_id) == context.tenant_id,
            col(CashMovement.cashier_shift_id).in_(drawer_ids),
        )
    )
    paid: dict[UUID, list[Payment]] = defaultdict(list)
    for payment in payments.all():
        paid[payment.cashier_shift_id].append(payment)
    out: dict[UUID, list[CashMovement]] = defaultdict(list)
    for move in moves.all():
        out[move.cashier_shift_id].append(move)
    return {d: _Flows(paid[d], out[d]) for d in drawer_ids}


def _read(drawer: CashierShift, flows: _Flows, staff_name: str) -> DrawerRead:
    by_method: dict[str, list[Decimal]] = defaultdict(lambda: [ZERO, ZERO])
    for payment in flows.payments:
        by_method[payment.method][0] += payment.amount
    for move in flows.moves:
        by_method[move.method][1] += move.amount
    cash = [m for m in flows.moves if m.method == CASH]
    cash_in = sum((p.amount for p in flows.payments if p.method == CASH), ZERO)
    cash_out = sum((m.amount for m in cash if m.kind == REFUND), ZERO)
    paid_outs = sum((m.amount for m in cash if m.kind == PAID_OUT), ZERO)
    expected = drawer.opening_float + cash_in - cash_out - paid_outs
    return DrawerRead(
        id=drawer.id,
        staff_name=staff_name,
        business_date=drawer.business_date,
        opened_at=drawer.opened_at,
        closed_at=drawer.closed_at,
        status=drawer.status,
        opening_float=drawer.opening_float,
        cash_in=cash_in,
        cash_out=cash_out,
        paid_outs=paid_outs,
        expected_cash=drawer.expected_cash if drawer.status != OPEN else expected,
        counted_cash=drawer.counted_cash,
        variance=drawer.variance,
        notes=drawer.notes,
        by_method=[
            MethodTotal(method=method, received=pair[0], paid_out=pair[1])
            for method, pair in sorted(by_method.items())
        ],
    )


async def read_drawers(
    session: AsyncSession, context: TenantContext, drawers: list[CashierShift]
) -> list[DrawerRead]:
    flows = await _flows_of(session, context, [d.id for d in drawers])
    names = await _staff_names(session, context, {d.staff_member_id for d in drawers})
    return [_read(d, flows[d.id], names.get(d.staff_member_id, "")) for d in drawers]


async def drawers_of_day(
    session: AsyncSession, context: TenantContext, property_id: UUID, day: dt.date
) -> list[CashierShift]:
    rows = await session.exec(
        select(CashierShift)
        .where(
            col(CashierShift.tenant_id) == context.tenant_id,
            col(CashierShift.property_id) == property_id,
            col(CashierShift.business_date) == day,
        )
        .order_by(col(CashierShift.opened_at))
    )
    return list(rows.all())


# ---- actions ----------------------------------------------------------------------------


async def read_mine(
    session: AsyncSession, context: TenantContext, prop: Property
) -> DrawerRead | None:
    drawer = await _open_drawer_of(session, context, prop.id, lock=False)
    return (await read_drawers(session, context, [drawer]))[0] if drawer else None


async def _record(
    session: AsyncSession, context: TenantContext, drawer: CashierShift, event: str, detail: dict
) -> None:
    await tenant_audit.record(
        session,
        context,
        event,
        property_id=drawer.property_id,
        entity_table=ENTITY,
        entity_id=drawer.id,
        payload=detail,
    )
    await session.commit()


async def open_drawer(
    session: AsyncSession, context: TenantContext, prop: Property, opening_float: Decimal
) -> DrawerRead:
    await lock_property(session, context, prop.id)
    if await _open_drawer_of(session, context, prop.id) is not None:
        raise errors.DrawerOpenError
    drawer = _new_drawer(context, prop, opening_float)
    session.add(drawer)
    await session.flush()
    await _record(session, context, drawer, "drawer.opened", {"float": str(opening_float)})
    return (await read_drawers(session, context, [drawer]))[0]


async def paid_out(
    session: AsyncSession, context: TenantContext, prop: Property, amount: Decimal, reason: str
) -> DrawerRead:
    """Petty cash taken from the drawer, with a reason. Commits."""
    await lock_property(session, context, prop.id)
    drawer = await current_or_open(session, context, prop)
    session.add(
        cash_movement(
            context,
            prop,
            amount=amount,
            method=CASH,
            kind=PAID_OUT,
            on=dt.datetime.now(dt.UTC),
            drawer_id=drawer.id,
            reason=reason,
        )
    )
    await _record(
        session, context, drawer, "drawer.paid_out", {"amount": str(amount), "reason": reason}
    )
    return (await read_drawers(session, context, [drawer]))[0]


async def close_drawer(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    counted: Decimal,
    note: str | None,
) -> DrawerRead:
    """Count the cash and close. A difference needs a note. Commits."""
    await lock_property(session, context, prop.id)
    drawer = await _open_drawer_of(session, context, prop.id)
    if drawer is None:
        raise errors.NoDrawerError
    expected = (await read_drawers(session, context, [drawer]))[0].expected_cash
    if counted != expected and not note:
        raise errors.NoteNeededError
    drawer.expected_cash, drawer.counted_cash = expected, counted
    drawer.closed_at, drawer.status = dt.datetime.now(dt.UTC), CLOSED
    drawer.notes = note
    drawer.updated_by = str(context.user_id)
    session.add(drawer)
    await _record(
        session,
        context,
        drawer,
        "drawer.closed",
        {"expected": str(expected), "counted": str(counted), "note": note},
    )
    await session.refresh(drawer)  # the difference the database worked out
    return (await read_drawers(session, context, [drawer]))[0]
