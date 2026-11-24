"""Posting to a guest's bill: extras, discounts, same-day voids and corrections.

Nothing is ever deleted. Every change runs under the property lock, then the booking's,
and refreshes what the guest owes before it commits.
"""

import datetime as dt
import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Folio, FolioTransaction, Property, Reservation, TransactionCode
from app.schemas.bills import ChargeRequest, CorrectionRequest, DiscountRequest, VoidRequest
from app.services import bill_errors as errors
from app.services import calendar_dates as dates_of
from app.services import tenant_audit
from app.services.bill_balance import extras_total, refresh_balance, room_owed
from app.services.bookings import BookingNotFoundError, get_for_update, lock_property
from app.services.front_desk_errors import NotFoundError
from app.services.stay_status import CONFIRMED, IN_HOUSE
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

ENTITY = "reservation"
OPEN_FOR_CHARGES = (CONFIRMED, IN_HOUSE)
MAX_LINES = 300
CHARGE, ADJUSTMENT, VOID = "charge", "adjustment", "void"
# category: (code, name, kind, department)
CODES: dict[str, tuple[str, str, str, str]] = {
    "extra_bed": ("EXTRA_BED", "Extra bed", "charge", "rooms"),
    "food_drinks": ("FNB", "Food & drinks", "charge", "fnb"),
    "laundry": ("LAUNDRY", "Laundry", "charge", "other"),
    "transport": ("TRANSPORT", "Transport", "charge", "other"),
    "minibar": ("MINIBAR", "Minibar", "charge", "fnb"),
    "late_checkout": ("LATE_CHECKOUT", "Late check-out", "charge", "rooms"),
    "other": ("OTHER", "Other", "charge", "other"),
    "discount": ("DISCOUNT", "Discount", "adjustment", "other"),
    "correction": ("CORRECTION", "Correction", "adjustment", "other"),
}
CATEGORY_OF_CODE = {code: category for category, (code, *_rest) in CODES.items()}


async def _find_codes(
    session: AsyncSession, context: TenantContext, property_id: UUID
) -> dict[str, TransactionCode]:
    rows = await session.exec(
        select(TransactionCode).where(
            col(TransactionCode.tenant_id) == context.tenant_id,
            col(TransactionCode.property_id) == property_id,
            col(TransactionCode.code).in_([code for code, *_ in CODES.values()]),
        )
    )
    return {row.code: row for row in rows.all()}


async def bill_codes(
    session: AsyncSession, context: TenantContext, property_id: UUID
) -> dict[str, TransactionCode]:
    """The property's bill categories, created on first use."""
    by_code = await _find_codes(session, context, property_id)
    missing = [values for values in CODES.values() if values[0] not in by_code]
    if missing:
        await session.exec(
            pg_insert(TransactionCode)
            .values(
                [
                    {
                        "tenant_id": context.tenant_id,
                        "property_id": property_id,
                        "code": code,
                        "name": name,
                        "kind": kind,
                        "department": department,
                    }
                    for code, name, kind, department in missing
                ]
            )
            .on_conflict_do_nothing()
        )
        by_code = await _find_codes(session, context, property_id)
    return {category: by_code[code] for category, (code, *_rest) in CODES.items()}


async def booking_folios(
    session: AsyncSession, context: TenantContext, booking_id: UUID
) -> list[Folio]:
    rows = await session.exec(
        select(Folio)
        .where(col(Folio.tenant_id) == context.tenant_id, col(Folio.reservation_id) == booking_id)
        .order_by(col(Folio.window_no))
    )
    return list(rows.all())


async def guest_folio(session: AsyncSession, context: TenantContext, booking: Reservation) -> Folio:
    """The booking's bill, opened on first use. Call under the booking's lock."""
    existing = await booking_folios(session, context, booking.id)
    if existing:
        return existing[0]
    folio = Folio(
        tenant_id=context.tenant_id,
        property_id=booking.property_id,
        kind="guest",
        reservation_id=booking.id,
        guest_id=booking.booker_guest_id,
        currency=booking.currency,
        created_by=str(context.user_id),
    )
    session.add(folio)
    await session.flush()
    return folio


async def _open(
    session: AsyncSession, context: TenantContext, prop: Property, booking_id: UUID
) -> Reservation:
    await lock_property(session, context, prop.id)
    try:
        booking = await get_for_update(session, context, prop.id, booking_id)
    except BookingNotFoundError:
        raise NotFoundError from None
    if booking.status not in OPEN_FOR_CHARGES:
        raise errors.BillClosedError
    return booking


async def _post(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    booking: Reservation,
    category: str,
    values: dict,
) -> FolioTransaction:
    folio = await guest_folio(session, context, booking)
    count = await session.exec(
        select(func.count()).where(
            col(FolioTransaction.tenant_id) == context.tenant_id,
            col(FolioTransaction.folio_id) == folio.id,
        )
    )
    if count.one() >= MAX_LINES:
        raise errors.TooManyLinesError
    codes = await bill_codes(session, context, prop.id)
    code = codes[category]
    if not code.is_active or not code.allow_manual_post:
        raise errors.CategoryOffError
    line = FolioTransaction(
        tenant_id=context.tenant_id,
        folio_id=folio.id,
        property_id=prop.id,
        business_date=dates_of.property_today(prop.timezone),
        transaction_code_id=code.id,
        currency=booking.currency,
        source="manual",
        posted_by=str(context.user_id),
        **values,
    )
    session.add(line)
    await session.flush()
    return line


