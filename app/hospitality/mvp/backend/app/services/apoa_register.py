"""The APOA register: foreign guests and what was reported, for an immigration officer.

Law 6/2011 Art. 72 obliges the property to give information on foreign guests when an
immigration officer asks. The register lists each foreign guest whose stay began in the
range, with the APOA check-in and check-out marks. Numbers are masked; cells that a
spreadsheet would run as a formula are made plain text.
"""

import csv
import datetime as dt
import io
from collections import defaultdict
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import (
    ForeignGuestReport,
    Property,
    Reservation,
    ReservationGuest,
    ReservationUnit,
)
from app.services import apoa_errors as errors
from app.services import tenant_audit
from app.services.apoa_reads import APOA, ARRIVAL, DEPARTURE, DONE, masked
from app.services.guest_id_reads import staff_names
from app.tenancy.context import TenantContext

MAX_RANGE_DAYS = 366
BOM = "\ufeff"
HEADER = [
    "booking",
    "guest",
    "nationality",
    "passport",
    "visa",
    "entry_date",
    "arrival",
    "departure",
    "apoa_check_in",
    "apoa_check_in_by",
    "apoa_reference",
    "apoa_check_out",
    "apoa_check_out_by",
    "note",
]
_FORMULA_START = ("=", "+", "-", "@", "|", "\t", "\r", "\n")
MAX_ROWS = 20_000


def check_range(start: dt.date, end: dt.date) -> None:
    if end < start or (end - start).days >= MAX_RANGE_DAYS:
        raise errors.RangeError


def plain(value: object) -> str:
    """A cell a spreadsheet shows as text, never runs."""
    text = "" if value is None else str(value)
    return f"'{text}" if text.lstrip(" ").startswith(_FORMULA_START) else text


async def _marks(
    session: AsyncSession, context: TenantContext, prop: Property, start: dt.date, end: dt.date
) -> list[tuple[ForeignGuestReport, Reservation]]:
    rows = await session.exec(
        select(ForeignGuestReport, Reservation)
        .join(
            ReservationGuest,
            (col(ReservationGuest.tenant_id) == col(ForeignGuestReport.tenant_id))
            & (col(ReservationGuest.id) == col(ForeignGuestReport.reservation_guest_id)),
        )
        .join(
            ReservationUnit,
            (col(ReservationUnit.tenant_id) == col(ReservationGuest.tenant_id))
            & (col(ReservationUnit.id) == col(ReservationGuest.reservation_unit_id)),
        )
        .join(
            Reservation,
            (col(Reservation.tenant_id) == col(ReservationUnit.tenant_id))
            & (col(Reservation.id) == col(ReservationUnit.reservation_id)),
        )
        .where(
            col(ForeignGuestReport.tenant_id) == context.tenant_id,
            col(ForeignGuestReport.report_system) == APOA,
            col(ForeignGuestReport.status).in_(DONE),
            col(Reservation.property_id) == prop.id,
            col(Reservation.arrival_date) >= start,
            col(Reservation.arrival_date) <= end,
        )
        .order_by(
            col(Reservation.arrival_date),
            col(Reservation.confirmation_no),
            col(ForeignGuestReport.id),
        )
        .limit(MAX_ROWS * 2 + 1)  # two steps per guest
    )
    return list(rows.all())


def _when(report: ForeignGuestReport | None, zone: ZoneInfo) -> str:
    """Local time at the property, as staff and an officer read it."""
    if report is None or report.submitted_at is None:
        return ""
    return report.submitted_at.astimezone(zone).strftime("%Y-%m-%d %H:%M")


def _by(report: ForeignGuestReport | None, names: dict[str, str]) -> str:
    if report is None:
        return ""
    return names.get(report.submitted_by or "", report.submitted_by or "")


def _row(
    booking: Reservation,
    steps: dict[str, ForeignGuestReport],
    names: dict[str, str],
    zone: ZoneInfo,
) -> list[str]:
    arrival, departure = steps.get(ARRIVAL), steps.get(DEPARTURE)
    seen = (arrival or departure).payload
    notes = [r.payload.get("reason") for r in (arrival, departure) if r and r.payload.get("reason")]
    return [
        plain(value)
        for value in (
            booking.confirmation_no,
            seen.get("full_name"),
            seen.get("nationality"),
            masked(seen.get("last4")),
            seen.get("visa_type"),
            seen.get("entry_date"),
            booking.arrival_date.isoformat(),
            booking.departure_date.isoformat(),
            _when(arrival, zone),
            _by(arrival, names),
            arrival.external_reference if arrival else "",
            _when(departure, zone),
            _by(departure, names),
            "; ".join(notes),
        )
    ]


async def register_csv(
    session: AsyncSession, context: TenantContext, prop: Property, start: dt.date, end: dt.date
) -> str:
    check_range(start, end)
    marks = await _marks(session, context, prop, start, end)
    if len(marks) > MAX_ROWS * 2:
        raise errors.RegisterTooLargeError
    grouped: dict[tuple[UUID, UUID], dict[str, ForeignGuestReport]] = defaultdict(dict)
    bookings: dict[UUID, Reservation] = {}
    for report, booking in marks:
        grouped[(booking.id, report.guest_id)][report.report_kind] = report
        bookings[booking.id] = booking
    names = await staff_names(session, context, {r.submitted_by or "" for r, _ in marks})
    zone = ZoneInfo(prop.timezone)
    out = io.StringIO()
    out.write(BOM)  # spreadsheets then read the names and "••••" as UTF-8
    writer = csv.writer(out)
    writer.writerow(HEADER)
    for (booking_id, _), steps in grouped.items():
        writer.writerow(_row(bookings[booking_id], steps, names, zone))
    await _record_export(session, context, prop, start, end, len(grouped))
    return out.getvalue()


async def _record_export(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    start: dt.date,
    end: dt.date,
    rows: int,
) -> None:
    """A bulk read of foreign guests' details is in the history, like a photo view."""
    await tenant_audit.record(
        session,
        context,
        "apoa.register_exported",
        property_id=prop.id,
        entity_table="property",
        entity_id=prop.id,
        payload={"from": start.isoformat(), "to": end.isoformat(), "rows": rows},
    )
    await session.commit()
