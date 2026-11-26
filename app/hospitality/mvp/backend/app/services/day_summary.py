"""One day's figures: rooms, movements, extras and money. Frozen when the day is closed.

Room revenue follows the channel report: the nightly prices of earning bookings, as
priced. Money is what was received or paid out on the day (property time), by method.
Amounts are strings, so the frozen snapshot keeps every rupiah exactly.
"""

import datetime as dt
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import (
    CashMovement,
    FolioTransaction,
    Payment,
    Property,
    Reservation,
    ReservationDailyRate,
    ReservationUnit,
    TransactionCode,
    Unit,
)
from app.services.bills import CATEGORY_OF_CODE
from app.services.cash_drawers import CAPTURED, INBOUND
from app.services.stay_status import EARNING, LEFT_UNPAID, NO_SHOW
from app.tenancy.context import TenantContext
from app.tenancy.timezones import property_zone

ZERO = Decimal("0")
WHOLE = Decimal("1")
TENTH = Decimal("0.1")


def day_bounds(day: dt.date, timezone: str) -> tuple[dt.datetime, dt.datetime]:
    """The day at the property, as a UTC range [start, end)."""
    zone = property_zone(timezone)
    start = dt.datetime.combine(day, dt.time(0), tzinfo=zone)
    return start.astimezone(dt.UTC), (start + dt.timedelta(days=1)).astimezone(dt.UTC)


def _money(value: Decimal) -> str:
    return str(value.quantize(WHOLE, rounding=ROUND_HALF_UP))


async def _rooms(
    session: AsyncSession, context: TenantContext, property_id: UUID, day: dt.date
) -> dict:
    available = (
        await session.exec(
            select(func.count(col(Unit.id))).where(
                col(Unit.tenant_id) == context.tenant_id,
                col(Unit.property_id) == property_id,
                col(Unit.is_active).is_(True),
                col(Unit.is_sellable).is_(True),
            )
        )
    ).one()
    sold, revenue = (
        await session.exec(
            select(func.count(col(ReservationDailyRate.id)), func.sum(ReservationDailyRate.amount))
            .join(
                ReservationUnit,
                (col(ReservationUnit.tenant_id) == col(ReservationDailyRate.tenant_id))
                & (col(ReservationUnit.id) == col(ReservationDailyRate.reservation_unit_id)),
            )
            .join(
                Reservation,
                (col(Reservation.tenant_id) == col(ReservationUnit.tenant_id))
                & (col(Reservation.id) == col(ReservationUnit.reservation_id)),
            )
            .where(
                col(Reservation.tenant_id) == context.tenant_id,
                col(Reservation.property_id) == property_id,
                col(Reservation.status).in_(EARNING),
                col(ReservationDailyRate.stay_date) == day,
            )
        )
    ).one()
    revenue = revenue or ZERO
    return {
        "available": available,
        "sold": sold,
        "occupancy_pct": str((Decimal(sold * 100) / available).quantize(TENTH))
        if available
        else "0.0",
        "revenue": _money(revenue),
        "adr": _money(revenue / sold) if sold else "0",
        "revpar": _money(revenue / available) if available else "0",
    }


async def _count_lines(
    session: AsyncSession, context: TenantContext, property_id: UUID, column, bounds: tuple
) -> int:  # noqa: ANN001 — a ReservationUnit time column
    return (
        await session.exec(
            select(func.count(func.distinct(col(ReservationUnit.reservation_id)))).where(
                col(ReservationUnit.tenant_id) == context.tenant_id,
                col(ReservationUnit.property_id) == property_id,
                column >= bounds[0],
                column < bounds[1],
            )
        )
    ).one()


async def _movements(
    session: AsyncSession, context: TenantContext, prop: Property, day: dt.date
) -> dict:
    bounds = day_bounds(day, prop.timezone)
    mine = (
        col(Reservation.tenant_id) == context.tenant_id,
        col(Reservation.property_id) == prop.id,
    )
    no_shows = await session.exec(
        select(func.count(col(Reservation.id))).where(
            *mine, col(Reservation.status) == NO_SHOW, col(Reservation.arrival_date) == day
        )
    )
    cancelled = await session.exec(
        select(func.count(col(Reservation.id))).where(
            *mine,
            col(Reservation.cancelled_at) >= bounds[0],
            col(Reservation.cancelled_at) < bounds[1],
        )
    )
    return {
        "arrivals": await _count_lines(
            session, context, prop.id, col(ReservationUnit.checked_in_at), bounds
        ),
        "departures": await _count_lines(
            session, context, prop.id, col(ReservationUnit.checked_out_at), bounds
        ),
        "no_shows": no_shows.one(),
        "cancellations": cancelled.one(),
    }


