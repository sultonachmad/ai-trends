"""Payment links, staff side: create, send to chat, list, read, cancel.

A link is `active` in the database until it is paid or cancelled; it *reads* as
`expired` once its expiry time has passed (there is no background job), and that is
written back the next time the link is touched. To people the active state is
called "pending".

Every query filters on `tenant_id` and the caller's property explicitly, on top of
row-level security.
"""

import datetime as dt
import logging
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, or_, tuple_
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import frontend_base_url
from app.models.tenant import Conversation, Guest, Payment, PaymentLink, Property
from app.payments.gateway import QRIS, SUPPORTED_METHODS
from app.payments.tokens import fingerprint, new_token
from app.schemas.inbox import GuestSummary
from app.schemas.payment_links import (
    LinkFilter,
    PaymentLinkCreated,
    PaymentLinkCreateRequest,
    PaymentLinkPage,
    PaymentLinkRead,
)
from app.services import inbox
from app.tenancy.business_settings import resolve_property_settings
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 30
MAX_PAGE_SIZE = 50
PAY_PATH = "/pay/"
_CURSOR_SEPARATOR = "|"
_STATE_FOR_PEOPLE = {"active": "pending"}
_CENTS = Decimal("0.01")
NEEDS_REFUND_FLAG = "needs_refund_review"  # on payment.metadata: money that was not applied


class PaymentLinkNotFoundError(LookupError):
    """No such payment link in the caller's property."""


class LinkConversationNotFoundError(LookupError):
    """The conversation to send the link to does not exist in the caller's property."""


class AmountOutOfRangeError(ValueError):
    """The amount is outside the property's allowed range."""

    def __init__(self, minimum: int, maximum: int) -> None:
        super().__init__(f"amount must be between {minimum} and {maximum}")
        self.minimum = minimum
        self.maximum = maximum


class TotalBelowAmountError(ValueError):
    """A down payment cannot be larger than the total it is part of."""


class LinkNotPendingError(Exception):
    """Only a pending link can be cancelled."""

    def __init__(self, state: str) -> None:
        super().__init__(state)
        self.state = state


class InvalidCursorError(ValueError):
    """The paging cursor is malformed."""


def effective_status(link: PaymentLink, now: dt.datetime) -> str:
    """The stored status, except that an `active` link past its expiry is `expired`."""
    if link.status == "active" and link.expires_at <= now:
        return "expired"
    return link.status


def state_for_people(link: PaymentLink, now: dt.datetime) -> str:
    status = effective_status(link, now)
    return _STATE_FOR_PEOPLE.get(status, status)


def pay_url(token: str) -> str:
    return f"{frontend_base_url()}{PAY_PATH}{token}"


def money(amount: Decimal) -> Decimal:
    """Amounts always leave the API with two decimals, however they were entered."""
    return amount.quantize(_CENTS)


def format_rupiah(amount: Decimal | int) -> str:
    """Rp 850.000 — Indonesian thousands separator, no decimals."""
    return "Rp " + f"{int(amount):,}".replace(",", ".")


def chat_message(link: PaymentLink, url: str, timezone_name: str) -> str:
    """The WhatsApp message carrying the link (Bahasa Indonesia, the guest default)."""
    try:
        zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo("UTC")
    until = link.expires_at.astimezone(zone).strftime("%d/%m/%Y %H:%M")
    lines = [link.description or "Pembayaran"]
    if link.deposit_of_total is not None:
        lines.append(
            f"DP {format_rupiah(link.amount)} dari total {format_rupiah(link.deposit_of_total)}"
        )
    else:
        lines.append(f"Jumlah: {format_rupiah(link.amount)}")
    lines.append(f"Bayar di sini: {url}")
    lines.append(f"Berlaku sampai {until}")
    return "\n".join(lines)


def _paid_via(payment: Payment | None) -> str | None:
    if payment is None:
        return None
    if payment.method == QRIS:
        return "QRIS"
    label = payment.method.replace("_", " ").capitalize()
    return f"{label} {payment.method_detail}" if payment.method_detail else label


def to_read(
    link: PaymentLink,
    guest: Guest | None,
    captured: Payment | None,
    now: dt.datetime,
    *,
    needs_refund_review: bool = False,
) -> PaymentLinkRead:
    return PaymentLinkRead(
        id=link.id,
        state=state_for_people(link, now),  # type: ignore[arg-type]
        amount=money(link.amount),
        total_amount=money(link.deposit_of_total) if link.deposit_of_total is not None else None,
        currency=link.currency,
        description=link.description,
        expires_at=link.expires_at,
        paid_at=link.paid_at,
        paid_via=_paid_via(captured),
        created_at=link.created_at,
        guest=(
            GuestSummary(id=guest.id, name=guest.full_name, phone=guest.whatsapp_phone)
            if guest
            else None
        ),
        conversation_id=link.conversation_id,
        sent_to_chat=link.sent_via == "whatsapp",
        needs_refund_review=needs_refund_review,
    )


