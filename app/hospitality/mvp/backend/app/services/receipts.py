"""Numbered receipts, issued at check-out and never changed afterwards."""

import datetime as dt
import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import (
    DocumentSequence,
    Guest,
    Invoice,
    InvoiceLine,
    LegalEntity,
    Property,
    Reservation,
    UnitType,
)
from app.schemas.bills import ReceiptLine, ReceiptRead
from app.services import calendar_dates as dates_of
from app.services import tenant_audit
from app.services.bill_balance import CHANNEL_COLLECTS, room_owed
from app.services.bill_reads import bill_entries
from app.services.bill_taxes import bill_tax
from app.services.bills import guest_folio
from app.services.bookings import lines_of
from app.services.front_desk_errors import NotFoundError
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

RECEIPT = "receipt"
PREFIX = "KW"
PADDING = 6


async def _next_number(
    session: AsyncSession, context: TenantContext, legal_entity_id: UUID, year: int
) -> str:
    """The next receipt number of the year, taken under the sequence's row lock."""
    period = str(year)
    await session.exec(
        pg_insert(DocumentSequence)
        .values(
            tenant_id=context.tenant_id,
            legal_entity_id=legal_entity_id,
            series=RECEIPT,
            period_key=period,
            prefix=f"{PREFIX}-{period}-",
            next_number=1,
            padding=PADDING,
        )
        .on_conflict_do_nothing()
    )
    sequence = (
        await session.exec(
            select(DocumentSequence)
            .where(
                col(DocumentSequence.tenant_id) == context.tenant_id,
                col(DocumentSequence.legal_entity_id) == legal_entity_id,
                col(DocumentSequence.series) == RECEIPT,
                col(DocumentSequence.period_key) == period,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).one()
    number = f"{sequence.prefix}{sequence.next_number:0{sequence.padding}d}"
    sequence.next_number += 1
    sequence.updated_at = dt.datetime.now(dt.UTC)
    session.add(sequence)
    return number


async def _room_line(
    session: AsyncSession, context: TenantContext, booking: Reservation
) -> InvoiceLine:
    lines = await lines_of(session, context, [booking.id])
    room = await session.get(UnitType, lines[0].unit_type_id) if lines else None
    nights = max((booking.departure_date - booking.arrival_date).days, 1) * max(len(lines), 1)
    amount = room_owed(booking)
    return InvoiceLine(
        tenant_id=context.tenant_id,
        line_no=1,
        description=room.name if room else "",
        quantity=Decimal(nights),
        unit_price=(amount / nights).quantize(Decimal("0.01")),
        amount=amount,
    )


async def issue_receipt(
    session: AsyncSession, context: TenantContext, prop: Property, booking: Reservation
) -> Invoice:
    """Freeze the bill into a numbered receipt. Does not commit."""
    today = dates_of.property_today(prop.timezone)
    folio = await guest_folio(session, context, booking)
    guest = await session.get(Guest, booking.booker_guest_id) if booking.booker_guest_id else None
    extras = [line for line in await bill_entries(session, context, [folio.id]) if not line.voided]
    room_line = await _room_line(session, context, booking)
    taxes = await bill_tax(session, context.tenant_id, booking)
    room_tax = sum(
        (i.parts.service + i.parts.pbjt for i in taxes.items if i.key.startswith("room:")),
        Decimal(0),
    )
    room_line.tax_amount = room_tax
    line_tax = {i.key: i.parts.service + i.parts.pbjt for i in taxes.items}
    subtotal = room_line.amount + sum((line.amount for line in extras), Decimal(0))
    total = subtotal + taxes.added
    receipt = Invoice(
        tenant_id=context.tenant_id,
        legal_entity_id=prop.legal_entity_id,
        property_id=prop.id,
        folio_id=folio.id,
        kind=RECEIPT,
        series=RECEIPT,
        number=await _next_number(session, context, prop.legal_entity_id, today.year),
        status="issued",
        business_date=today,
        issued_at=dt.datetime.now(dt.UTC),
        guest_id=booking.booker_guest_id,
        bill_to={
            "guest_name": guest.full_name if guest else "",
            "booking_number": booking.confirmation_no,
            "arrival": booking.arrival_date.isoformat(),
            "departure": booking.departure_date.isoformat(),
            "property_name": prop.name,
            "paid_to_channel": booking.payment_collect_model == CHANNEL_COLLECTS,
            "price_mode": taxes.mode,
            "service": str(taxes.service),
            "pbjt": str(taxes.pbjt),
        },
        currency=booking.currency,
        subtotal=subtotal,
        tax_total=taxes.service + taxes.pbjt,  # inside the prices when nett, on top when ++
        total=total,
        paid_amount=booking.paid_amount,
        created_by=str(context.user_id),
    )
    session.add(receipt)
    await session.flush()
    room_line.invoice_id = receipt.id
    rows = [room_line] + [
        InvoiceLine(
            tenant_id=context.tenant_id,
            invoice_id=receipt.id,
            line_no=index,
            folio_transaction_id=line.id,
            description=line.description,
            quantity=line.quantity,
            unit_price=line.unit_price if line.unit_price is not None else line.amount,
            amount=line.amount,
            tax_amount=line_tax.get(str(line.id), Decimal(0)),
        )
        for index, line in enumerate(extras, start=2)
    ]
    session.add_all(rows)
    await tenant_audit.record(
        session,
        context,
        "receipt.issued",
        property_id=prop.id,
        entity_table="invoice",
        entity_id=receipt.id,
        payload={
            "number": receipt.number,
            "total": str(total),
            "tax": str(taxes.service + taxes.pbjt),
        },
    )
    log.info("Receipt issued booking=%s number=%s", booking.id, receipt.number)
    return receipt


async def read_receipt(
    session: AsyncSession, context: TenantContext, prop: Property, receipt_id: UUID
) -> ReceiptRead:
    receipt = (
        await session.exec(
            select(Invoice).where(
                col(Invoice.tenant_id) == context.tenant_id,
                col(Invoice.property_id) == prop.id,
                col(Invoice.id) == receipt_id,
                col(Invoice.kind) == RECEIPT,
            )
        )
    ).first()
    if receipt is None:
        raise NotFoundError
    lines = (
        await session.exec(
            select(InvoiceLine)
            .where(
                col(InvoiceLine.tenant_id) == context.tenant_id,
                col(InvoiceLine.invoice_id) == receipt.id,
            )
            .order_by(col(InvoiceLine.line_no))
        )
    ).all()
    issuer = await session.get(LegalEntity, receipt.legal_entity_id)
    snapshot = receipt.bill_to or {}
    return ReceiptRead(
        id=receipt.id,
        number=receipt.number or "",
        issued_at=receipt.issued_at,
        business_date=receipt.business_date,
        issuer_name=issuer.name if issuer else "",
        issuer_tax_id=issuer.tax_id if issuer else None,
        property_name=str(snapshot.get("property_name", "")),
        booking_number=str(snapshot.get("booking_number", "")),
        guest_name=str(snapshot.get("guest_name", "")),
        arrival=dt.date.fromisoformat(snapshot["arrival"]),
        departure=dt.date.fromisoformat(snapshot["departure"]),
        paid_to_channel=bool(snapshot.get("paid_to_channel")),
        lines=[
            ReceiptLine(
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                amount=line.amount,
                is_room=line.folio_transaction_id is None,
            )
            for line in lines
        ],
        taxes_included=snapshot.get("price_mode", "nett") == "nett",
        subtotal=receipt.subtotal,
        service=Decimal(str(snapshot.get("service", "0"))),
        pbjt=Decimal(str(snapshot.get("pbjt", "0"))),
        total=receipt.total,
        paid=receipt.paid_amount,
        balance=receipt.total - receipt.paid_amount,
    )
