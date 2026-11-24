"""Service charge and PBJT on one booking's bill, night by night and line by line.

Each booking keeps the price mode it was made under (`source_detail.price_mode`); channel
bookings are always nett, because the channel's amount is what the guest paid.
"""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import (
    Folio,
    FolioTransaction,
    Reservation,
    ReservationDailyRate,
    ReservationUnit,
    TransactionCode,
)
from app.services.bills import CATEGORY_OF_CODE
from app.services.tax_engine import NETT, PLUS_PLUS, TaxSplit, split
from app.services.tax_rules import RateBook, rate_book

PRICE_MODE = "price_mode"
ZERO = Decimal("0")
CHANNEL_COLLECTS = "channel"


def mode_of(booking: Reservation) -> str:
    return str((booking.source_detail or {}).get(PRICE_MODE) or NETT)


@dataclass(frozen=True)
class TaxedItem:
    key: str  # "room:<date>" or the bill line id
    day: dt.date
    parts: TaxSplit


@dataclass(frozen=True)
class BillTax:
    mode: str
    items: tuple[TaxedItem, ...]
    is_set: bool = True  # the owner has confirmed tax rates

    @property
    def room_tax(self) -> Decimal:
        return sum(
            (i.parts.service + i.parts.pbjt for i in self.items if i.key.startswith("room:")),
            ZERO,
        )

    @property
    def service(self) -> Decimal:
        return sum((item.parts.service for item in self.items), ZERO)

    @property
    def pbjt(self) -> Decimal:
        return sum((item.parts.pbjt for item in self.items), ZERO)

    @property
    def added(self) -> Decimal:
        """What the taxes add to what is owed: everything in ++, nothing in nett."""
        return self.service + self.pbjt if self.mode == PLUS_PLUS else ZERO


async def _room_nights(
    session: AsyncSession, tenant_id: UUID, booking_id: UUID
) -> list[tuple[dt.date, Decimal]]:
    rows = await session.exec(
        select(col(ReservationDailyRate.stay_date), func.sum(col(ReservationDailyRate.amount)))
        .join(
            ReservationUnit,
            (col(ReservationUnit.tenant_id) == col(ReservationDailyRate.tenant_id))
            & (col(ReservationUnit.id) == col(ReservationDailyRate.reservation_unit_id)),
        )
        .where(
            col(ReservationDailyRate.tenant_id) == tenant_id,
            col(ReservationUnit.reservation_id) == booking_id,
        )
        .group_by(col(ReservationDailyRate.stay_date))
    )
    return [(night, Decimal(amount)) for night, amount in rows.all()]


async def _bill_lines(
    session: AsyncSession, tenant_id: UUID, booking_id: UUID
) -> list[tuple[str, dt.date, str, Decimal]]:
    """(id, business date, category, amount) of the bill lines still standing."""
    rows = (
        await session.exec(
            select(FolioTransaction, col(TransactionCode.code))
            .join(
                Folio,
                (col(Folio.tenant_id) == col(FolioTransaction.tenant_id))
                & (col(Folio.id) == col(FolioTransaction.folio_id)),
            )
            .join(
                TransactionCode,
                (col(TransactionCode.tenant_id) == col(FolioTransaction.tenant_id))
                & (col(TransactionCode.id) == col(FolioTransaction.transaction_code_id)),
            )
            .where(
                col(FolioTransaction.tenant_id) == tenant_id,
                col(Folio.reservation_id) == booking_id,
                col(FolioTransaction.kind).in_(("charge", "adjustment", "void")),
            )
        )
    ).all()
    voided = {line.reverses_transaction_id for line, _ in rows if line.kind == "void"}
    return [
        (str(line.id), line.business_date, CATEGORY_OF_CODE.get(code, "other"), line.amount)
        for line, code in rows
        if line.kind != "void" and line.id not in voided
    ]


def _taxed(book: RateBook, mode: str, key: str, day: dt.date, amount: Decimal) -> TaxedItem:
    return TaxedItem(key=key, day=day, parts=split(amount, book.rates_on(day), mode))


async def bill_tax(session: AsyncSession, tenant_id: UUID, booking: Reservation) -> BillTax:
    """The booking's service charge and PBJT, by the rule of each night's or line's date."""
    mode = mode_of(booking)
    book = await rate_book(session, tenant_id, booking.property_id)
    if not book.is_set:
        return BillTax(mode=mode, items=(), is_set=False)
    items: list[TaxedItem] = []
    if booking.payment_collect_model != CHANNEL_COLLECTS:
        for night, amount in await _room_nights(session, tenant_id, booking.id):
            items.append(_taxed(book, mode, f"room:{night.isoformat()}", night, amount))
    for line_id, day, category, amount in await _bill_lines(session, tenant_id, booking.id):
        if category not in book.untaxed_on(day):
            items.append(_taxed(book, mode, line_id, day, amount))
    return BillTax(mode=mode, items=tuple(items))


def with_tax(booking: Reservation) -> Decimal:
    """The room price as the guest pays it: plus service and PBJT when priced "++"."""
    added = booking.total_tax if mode_of(booking) == PLUS_PLUS else ZERO
    return booking.total_amount + added