@dataclass(frozen=True)
class _Related:
    """What a page of links needs besides the links themselves."""

    guests: dict[UUID, Guest]
    paid_by: dict[UUID, Payment]  # the payment that made each paid link paid
    refund_review: frozenset[UUID]  # links holding money that was not applied


async def _related(session: AsyncSession, tenant_id: UUID, links: list[PaymentLink]) -> _Related:
    """Guests and captured payments for a page of links — two queries, not two per row."""
    guest_ids = {link.guest_id for link in links if link.guest_id}
    guests: dict[UUID, Guest] = {}
    if guest_ids:
        rows = await session.exec(
            select(Guest).where(col(Guest.tenant_id) == tenant_id, col(Guest.id).in_(guest_ids))
        )
        guests = {g.id: g for g in rows.all()}
    paid_by: dict[UUID, Payment] = {}
    refund_review: set[UUID] = set()
    if links:
        rows = await session.exec(
            select(Payment)
            .where(
                col(Payment.tenant_id) == tenant_id,
                col(Payment.payment_link_id).in_([link.id for link in links]),
                col(Payment.status) == "captured",
            )
            .order_by(col(Payment.captured_at))
        )
        for payment in rows.all():
            link_id: UUID = payment.payment_link_id  # type: ignore[assignment]
            if (payment.metadata_ or {}).get(NEEDS_REFUND_FLAG):
                refund_review.add(link_id)
            else:
                paid_by.setdefault(link_id, payment)
    return _Related(guests=guests, paid_by=paid_by, refund_review=frozenset(refund_review))


def _read(link: PaymentLink, related: _Related, now: dt.datetime) -> PaymentLinkRead:
    return to_read(
        link,
        related.guests.get(link.guest_id) if link.guest_id else None,
        related.paid_by.get(link.id),
        now,
        needs_refund_review=link.id in related.refund_review,
    )


async def _read_one(session: AsyncSession, link: PaymentLink) -> PaymentLinkRead:
    related = await _related(session, link.tenant_id, [link])
    return _read(link, related, dt.datetime.now(dt.UTC))


def _check_amounts(request: PaymentLinkCreateRequest, prop: Property) -> None:
    settings = resolve_property_settings(prop.settings)
    low, high = settings.payment_link_min_amount_idr, settings.payment_link_max_amount_idr
    if not low <= request.amount <= high:
        raise AmountOutOfRangeError(low, high)
    if request.total_amount is not None and request.total_amount < request.amount:
        raise TotalBelowAmountError


async def _conversation_for_link(
    session: AsyncSession, context: TenantContext, prop: Property, conversation_id: UUID | None
) -> Conversation | None:
    if conversation_id is None:
        return None
    conversation = (
        await session.exec(
            select(Conversation).where(
                col(Conversation.tenant_id) == context.tenant_id,
                col(Conversation.property_id) == prop.id,
                col(Conversation.id) == conversation_id,
            )
        )
    ).first()
    if conversation is None:
        raise LinkConversationNotFoundError
    return conversation


@dataclass(frozen=True)
class _SendOutcome:
    sent: bool
    reason: str | None


async def _send_to_chat(
    session: AsyncSession, context: TenantContext, prop: Property, link: PaymentLink, url: str
) -> _SendOutcome:
    """Send the link into its conversation. A refusal is reported, never raised."""
    try:
        message = await inbox.send_reply(
            session,
            context,
            prop.id,
            link.conversation_id,  # type: ignore[arg-type]
            chat_message(link, url, prop.timezone),
        )
    except inbox.ConversationResolvedError:
        return _SendOutcome(sent=False, reason="resolved")
    except inbox.ReplyWindowClosedError:
        return _SendOutcome(sent=False, reason="window_closed")
    except Exception:  # noqa: BLE001 — the link exists; staff must still get its address
        log.exception("Could not send payment link to chat link=%s", link.id)
        await session.rollback()
        return _SendOutcome(sent=False, reason="send_failed")
    if message.status == "failed":
        return _SendOutcome(sent=False, reason="send_failed")
    return _SendOutcome(sent=True, reason=None)


async def create_link(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    request: PaymentLinkCreateRequest,
) -> PaymentLinkCreated:
    """Create a link and, when it belongs to a conversation, send it there.

    The link is committed before anything is sent, so a link the guest received
    always exists. The returned `url` carries the secret token and is not stored.
    """
    _check_amounts(request, prop)
    conversation = await _conversation_for_link(session, context, prop, request.conversation_id)
    settings = resolve_property_settings(prop.settings)
    hours = request.expires_in_hours or settings.payment_link_expiry_hours
    token = new_token()
    link = PaymentLink(
        tenant_id=context.tenant_id,
        property_id=prop.id,
        conversation_id=conversation.id if conversation else None,
        guest_id=conversation.guest_id if conversation else None,
        token_hash=fingerprint(token),
        amount=request.amount,
        deposit_of_total=request.total_amount,
        currency=prop.currency,
        description=request.description,
        allowed_methods=list(SUPPORTED_METHODS),
        expires_at=dt.datetime.now(dt.UTC) + dt.timedelta(hours=hours),
        status="active",
        created_by=str(context.user_id),
    )
    session.add(link)
    await session.commit()
    log.info("Payment link created link=%s amount=%s", link.id, link.amount)

    url = pay_url(token)
    outcome = _SendOutcome(sent=False, reason=None)
    if conversation is not None:
        outcome = await _send_to_chat(session, context, prop, link, url)
        if outcome.sent:
            link.sent_via = "whatsapp"
            session.add(link)
            await session.commit()
    return PaymentLinkCreated(
        link=await _read_one(session, link),
        url=url,
        sent_to_chat=outcome.sent,
        not_sent_reason=outcome.reason,  # type: ignore[arg-type]
    )