async def _extras(
    session: AsyncSession, context: TenantContext, property_id: UUID, day: dt.date
) -> list[dict]:
    rows = await session.exec(
        select(TransactionCode.code, func.sum(FolioTransaction.amount))
        .join(
            TransactionCode,
            (col(TransactionCode.tenant_id) == col(FolioTransaction.tenant_id))
            & (col(TransactionCode.id) == col(FolioTransaction.transaction_code_id)),
        )
        .where(
            col(FolioTransaction.tenant_id) == context.tenant_id,
            col(FolioTransaction.property_id) == property_id,
            col(FolioTransaction.business_date) == day,
        )
        .group_by(TransactionCode.code)
    )
    by_category: dict[str, Decimal] = defaultdict(Decimal)
    for code, amount in rows.all():
        by_category[CATEGORY_OF_CODE.get(code, "other")] += amount or ZERO
    return [{"category": c, "amount": _money(a)} for c, a in sorted(by_category.items()) if a]


async def _payments_on(
    session: AsyncSession, context: TenantContext, property_id: UUID, bounds: tuple
) -> list[tuple[Payment, dt.date | None]]:
    rows = await session.exec(
        select(Payment, Reservation.arrival_date)
        .outerjoin(
            Reservation,
            (col(Reservation.tenant_id) == col(Payment.tenant_id))
            & (col(Reservation.id) == col(Payment.reservation_id)),
        )
        .where(
            col(Payment.tenant_id) == context.tenant_id,
            col(Payment.property_id) == property_id,
            col(Payment.status) == CAPTURED,
            col(Payment.direction) == INBOUND,
            col(Payment.captured_at) >= bounds[0],
            col(Payment.captured_at) < bounds[1],
        )
    )
    return list(rows.all())


async def _moves_on(
    session: AsyncSession, context: TenantContext, property_id: UUID, bounds: tuple
) -> list[CashMovement]:
    rows = await session.exec(
        select(CashMovement).where(
            col(CashMovement.tenant_id) == context.tenant_id,
            col(CashMovement.property_id) == property_id,
            col(CashMovement.occurred_at) >= bounds[0],
            col(CashMovement.occurred_at) < bounds[1],
        )
    )
    return list(rows.all())


def _money_block(
    rows: list[tuple[Payment, dt.date | None]], moves: list[CashMovement], day: dt.date
) -> dict:
    received: dict[str, Decimal] = defaultdict(Decimal)
    paid_out: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    online = deposits = ZERO
    for payment, arrival in rows:
        received[payment.method] += payment.amount
        online += payment.amount if payment.payment_link_id else ZERO
        deposits += payment.amount if arrival and arrival > day else ZERO
    for move in moves:
        paid_out[(move.kind, move.method)] += move.amount
    return {
        "received": [{"method": m, "amount": _money(a)} for m, a in sorted(received.items())],
        "received_total": _money(sum(received.values(), ZERO)),
        "online": _money(online),
        "deposits": _money(deposits),
        "paid_out": [
            {"kind": k, "method": m, "amount": _money(a)} for (k, m), a in sorted(paid_out.items())
        ],
    }


async def left_unpaid(
    session: AsyncSession, context: TenantContext, prop: Property, bounds: tuple
) -> dict:
    rows = await session.exec(
        select(Reservation.id, Reservation.source_detail)
        .join(
            ReservationUnit,
            (col(ReservationUnit.tenant_id) == col(Reservation.tenant_id))
            & (col(ReservationUnit.reservation_id) == col(Reservation.id)),
        )
        .where(
            col(Reservation.tenant_id) == context.tenant_id,
            col(Reservation.property_id) == prop.id,
            col(ReservationUnit.checked_out_at) >= bounds[0],
            col(ReservationUnit.checked_out_at) < bounds[1],
            col(Reservation.source_detail).has_key(LEFT_UNPAID),
        )
        .distinct()
    )
    # one row per booking, however many rooms it had
    amounts = [Decimal(str(detail[LEFT_UNPAID].get("amount", 0))) for _, detail in rows.all()]
    return {"count": len(amounts), "amount": _money(sum(amounts, ZERO))}


async def read_summary(
    session: AsyncSession, context: TenantContext, prop: Property, day: dt.date
) -> dict:
    bounds = day_bounds(day, prop.timezone)
    return {
        "rooms": await _rooms(session, context, prop.id, day),
        "movements": await _movements(session, context, prop, day),
        "extras": await _extras(session, context, prop.id, day),
        "money": _money_block(
            await _payments_on(session, context, prop.id, bounds),
            await _moves_on(session, context, prop.id, bounds),
            day,
        ),
        "left_unpaid": await left_unpaid(session, context, prop, bounds),
    }