async def _finish(
    session: AsyncSession,
    context: TenantContext,
    booking: Reservation,
    event: str,
    payload: dict,
) -> Reservation:
    owed_before = booking.balance_due
    await refresh_balance(session, context.tenant_id, booking)
    payload = {
        **payload,
        "owed_before": str(owed_before + booking.paid_amount),
        "owed_after": str(booking.balance_due + booking.paid_amount),
    }
    booking.updated_by = str(context.user_id)
    await tenant_audit.record(
        session,
        context,
        event,
        property_id=booking.property_id,
        entity_table=ENTITY,
        entity_id=booking.id,
        payload=payload,
    )
    await session.commit()
    await session.refresh(booking)
    log.info("%s booking=%s", event, booking.id)
    return booking


async def _check_not_below_zero(
    session: AsyncSession, context: TenantContext, booking: Reservation, change: Decimal
) -> None:
    owed = room_owed(booking) + await extras_total(session, context.tenant_id, booking.id)
    if owed + change < 0:
        raise errors.DiscountTooLargeError


async def post_charge(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    booking_id: UUID,
    request: ChargeRequest,
) -> Reservation:
    """Add an extra to the bill. Commits."""
    booking = await _open(session, context, prop, booking_id)
    amount = request.unit_price * request.quantity
    await _post(
        session,
        context,
        prop,
        booking,
        request.category,
        {
            "kind": CHARGE,
            "description": request.description,
            "quantity": Decimal(request.quantity),
            "unit_price": request.unit_price,
            "amount": amount,
        },
    )
    payload = {"category": request.category, "amount": str(amount)}
    return await _finish(session, context, booking, "bill.charge_posted", payload)


async def give_discount(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    booking_id: UUID,
    request: DiscountRequest,
) -> Reservation:
    """Take money off the bill, with a reason. Commits."""
    booking = await _open(session, context, prop, booking_id)
    await _check_not_below_zero(session, context, booking, -request.amount)
    values = {"kind": ADJUSTMENT, "description": request.reason, "amount": -request.amount}
    await _post(session, context, prop, booking, "discount", values)
    payload = {"amount": str(-request.amount), "reason": request.reason}
    return await _finish(session, context, booking, "bill.discount_given", payload)


async def correct(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    booking_id: UUID,
    request: CorrectionRequest,
) -> Reservation:
    """Fix an earlier day's mistake with a signed amount and a reason. Commits."""
    if request.amount == 0:
        raise errors.ZeroCorrectionError
    booking = await _open(session, context, prop, booking_id)
    await _check_not_below_zero(session, context, booking, request.amount)
    values = {"kind": ADJUSTMENT, "description": request.reason, "amount": request.amount}
    await _post(session, context, prop, booking, "correction", values)
    payload = {"amount": str(request.amount), "reason": request.reason}
    return await _finish(session, context, booking, "bill.corrected", payload)


async def _line_to_void(
    session: AsyncSession, context: TenantContext, booking: Reservation, line_id: UUID
) -> FolioTransaction:
    folio_ids = [folio.id for folio in await booking_folios(session, context, booking.id)]
    line = (
        await session.exec(
            select(FolioTransaction)
            .where(
                col(FolioTransaction.tenant_id) == context.tenant_id,
                col(FolioTransaction.id) == line_id,
                col(FolioTransaction.folio_id).in_(folio_ids),
            )
            .with_for_update()
        )
    ).first()
    if line is None:
        raise NotFoundError
    if line.kind not in (CHARGE, ADJUSTMENT):
        raise errors.NotVoidableError
    voided = await session.exec(
        select(func.count()).where(
            col(FolioTransaction.tenant_id) == context.tenant_id,
            col(FolioTransaction.folio_id) == line.folio_id,
            col(FolioTransaction.reverses_transaction_id) == line.id,
        )
    )
    if voided.one():
        raise errors.AlreadyVoidedError
    return line


async def void_line(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    booking_id: UUID,
    line_id: UUID,
    request: VoidRequest,
) -> Reservation:
    """Cancel one of today's lines with a reverse line. Commits."""
    booking = await _open(session, context, prop, booking_id)
    line = await _line_to_void(session, context, booking, line_id)
    if line.business_date != dates_of.property_today(prop.timezone):
        raise errors.VoidTooLateError
    await _check_not_below_zero(session, context, booking, -line.amount)
    session.add(
        FolioTransaction(
            tenant_id=context.tenant_id,
            folio_id=line.folio_id,
            property_id=line.property_id,
            business_date=line.business_date,
            posted_at=dt.datetime.now(dt.UTC),
            transaction_code_id=line.transaction_code_id,
            kind=VOID,
            description=request.reason,
            amount=-line.amount,
            currency=line.currency,
            reverses_transaction_id=line.id,
            source="manual",
            posted_by=str(context.user_id),
        )
    )
    payload = {"line": str(line.id), "amount": str(-line.amount), "reason": request.reason}
    return await _finish(session, context, booking, "bill.line_voided", payload)
