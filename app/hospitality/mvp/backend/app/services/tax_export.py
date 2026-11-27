"""The month's tax summary as two spreadsheet files: by day, and by booking.

UTF-8 with a byte-order mark (spreadsheets read it right), cells that could run as a
formula are made text, no guest names. Each regional return format differs, so this is a
general layout for the owner or their accountant to copy from [verify per region].
"""

import csv
import io

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Property
from app.schemas.tax_summary import TaxAmounts, TaxMonth
from app.services import tenant_audit
from app.services.apoa_register import BOM, plain
from app.services.tax_summary import read_month
from app.tenancy.context import TenantContext

AMOUNTS = (
    ("room_nights", "Room nights"),
    ("room_base", "Room revenue (before tax)"),
    ("extras_base", "Taxed extras (before tax)"),
    ("service", "Service charge"),
    ("pbjt", "PBJT"),
    ("untaxed", "Untaxed extras"),
    ("channel_nights", "Channel room nights"),
    ("channel_base", "Channel room revenue (before tax)"),
    ("channel_service", "Channel service charge (inside price)"),
    ("channel_pbjt", "Channel PBJT (inside price)"),
)
NOTES = (
    "Basis: each room night in the month it is stayed, each extra on the day it was posted,"
    " at the tax rate of that date. Check with your regional tax office whether PBJT is due"
    " on stays or on payments received.",
    "Channel columns: bookings paid through a sales channel. Their bills carry no tax because"
    " the channel collected the money. Check with your tax office whether you or the channel"
    " reports them.",
)


def _values(amounts: TaxAmounts) -> list[str]:
    return [plain(getattr(amounts, key)) for key, _ in AMOUNTS]


def _head(writer: csv.writer, prop: Property, month: TaxMonth, title: str) -> None:
    status = "DRAFT - not every day is closed" if month.draft else "FINAL - every day is closed"
    writer.writerow([plain(title)])
    writer.writerow(["Property", plain(prop.name)])
    writer.writerow(["Month", month.month])
    writer.writerow(["Status", status, f"{month.closed_days}/{month.days_in_month} days closed"])
    for note in NOTES:
        writer.writerow(["Note", note])
    writer.writerow([])


def days_csv(prop: Property, month: TaxMonth) -> str:
    out = io.StringIO()
    out.write(BOM)
    writer = csv.writer(out)
    _head(writer, prop, month, "Monthly tax summary by day")
    writer.writerow(["Date", *[label for _, label in AMOUNTS]])
    for day in month.days:
        writer.writerow([day.date.isoformat(), *_values(day)])
    writer.writerow(["Total", *_values(month.totals)])
    return out.getvalue()


def bookings_csv(prop: Property, month: TaxMonth) -> str:
    out = io.StringIO()
    out.write(BOM)
    writer = csv.writer(out)
    _head(writer, prop, month, "Monthly tax summary by booking")
    writer.writerow(
        [
            "Booking",
            "Arrival",
            "Departure",
            "Source",
            "Price mode",
            *[label for _, label in AMOUNTS],
        ]
    )
    for row in month.bookings:
        writer.writerow(
            [
                plain(row.number),
                row.arrival.isoformat(),
                row.departure.isoformat(),
                plain(row.source),
                row.price_mode,
                *_values(row),
            ]
        )
    writer.writerow(["Total", "", "", "", "", *_values(month.totals)])
    return out.getvalue()


async def export(
    session: AsyncSession, context: TenantContext, prop: Property, month: str, kind: str
) -> str:
    """The file, recorded in the history (who, which month, which file). Commits."""
    summary = await read_month(session, context, prop, month)
    content = days_csv(prop, summary) if kind == "days" else bookings_csv(prop, summary)
    await tenant_audit.record(
        session,
        context,
        "tax.exported",
        property_id=prop.id,
        entity_table="property",
        entity_id=prop.id,
        payload={"month": month, "file": kind, "draft": summary.draft},
    )
    await session.commit()
    return content
