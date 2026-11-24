"""A guest books on the public page: one transaction, one hold, one payment link.

Everything is decided under the property lock: limits, the price the guest was shown,
the last unit. A retried submission with the same key returns the same booking (BR-BE-02)
and a changed price books nothing until the guest re-confirms it (BR-BE-01).
"""

import datetime as dt
import hashlib
import ipaddress
import json
import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import settings as app_settings
from app.messaging.phone import InvalidPhoneError, normalise_phone
from app.models.tenant import (
    GuestBookingLink,
    IdempotencyRecord,
    PaymentLink,
    Property,
    RatePlan,
    Reservation,
)
from app.payments.tokens import fingerprint
from app.schemas.booking_page import CheckoutRequest, CheckoutResult
from app.services import booking_tokens as tokens
from app.services.bill_taxes import with_tax
from app.services.booking_guests import find_or_create_guest
from app.services.booking_holds import BOOKING_PAGE
from app.services.booking_search import deposit_of, stay_problem
from app.services.booking_sources import direct_web_source
from app.services.booking_stays import Stay, check_stay
from app.services.bookings import TENTATIVE, BookingOrder, book_in_transaction, lock_property
from app.services.calendar_dates import property_today
from app.services.payment_links import SUPPORTED_METHODS, money, pay_url
from app.services.tax_rules import priced, rate_book
from app.tenancy.business_settings import PropertySettings, resolve_property_settings
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

SCOPE = "booking_engine.checkout"
TERMS_VERSION = "2026-11-v1"
IDEMPOTENCY_HOURS = 48


class CheckoutError(Exception):
    """A checkout that cannot go ahead. `code` is translated on the guest's page."""

    def __init__(self, code: str, status: int = 409, **details: object) -> None:
        super().__init__(code)
        self.code = code
        self.status = status
        self.details = details


def visitor_key(address: str | None) -> str | None:
    """A keyed hash: enough to count a visitor's holds, without storing the address.

    IPv6 counts per /64, because one household can rotate through a whole /64.
    """
    if not address:
        return None
    try:
        ip = ipaddress.ip_address(address)
        if isinstance(ip, ipaddress.IPv6Address):
            mapped = ip.ipv4_mapped
            address = str(mapped) if mapped else str(ipaddress.ip_network((ip, 64), strict=False))
    except ValueError:
        pass
    return hashlib.sha256(f"{app_settings.SECRET_KEY}:{address}".encode()).hexdigest()[:32]


def _request_hash(request: CheckoutRequest, phone: str) -> str:
    fields = request.model_dump(mode="json", exclude={"idempotency_key"})
    return hashlib.sha256(
        json.dumps({**fields, "guest_phone": phone}, sort_keys=True).encode()
    ).hexdigest()


async def _result_for(
    session: AsyncSession, context: TenantContext, booking_id: UUID
) -> CheckoutResult:
    booking = (
        await session.exec(
            select(Reservation).where(
                col(Reservation.tenant_id) == context.tenant_id, col(Reservation.id) == booking_id
            )
        )
    ).one()
    link = (
        await session.exec(
            select(PaymentLink).where(
                col(PaymentLink.tenant_id) == context.tenant_id,
                col(PaymentLink.reservation_id) == booking_id,
                col(PaymentLink.origin) == BOOKING_PAGE,
            )
        )
    ).one()
    guest_link = (
        await session.exec(
            select(GuestBookingLink).where(
                col(GuestBookingLink.tenant_id) == context.tenant_id,
                col(GuestBookingLink.reservation_id) == booking_id,
            )
        )
    ).one()
    seed = guest_link.token_seed
    return CheckoutResult(
        number=booking.confirmation_no,
        pay_url=pay_url(tokens.derive(seed, tokens.PAY)),
        booking_path=tokens.guest_path(seed),
        amount_due=money(link.amount),
        total=money(with_tax(booking)),
        hold_expires_at=link.expires_at,
    )


async def _replayed(
    session: AsyncSession, context: TenantContext, key: str, request_hash: str
) -> CheckoutResult | None:
    record = (
        await session.exec(
            select(IdempotencyRecord).where(
                col(IdempotencyRecord.tenant_id) == context.tenant_id,
                col(IdempotencyRecord.scope) == SCOPE,
                col(IdempotencyRecord.key) == key,
            )
        )
    ).first()
    if record is None:
        return None
    if record.expires_at <= dt.datetime.now(dt.UTC):
        await session.delete(record)
        await session.flush()
        return None
    if record.request_hash != request_hash:
        raise CheckoutError("key_reused", 422)
    return await _result_for(session, context, UUID(record.response["reservation_id"]))


async def _count_holds(
    session: AsyncSession, context: TenantContext, property_id: UUID, *conditions: object
) -> int:
    statement = (
        select(func.count())
        .select_from(Reservation)
        .where(
            col(Reservation.tenant_id) == context.tenant_id,
            col(Reservation.property_id) == property_id,
            col(Reservation.status) == TENTATIVE,
            col(Reservation.option_expires_at) > dt.datetime.now(dt.UTC),
            *conditions,
        )
    )
    return int((await session.exec(statement)).one())


async def _check_limits(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    settings: PropertySettings,
    guest_id: UUID,
    visitor: str | None,
) -> None:
    total = await _count_holds(session, context, property_id)
    if total >= settings.direct_max_holds_per_property:
        raise CheckoutError("too_many_holds", 429)
    by_phone = await _count_holds(
        session, context, property_id, col(Reservation.booker_guest_id) == guest_id
    )
    if by_phone >= settings.direct_max_holds_per_phone:
        raise CheckoutError("too_many_holds", 429)
    if visitor:
        mine = col(Reservation.source_detail)["visitor"].astext == visitor
        if await _count_holds(session, context, property_id, mine) >= (
            settings.direct_max_holds_per_visitor
        ):
            raise CheckoutError("too_many_holds", 429)


