"""Production by booking source for a period, computed live from the bookings.

Revenue is the value of the nights stayed inside the period on confirmed bookings, so a
stay across two months is split between them. It is not cash received. Commission is the
amount stored on each booking, spread by that booking's nightly revenue and rounded once
per booking, so rows always add up to the totals.
"""

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Channel, Property, Reservation, ReservationDailyRate, ReservationUnit
from app.schemas.reports import ChannelReport, ReportFigures, ReportRow
from app.services import calendar_dates as dates_of
from app.services.booking_holds import BOOKING_PAGE
from app.services.stay_status import CANCELLED, EARNING
from app.tenancy.context import TenantContext

MAX_REPORT_DAYS = 366
_CENTS = Decimal("0.01")
_TENTH = Decimal("0.1")
_ZERO = Decimal("0")


@dataclass
class _Tally:
    bookings: int = 0
    nights: int = 0
    revenue: Decimal = _ZERO
    commission: Decimal = _ZERO
    cancelled: int = 0

    def add(self, other: "_Tally") -> None:
        self.bookings += other.bookings
        self.nights += other.nights
        self.revenue += other.revenue
        self.commission += other.commission
        self.cancelled += other.cancelled


def commission_in_period(
    commission: Decimal | None, period_revenue: Decimal, booking_total: Decimal
) -> Decimal:
    """The booking's commission for its nights in the period, rounded once."""
    if not commission or booking_total <= _ZERO:
        return _ZERO
    share = commission * period_revenue / booking_total
    return min(share.quantize(_CENTS, rounding=ROUND_HALF_UP), commission)


def _percent(part: Decimal | int, whole: Decimal | int) -> Decimal:
    if not whole:
        return _ZERO.quantize(_TENTH)
    return (Decimal(part) * 100 / Decimal(whole)).quantize(_TENTH, rounding=ROUND_HALF_UP)


def _figures(tally: _Tally) -> dict[str, object]:
    average = tally.revenue / tally.nights if tally.nights else _ZERO
    return {
        "bookings": tally.bookings,
        "nights": tally.nights,
        "revenue": tally.revenue.quantize(_CENTS),
        "average_per_night": average.quantize(_CENTS, rounding=ROUND_HALF_UP),
        "cancelled": tally.cancelled,
        "cancellation_rate": _percent(tally.cancelled, tally.bookings + tally.cancelled),
        "commission": tally.commission.quantize(_CENTS),
        "net_revenue": (tally.revenue - tally.commission).quantize(_CENTS),
    }


async def _stayed(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    start: dt.date,
    end: dt.date,
) -> dict[UUID, _Tally]:
    """Confirmed bookings' nights, revenue and commission inside the period, per source."""
    rows = await session.exec(
        select(
            col(Reservation.channel_id),
            col(Reservation.commission_amount),
            col(Reservation.total_amount),
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
            col(Reservation.property_id) == property_id,
            col(Reservation.status).in_(EARNING),
            col(ReservationDailyRate.stay_date) >= start,
            col(ReservationDailyRate.stay_date) <= end,
        )
        .group_by(col(Reservation.id))
    )
    tallies: dict[UUID, _Tally] = defaultdict(_Tally)
    for channel_id, commission, total, nights, revenue in rows.all():
        tally = tallies[channel_id]
        tally.bookings += 1
        tally.nights += int(nights)
        tally.revenue += revenue
        tally.commission += commission_in_period(commission, revenue, total)
    return tallies


async def _cancelled(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    start: dt.date,
    end: dt.date,
) -> dict[UUID, int]:
    """Real cancellations of stays touching the period, per source.

    A booking-page hold that was never paid was never a booking, so it does not count.
    """
    rows = await session.exec(
        select(
            col(Reservation.channel_id),
            col(Reservation.booked_by),
            col(Reservation.source_detail),
        ).where(
            col(Reservation.tenant_id) == context.tenant_id,
            col(Reservation.property_id) == property_id,
            col(Reservation.status) == CANCELLED,
            col(Reservation.arrival_date) <= end,
            col(Reservation.departure_date) > start,
        )
    )
    counts: dict[UUID, int] = defaultdict(int)
    for channel_id, booked_by, detail in rows.all():
        if booked_by == BOOKING_PAGE and "confirmation" not in (detail or {}):
            continue
        counts[channel_id] += 1
    return counts


async def read_report(
    session: AsyncSession, context: TenantContext, prop: Property, start: dt.date, end: dt.date
) -> ChannelReport:
    """The report for `start` to `end` inclusive, at the property's dates."""
    dates_of.check_read_window(start, end, max_days=MAX_REPORT_DAYS)
    tallies = await _stayed(session, context, prop.id, start, end)
    for channel_id, count in (await _cancelled(session, context, prop.id, start, end)).items():
        tallies[channel_id].cancelled += count
    channels = (
        (
            await session.exec(
                select(Channel).where(
                    col(Channel.tenant_id) == context.tenant_id,
                    col(Channel.id).in_(list(tallies)),
                )
            )
        ).all()
        if tallies
        else []
    )
    total, direct, sold = _Tally(), _Tally(), _Tally()
    for channel in channels:
        tally = tallies[channel.id]
        total.add(tally)
        (direct if channel.is_direct else sold).add(tally)
    rows = [
        ReportRow(
            code=channel.code,
            name=channel.name,
            is_direct=channel.is_direct,
            revenue_share=_percent(tallies[channel.id].revenue, total.revenue),
            **_figures(tallies[channel.id]),
        )
        for channel in channels
    ]
    rows.sort(key=lambda row: (-row.revenue, row.name))
    return ChannelReport(
        start=start,
        end=end,
        rows=rows,
        direct=ReportFigures(**_figures(direct)),
        channels=ReportFigures(**_figures(sold)),
        total=ReportFigures(**_figures(total)),
    )
