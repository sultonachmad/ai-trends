"""A month's service charge and PBJT, from the same split the guest bills use.

Each room night counts on its stay date and each extra on its business date, split by
the tax rule of that date and the booking's price mode, per booking and night exactly as
`bill_taxes.bill_tax` does, so the month adds up to the bills. Bookings that earn
(confirmed, in house, checked out) count.

Bookings paid through a channel carry no tax on their bill (the channel collected the
money). They are summed apart, with the tax worked out inside the price, because whether
the property or the channel reports them differs by region [verify per region].
"""

import calendar
import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import (
    BusinessDay,
    Channel,
    Folio,
    FolioTransaction,
    Property,
    Reservation,
    ReservationDailyRate,
    ReservationUnit,
    TransactionCode,
)
from app.schemas.tax_summary import TaxAmounts, TaxBooking, TaxDay, TaxMonth
from app.services.bill_taxes import CHANNEL_COLLECTS, mode_of
from app.services.bills import CATEGORY_OF_CODE
from app.services.stay_status import EARNING
from app.services.tax_engine import NETT, split
from app.services.tax_rules import RateBook, rate_book
from app.tenancy.context import TenantContext

CLOSED = "closed"


@dataclass(frozen=True)
class Piece:
    booking_id: UUID
    day: dt.date
    kind: str  # room, extra, untaxed or channel
    nights: int
    base: Decimal
    service: Decimal
    pbjt: Decimal


def month_bounds(month: str) -> tuple[dt.date, dt.date]:
    """First and last day of `YYYY-MM`."""
    year, number = (int(part) for part in month.split("-"))
    return dt.date(year, number, 1), dt.date(year, number, calendar.monthrange(year, number)[1])


async def _nights(
    session: AsyncSession, context: TenantContext, prop: Property, first: dt.date, last: dt.date
) -> list[tuple[UUID, dt.date, int, Decimal]]:
    """(booking, night, units, amount) of earning bookings, per booking and night."""
    rows = await session.exec(
        select(
            col(Reservation.id),
            col(ReservationDailyRate.stay_date),
            func.count(col(ReservationDailyRate.id)),
            func.sum(col(ReservationDailyRate.amount)),
        )
        .join(
            ReservationUnit,
            (col(ReservationUnit.tenant_id) == col(Reservation.tenant_id))
            & (col(ReservationUnit.reservation_id) == col(Reservation.id)),
        )
        .join(
            ReservationDailyRate,
            (col(ReservationDailyRate.tenant_id) == col(ReservationUnit.tenant_id))
            & (col(ReservationDailyRate.reservation_unit_id) == col(ReservationUnit.id)),
        )
        .where(
            col(Reservation.tenant_id) == context.tenant_id,
            col(Reservation.property_id) == prop.id,
            col(Reservation.status).in_(EARNING),
            col(ReservationDailyRate.stay_date) >= first,
            col(ReservationDailyRate.stay_date) <= last,
        )
        .group_by(col(Reservation.id), col(ReservationDailyRate.stay_date))
    )
    return [(b, night, int(units), Decimal(amount)) for b, night, units, amount in rows.all()]


async def _lines(
    session: AsyncSession, context: TenantContext, prop: Property, first: dt.date, last: dt.date
) -> list[tuple[UUID, dt.date, str, Decimal]]:
    """(booking, business date, category, amount) of bill lines still standing."""
    rows = (
        await session.exec(
            select(
                col(FolioTransaction.id),
                col(FolioTransaction.kind),
                col(FolioTransaction.business_date),
                col(FolioTransaction.amount),
                col(TransactionCode.code),
                col(Reservation.id),
            )
            .join(
                Folio,
                (col(Folio.tenant_id) == col(FolioTransaction.tenant_id))
                & (col(Folio.id) == col(FolioTransaction.folio_id)),
            )
            .join(
                Reservation,
                (col(Reservation.tenant_id) == col(Folio.tenant_id))
                & (col(Reservation.id) == col(Folio.reservation_id)),
            )
            .join(
                TransactionCode,
                (col(TransactionCode.tenant_id) == col(FolioTransaction.tenant_id))
                & (col(TransactionCode.id) == col(FolioTransaction.transaction_code_id)),
            )
            .where(
                col(FolioTransaction.tenant_id) == context.tenant_id,
                col(Reservation.property_id) == prop.id,
                col(Reservation.status).in_(EARNING),
                col(FolioTransaction.kind).in_(("charge", "adjustment", "void")),
                col(FolioTransaction.business_date) >= first,
                col(FolioTransaction.business_date) <= last,
            )
        )
    ).all()
    charges = [row for row in rows if row[1] != "void"]
    voided = await _voided(session, context, [row[0] for row in charges])
    return [
        (booking_id, day, CATEGORY_OF_CODE.get(code, "other"), amount)
        for line_id, _, day, amount, code, booking_id in charges
        if line_id not in voided
    ]


async def _voided(session: AsyncSession, context: TenantContext, ids: list[UUID]) -> set[UUID]:
    """Lines voided by a void of any date (voids are same-day today; this keeps the month
    equal to the bills even if that ever changes)."""
    if not ids:
        return set()
    rows = await session.exec(
        select(col(FolioTransaction.reverses_transaction_id)).where(
            col(FolioTransaction.tenant_id) == context.tenant_id,
            col(FolioTransaction.kind) == "void",
            col(FolioTransaction.reverses_transaction_id).in_(ids),
        )
    )
    return set(rows.all())