async def _sold_plan(
    session: AsyncSession, context: TenantContext, property_id: UUID, plan_id: UUID
) -> None:
    plan = (
        await session.exec(
            select(col(RatePlan.id)).where(
                col(RatePlan.tenant_id) == context.tenant_id,
                col(RatePlan.property_id) == property_id,
                col(RatePlan.id) == plan_id,
                col(RatePlan.status) == "active",
                col(RatePlan.is_public).is_(True),
            )
        )
    ).first()
    if plan is None:
        raise CheckoutError("not_for_sale", 422)


def _amount_due(request: CheckoutRequest, total: Decimal, settings: PropertySettings) -> Decimal:
    due = (
        total
        if request.pay_choice == "full"
        else deposit_of(total, settings.direct_deposit_percent)
    )
    if not settings.payment_link_min_amount_idr <= due <= settings.payment_link_max_amount_idr:
        raise CheckoutError("amount_out_of_range", 422)
    return due


async def _create(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    request: CheckoutRequest,
    phone: str,
    visitor: str | None,
    request_hash: str,
) -> UUID:
    settings = resolve_property_settings(prop.settings)
    property_id, currency = prop.id, prop.currency
    if request.arrival < property_today(prop.timezone):
        raise CheckoutError("past_arrival", 422)
    await _sold_plan(session, context, property_id, request.rate_plan_id)
    stay = Stay(
        arrival=request.arrival,
        departure=request.departure,
        room_type_id=request.room_type_id,
        rate_plan_id=request.rate_plan_id,
        units=1,
        adults=request.adults,
        children=request.children,
    )
    checked = await check_stay(session, context, prop, settings, stay)
    problem, required = stay_problem(checked)
    if problem:
        raise CheckoutError(problem, 409, min_stay=required)
    book = await rate_book(session, context.tenant_id, property_id)
    total, _tax = priced(
        book,
        prop.price_display_mode,
        [(night.date, night.amount) for night in checked.nights],
    )
    if total != request.expected_total:
        raise CheckoutError("price_changed", 409, total=str(money(total)))
    due = _amount_due(request, total, settings)
    guest = await find_or_create_guest(session, context.tenant_id, request.guest_name, phone)
    await _check_limits(session, context, property_id, settings, guest.id, visitor)
    now = dt.datetime.now(dt.UTC)
    hold_until = now + dt.timedelta(minutes=settings.direct_hold_minutes)
    source = await direct_web_source(session, context)
    guest_id = guest.id
    booking = await book_in_transaction(
        session,
        context,
        prop,
        BookingOrder(
            stay=stay,
            guest=guest,
            source=source,
            booked_by=BOOKING_PAGE,
            hold_until=hold_until,
            language=request.language,
            source_detail={
                "visitor": visitor,
                "pay_choice": request.pay_choice,
                "booker_name": request.guest_name,
                "terms_version": TERMS_VERSION,
                "terms_accepted_at": now.isoformat(),
            },
        ),
    )
    seed = tokens.new_seed()
    session.add(
        GuestBookingLink(
            tenant_id=context.tenant_id,
            reservation_id=booking.id,
            token_hash=fingerprint(tokens.derive(seed, tokens.GUEST)),
            token_seed=seed,
        )
    )
    session.add(
        PaymentLink(
            tenant_id=context.tenant_id,
            property_id=property_id,
            guest_id=guest_id,
            reservation_id=booking.id,
            origin=BOOKING_PAGE,
            token_hash=fingerprint(tokens.derive(seed, tokens.PAY)),
            amount=due,
            deposit_of_total=total if due < total else None,
            currency=currency,
            description=f"Booking {booking.confirmation_no}",
            allowed_methods=list(SUPPORTED_METHODS),
            expires_at=hold_until,
            status="active",
            created_by=BOOKING_PAGE,
        )
    )
    session.add(
        IdempotencyRecord(
            tenant_id=context.tenant_id,
            scope=SCOPE,
            key=f"{property_id}:{request.idempotency_key}",
            request_hash=request_hash,
            response={"reservation_id": str(booking.id)},
            status_code=201,
            expires_at=now + dt.timedelta(hours=IDEMPOTENCY_HOURS),
        )
    )
    return booking.id


async def checkout(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    request: CheckoutRequest,
    address: str | None,
) -> CheckoutResult:
    """Hold the room and create its payment link, or explain why not. Commits."""
    if not request.accepted_terms:
        raise CheckoutError("terms_required", 422)
    try:
        phone = normalise_phone(request.guest_phone)
    except InvalidPhoneError:
        raise CheckoutError("invalid_phone", 422) from None
    request_hash = _request_hash(request, phone)
    scoped_key = f"{prop.id}:{request.idempotency_key}"
    await lock_property(session, context, prop.id)
    try:
        replay = await _replayed(session, context, scoped_key, request_hash)
        if replay is not None:
            await session.commit()
            return replay
        booking_id = await _create(
            session, context, prop, request, phone, visitor_key(address), request_hash
        )
        await session.flush()
        result = await _result_for(session, context, booking_id)
    except Exception:
        await session.rollback()
        raise
    await session.commit()
    log.info("Direct booking held booking=%s", booking_id)
    return result