def encode_cursor(link: PaymentLink) -> str:
    return f"{link.created_at.isoformat()}{_CURSOR_SEPARATOR}{link.id}"


def decode_cursor(cursor: str) -> tuple[dt.datetime, UUID]:
    try:
        stamp, identifier = cursor.split(_CURSOR_SEPARATOR, 1)
        moment, link_id = dt.datetime.fromisoformat(stamp), UUID(identifier)
    except ValueError as exc:
        raise InvalidCursorError("invalid cursor") from exc
    if moment.tzinfo is None:
        raise InvalidCursorError("invalid cursor")
    return moment, link_id


def _state_condition(state: LinkFilter, now: dt.datetime) -> object | None:
    """SQL condition for a people-facing state, using the expiry time for pending/expired."""
    status, expires = col(PaymentLink.status), col(PaymentLink.expires_at)
    if state == "pending":
        return and_(status == "active", expires > now)
    if state == "expired":
        return or_(status == "expired", and_(status == "active", expires <= now))
    if state in ("paid", "cancelled"):
        return status == state
    return None


async def list_links(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    state: LinkFilter = "all",
    limit: int = DEFAULT_PAGE_SIZE,
    cursor: str | None = None,
) -> PaymentLinkPage:
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    now = dt.datetime.now(dt.UTC)
    statement = select(PaymentLink).where(
        col(PaymentLink.tenant_id) == context.tenant_id,
        col(PaymentLink.property_id) == property_id,
    )
    condition = _state_condition(state, now)
    if condition is not None:
        statement = statement.where(condition)  # type: ignore[arg-type]
    if cursor:
        statement = statement.where(
            tuple_(col(PaymentLink.created_at), col(PaymentLink.id)) < decode_cursor(cursor)
        )
    statement = statement.order_by(
        col(PaymentLink.created_at).desc(), col(PaymentLink.id).desc()
    ).limit(limit + 1)
    rows = list((await session.exec(statement)).all())
    page, has_more = rows[:limit], len(rows) > limit
    related = await _related(session, context.tenant_id, page)
    return PaymentLinkPage(
        items=[_read(link, related, now) for link in page],
        next_cursor=encode_cursor(page[-1]) if has_more else None,
    )


async def get_link(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    link_id: UUID,
    *,
    lock: bool = False,
) -> PaymentLink:
    statement = select(PaymentLink).where(
        col(PaymentLink.tenant_id) == context.tenant_id,
        col(PaymentLink.property_id) == property_id,
        col(PaymentLink.id) == link_id,
    )
    if lock:
        statement = statement.with_for_update()
    link = (await session.exec(statement)).first()
    if link is None:
        raise PaymentLinkNotFoundError
    return link


async def read_link(
    session: AsyncSession, context: TenantContext, property_id: UUID, link_id: UUID
) -> PaymentLinkRead:
    return await _read_one(session, await get_link(session, context, property_id, link_id))


async def cancel_pending_payments(session: AsyncSession, link: PaymentLink) -> None:
    """Mark the link's unpaid payment attempts cancelled (caller commits)."""
    rows = await session.exec(
        select(Payment).where(
            col(Payment.tenant_id) == link.tenant_id,
            col(Payment.payment_link_id) == link.id,
            col(Payment.status) == "pending",
        )
    )
    for payment in rows.all():
        payment.status = "cancelled"
        session.add(payment)


async def cancel_link(
    session: AsyncSession, context: TenantContext, property_id: UUID, link_id: UUID
) -> PaymentLinkRead:
    """Cancel a pending link. An expired link is recorded as expired; neither can be paid."""
    link = await get_link(session, context, property_id, link_id, lock=True)
    status = effective_status(link, dt.datetime.now(dt.UTC))
    if status != "active":
        if status == "expired" and link.status == "active":
            link.status = "expired"  # write the lapse back while we hold the row
            session.add(link)
            await cancel_pending_payments(session, link)
            await session.commit()
        else:
            await session.rollback()
        raise LinkNotPendingError(_STATE_FOR_PEOPLE.get(status, status))
    link.status = "cancelled"
    link.updated_by = str(context.user_id)
    session.add(link)
    await cancel_pending_payments(session, link)
    await session.commit()
    log.info("Payment link cancelled link=%s", link.id)
    return await _read_one(session, link)
