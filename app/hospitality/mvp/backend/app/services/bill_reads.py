"""Reading a guest's bill."""

import datetime as dt
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import (
    FolioTransaction,
    Guest,
    Invoice,
    Property,
    Reservation,
    TransactionCode,
    UnitType,
)
from app.schemas.bills import BillLine, BillRead, ReceiptSummary
from app.services import calendar_dates as dates_of
from app.services.bill_balance import CHANNEL_COLLECTS, ZERO
from app.services.booking_reads import _by_id, _nightly, payment_entries
from app.services.bookings import balance_to_collect, lines_of
from app.services.front_desk_errors import NotFoundError
from app.services.stay_status import CONFIRMED, IN_HOUSE, LEFT_UNPAID
from app.tenancy.context import TenantContext

VOID = "void"


async def bill_entries(
    session: AsyncSession,
    context: TenantContext,
    folio_ids: list[UUID],
    today: dt.date | None = None,
) -> list[BillLine]:
    """The bill's own lines in order; void lines show as a mark on what they cancel."""
    from app.services.bills import CATEGORY_OF_CODE

    if not folio_ids:
        return []
    rows = (
        await session.exec(
            select(FolioTransaction)
            .where(
                col(FolioTransaction.tenant_id) == context.tenant_id,
                col(FolioTransaction.folio_id).in_(folio_ids),
            )
            .order_by(col(FolioTransaction.posted_at), col(FolioTransaction.id))
        )
    ).all()
    codes = await _by_id(session, context, TransactionCode, {r.transaction_code_id for r in rows})
    voids = {r.reverses_transaction_id: r for r in rows if r.kind == VOID}
    return [
        BillLine(
            id=row.id,
            category=CATEGORY_OF_CODE.get(codes[row.transaction_code_id].code, "other"),
            description=row.description,
            quantity=row.quantity,
            unit_price=row.unit_price,
            amount=row.amount,
            business_date=row.business_date,
            posted_at=row.posted_at,
            voided=row.id in voids,
            void_reason=voids[row.id].description if row.id in voids else None,
            can_void=today is not None and row.id not in voids and row.business_date == today,
        )
        for row in rows
        if row.kind != VOID
    ]


async def _booking(
    session: AsyncSession, context: TenantContext, prop: Property, booking_id: UUID
) -> Reservation:
    booking = (
        await session.exec(
            select(Reservation).where(
                col(Reservation.tenant_id) == context.tenant_id,
                col(Reservation.property_id) == prop.id,
                col(Reservation.id) == booking_id,
            )
        )
    ).first()
    if booking is None:
        raise NotFoundError
    return booking


async def read_bill(
    session: AsyncSession, context: TenantContext, prop: Property, booking_id: UUID
) -> BillRead:
    from app.services.bills import booking_folios

    booking = await _booking(session, context, prop, booking_id)
    today = dates_of.property_today(prop.timezone)
    is_open = booking.status in (CONFIRMED, IN_HOUSE)
    folio_ids = [folio.id for folio in await booking_folios(session, context, booking.id)]
    lines = await bill_entries(session, context, folio_ids, today if is_open else None)
    stay_lines = await lines_of(session, context, [booking.id])
    room = await session.get(UnitType, stay_lines[0].unit_type_id) if stay_lines else None
    guest = await session.get(Guest, booking.booker_guest_id) if booking.booker_guest_id else None
    receipts = (
        (
            await session.exec(
                select(Invoice)
                .where(
                    col(Invoice.tenant_id) == context.tenant_id,
                    col(Invoice.folio_id).in_(folio_ids),
                    col(Invoice.kind) == "receipt",
                )
                .order_by(col(Invoice.issued_at))
            )
        ).all()
        if folio_ids
        else []
    )
    payments = await payment_entries(session, context, prop, booking.id)
    return BillRead(
        booking_id=booking.id,
        number=booking.confirmation_no,
        status=booking.status,
        guest_name=guest.full_name if guest else "",
        arrival=booking.arrival_date,
        departure=booking.departure_date,
        closed=not is_open,
        paid_to_channel=booking.payment_collect_model == CHANNEL_COLLECTS,
        left_unpaid=bool(booking.source_detail.get(LEFT_UNPAID)),
        room_type=room.name if room else "",
        room_nights=[
            {"date": night.date, "amount": night.amount}
            for night in await _nightly(session, context, booking.id)
        ],
        room_total=booking.total_amount,
        lines=lines,
        extras_total=sum((line.amount for line in lines if not line.voided), ZERO),
        payments=payments,
        paid=booking.paid_amount,
        balance=balance_to_collect(booking),
        receipts=[
            ReceiptSummary(
                id=r.id,
                number=r.number or "",
                issued_at=r.issued_at,
                total=r.total,
                replaced=index < len(receipts) - 1,
            )
            for index, r in enumerate(receipts)
        ],
    )