def _night_piece(
    book: RateBook, booking: Reservation, night: dt.date, units: int, amount: Decimal
) -> Piece:
    channel = booking.payment_collect_model == CHANNEL_COLLECTS
    parts = split(amount, book.rates_on(night), NETT if channel else mode_of(booking))
    kind = "channel" if channel else "room"
    return Piece(booking.id, night, kind, units, parts.base, parts.service, parts.pbjt)


def _line_piece(
    book: RateBook, booking: Reservation, day: dt.date, category: str, amount: Decimal
) -> Piece:
    if category in book.untaxed_on(day):
        return Piece(booking.id, day, "untaxed", 0, amount, Decimal("0"), Decimal("0"))
    parts = split(amount, book.rates_on(day), mode_of(booking))
    return Piece(booking.id, day, "extra", 0, parts.base, parts.service, parts.pbjt)


def _add(total: dict, piece: Piece) -> None:
    """Add one piece to a running total held as a plain dict of TaxAmounts fields."""
    if piece.kind == "channel":
        total["channel_nights"] += piece.nights
        total["channel_base"] += piece.base
        total["channel_service"] += piece.service
        total["channel_pbjt"] += piece.pbjt
        return
    if piece.kind == "untaxed":
        total["untaxed"] += piece.base
        return
    if piece.kind == "room":
        total["room_nights"] += piece.nights
        total["room_base"] += piece.base
    else:
        total["extras_base"] += piece.base
    total["service"] += piece.service
    total["pbjt"] += piece.pbjt


def _empty() -> dict:
    """A running total (TaxAmounts fields), local to one read."""
    return TaxAmounts().model_dump()


async def _bookings(
    session: AsyncSession, context: TenantContext, ids: set[UUID]
) -> dict[UUID, Reservation]:
    if not ids:
        return {}
    rows = await session.exec(
        select(Reservation).where(
            col(Reservation.tenant_id) == context.tenant_id, col(Reservation.id).in_(ids)
        )
    )
    return {booking.id: booking for booking in rows.all()}


async def _sources(session: AsyncSession, context: TenantContext, ids: set[UUID]) -> dict:
    if not ids:
        return {}
    rows = await session.exec(
        select(Channel.id, Channel.name).where(
            col(Channel.tenant_id) == context.tenant_id, col(Channel.id).in_(ids)
        )
    )
    return dict(rows.all())


async def _closed_days(
    session: AsyncSession, context: TenantContext, prop: Property, first: dt.date, last: dt.date
) -> int:
    found = await session.exec(
        select(func.count()).where(
            col(BusinessDay.tenant_id) == context.tenant_id,
            col(BusinessDay.property_id) == prop.id,
            col(BusinessDay.business_date) >= first,
            col(BusinessDay.business_date) <= last,
            col(BusinessDay.status) == CLOSED,
        )
    )
    return int(found.one())


async def pieces(
    session: AsyncSession, context: TenantContext, prop: Property, first: dt.date, last: dt.date
) -> tuple[RateBook, dict[UUID, Reservation], list[Piece]]:
    book = await rate_book(session, context.tenant_id, prop.id)
    nights = await _nights(session, context, prop, first, last)
    lines = await _lines(session, context, prop, first, last)
    bookings = await _bookings(
        session, context, {n[0] for n in nights} | {line[0] for line in lines}
    )
    if not book.is_set:
        return book, bookings, []
    found = [_night_piece(book, bookings[b], night, u, amount) for b, night, u, amount in nights]
    found += [_line_piece(book, bookings[b], day, cat, amount) for b, day, cat, amount in lines]
    return book, bookings, found


async def read_month(
    session: AsyncSession, context: TenantContext, prop: Property, month: str
) -> TaxMonth:
    first, last = month_bounds(month)
    book, bookings, found = await pieces(session, context, prop, first, last)
    by_day: dict[dt.date, dict] = defaultdict(_empty)
    by_booking: dict[UUID, dict] = defaultdict(_empty)
    totals = _empty()
    for piece in found:
        _add(by_day[piece.day], piece)
        _add(by_booking[piece.booking_id], piece)
        _add(totals, piece)
    sources = await _sources(session, context, {b.channel_id for b in bookings.values()})
    closed = await _closed_days(session, context, prop, first, last)
    days_in_month = (last - first).days + 1
    return TaxMonth(
        month=month,
        first_day=first,
        last_day=last,
        is_set=book.is_set,
        draft=closed < days_in_month,
        closed_days=closed,
        days_in_month=days_in_month,
        days=[TaxDay(date=day, **by_day[day]) for day in sorted(by_day)],
        bookings=[
            _booking_row(bookings[booking_id], sources, by_booking[booking_id])
            for booking_id in sorted(by_booking, key=lambda b: bookings[b].confirmation_no)
        ],
        totals=TaxAmounts(**totals),
    )


def _booking_row(booking: Reservation, sources: dict, total: dict) -> TaxBooking:
    channel = booking.payment_collect_model == CHANNEL_COLLECTS
    return TaxBooking(
        booking_id=str(booking.id),
        number=booking.confirmation_no,
        arrival=booking.arrival_date,
        departure=booking.departure_date,
        source=sources.get(booking.channel_id, ""),
        price_mode=NETT if channel else mode_of(booking),
        **total,
    )
