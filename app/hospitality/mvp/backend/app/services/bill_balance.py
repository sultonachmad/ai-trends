"""What a guest owes the property: one rule for every page and every writer.

Room nights count unless the channel was paid for them; extras, discounts, voids and
corrections on the bill count; service charge and PBJT count when prices are "++";
money received counts against it.
"""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Folio, FolioTransaction, Reservation

CHANNEL_COLLECTS = "channel"  # the guest paid the channel for the room
BILL_KINDS = ("charge", "adjustment", "void")  # lines that change what is owed
ZERO = Decimal("0")


def room_owed(booking: Reservation) -> Decimal:
    """The room part the guest pays the property."""
    return ZERO if booking.payment_collect_model == CHANNEL_COLLECTS else booking.total_amount


async def extras_total(session: AsyncSession, tenant_id: UUID, booking_id: UUID) -> Decimal:
    """Extras, discounts, voids and corrections on the booking's bill."""
    total = await session.exec(
        select(func.coalesce(func.sum(FolioTransaction.amount), 0))
        .join(
            Folio,
            (col(Folio.tenant_id) == col(FolioTransaction.tenant_id))
            & (col(Folio.id) == col(FolioTransaction.folio_id)),
        )
        .where(
            col(FolioTransaction.tenant_id) == tenant_id,
            col(Folio.reservation_id) == booking_id,
            col(FolioTransaction.kind).in_(BILL_KINDS),
        )
    )
    return Decimal(total.one())


async def refresh_balance(session: AsyncSession, tenant_id: UUID, booking: Reservation) -> None:
    """Set `balance_due` from the room, the bill and the money received. Does not commit."""
    from app.services.bill_taxes import bill_tax

    await session.flush()
    extras = await extras_total(session, tenant_id, booking.id)
    taxes = await bill_tax(session, tenant_id, booking)
    booking.total_tax = taxes.room_tax  # the room's own service and PBJT
    booking.balance_due = room_owed(booking) + extras + taxes.added - booking.paid_amount
    session.add(booking)
