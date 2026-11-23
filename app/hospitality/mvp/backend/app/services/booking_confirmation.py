"""The WhatsApp confirmation of a paid direct booking.

Sent by the background loop, never inside the payment transaction, so a messaging fault
cannot undo a booking. The message is stored first and appears in the inbox. Failures
retry with backoff and end as "failed", which staff see. A send interrupted midway is
not repeated, because the guest may already have it.
"""

import datetime as dt
import logging
from uuid import UUID

from sqlalchemy import text
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.messaging.provider import SendResult, get_provider
from app.models.tenant import (
    Guest,
    GuestBookingLink,
    Message,
    MessagingAccount,
    Property,
    Reservation,
)
from app.services import booking_tokens as tokens
from app.services.bookings import CONFIRMED
from app.services.inbound import _find_or_create_conversation, next_message_time
from app.services.messaging_accounts import get_or_create_whatsapp_account
from app.services.payment_links import format_rupiah
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

TEMPLATE = "booking_confirmation"
MAX_ATTEMPTS = 5
BASE_BACKOFF_SECONDS = 30
STUCK_AFTER = dt.timedelta(minutes=10)
BATCH = 50
PENDING, SENDING, SENT, FAILED = "pending", "sending", "sent", "failed"
_STATE = "(source_detail -> 'confirmation' ->> 'status')"
# literal SQL, so the planner can use the partial index ix_reservation_confirmation
_AWAITING = text(f"{_STATE} IN ('pending', 'sending')")
_IS_PENDING = text(f"{_STATE} = 'pending'")
_IS_SENDING = text(f"{_STATE} = 'sending'")


def _day(value: dt.date) -> str:
    return value.strftime("%d/%m/%Y")


def confirmation_params(booking: Reservation, prop: Property, url: str) -> dict[str, str]:
    return {
        "property": prop.name,
        "number": booking.confirmation_no,
        "arrival": _day(booking.arrival_date),
        "departure": _day(booking.departure_date),
        "paid": format_rupiah(booking.paid_amount),
        "balance": format_rupiah(booking.balance_due),
        "link": url,
    }


def confirmation_text(params: dict[str, str], language: str | None) -> str:
    if language == "en":
        return (
            f"Your booking at {params['property']} is confirmed.\n"
            f"Booking number: {params['number']}\n"
            f"Stay: {params['arrival']} to {params['departure']}\n"
            f"Paid: {params['paid']}\nBalance due: {params['balance']}\n"
            f"View or cancel: {params['link']}"
        )
    return (
        f"Pemesanan Anda di {params['property']} sudah dikonfirmasi.\n"
        f"Nomor pemesanan: {params['number']}\n"
        f"Menginap: {params['arrival']} sampai {params['departure']}\n"
        f"Sudah dibayar: {params['paid']}\nSisa pembayaran: {params['balance']}\n"
        f"Lihat atau batalkan: {params['link']}"
    )


def _set_state(booking: Reservation, **changes: object) -> None:
    current = (booking.source_detail or {}).get("confirmation") or {}
    booking.source_detail = {
        **(booking.source_detail or {}),
        "confirmation": {**current, **changes},
    }


async def _claim(
    session: AsyncSession, context: TenantContext, booking_id: UUID
) -> tuple[Message, MessagingAccount, str, dict[str, str], str | None] | None:
    """Store the message and mark the send as started. Commits."""
    booking = (
        await session.exec(
            select(Reservation)
            .where(
                col(Reservation.tenant_id) == context.tenant_id,
                col(Reservation.id) == booking_id,
                col(Reservation.status) == CONFIRMED,
            )
            .with_for_update(skip_locked=True)
            .execution_options(populate_existing=True)
        )
    ).first()
    state = ((booking.source_detail or {}).get("confirmation") or {}) if booking else {}
    if booking is None or state.get("status") != PENDING:
        await session.commit()
        return None
    guest = await session.get(Guest, booking.booker_guest_id) if booking.booker_guest_id else None
    phone = guest.whatsapp_phone if guest else None
    if guest is None or not phone:
        _set_state(booking, status=FAILED, error="no_phone")
        session.add(booking)
        await session.commit()
        return None
    prop = (
        await session.exec(
            select(Property).where(
                col(Property.tenant_id) == context.tenant_id,
                col(Property.id) == booking.property_id,
            )
        )
    ).one()
    seed = (
        await session.exec(
            select(col(GuestBookingLink.token_seed)).where(
                col(GuestBookingLink.tenant_id) == context.tenant_id,
                col(GuestBookingLink.reservation_id) == booking.id,
            )
        )
    ).one()
    params = confirmation_params(booking, prop, tokens.guest_url(seed))
    account = await get_or_create_whatsapp_account(session, prop)
    conversation = await _find_or_create_conversation(session, account, guest, phone)
    at = next_message_time(conversation.last_message_at)
    message = Message(
        tenant_id=context.tenant_id,
        conversation_id=conversation.id,
        direction="outbound",
        sender_kind="system",
        body=confirmation_text(params, booking.language),
        status="queued",
        created_at=at,
    )
    session.add(message)
    conversation.last_message_at = at
    session.add(conversation)
    await session.flush()
    _set_state(
        booking,
        status=SENDING,
        attempts=int(state.get("attempts", 0)) + 1,
        message_id=str(message.id),
        started_at=dt.datetime.now(dt.UTC).isoformat(),
    )
    session.add(booking)
    language = booking.language
    await session.commit()
    return message, account, phone, params, language


async def _deliver(
    account: MessagingAccount, phone: str, params: dict[str, str], language: str | None
) -> SendResult:
    try:
        return await get_provider(account.provider).send_template(
            sender=account.sender_identity,
            recipient=phone,
            template=TEMPLATE,
            language=language or "id",
            params=params,
        )
    except Exception:  # noqa: BLE001 — a provider fault must not lose the booking state
        log.exception("Confirmation send failed for account=%s", account.id)
        return SendResult(accepted=False, error="provider_failure")


async def _record(
    session: AsyncSession,
    context: TenantContext,
    booking_id: UUID,
    message: Message,
    result: SendResult,
) -> None:
    booking = (
        await session.exec(
            select(Reservation)
            .where(
                col(Reservation.tenant_id) == context.tenant_id, col(Reservation.id) == booking_id
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).one()
    state = (booking.source_detail or {}).get("confirmation") or {}
    attempts = int(state.get("attempts", 1))
    message.status = "sent" if result.accepted else "failed"
    message.provider_message_id = result.provider_message_id
    session.add(message)
    if result.accepted:
        _set_state(booking, status=SENT, error=None)
    elif attempts >= MAX_ATTEMPTS:
        _set_state(booking, status=FAILED, error=result.error)
    else:
        wait = BASE_BACKOFF_SECONDS * 2 ** (attempts - 1)
        retry = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=wait)
        _set_state(booking, status=PENDING, error=result.error, next_at=retry.isoformat())
    session.add(booking)
    await session.commit()


async def _note_failure(session: AsyncSession, context: TenantContext, booking_id: UUID) -> None:
    """An attempt that broke before sending still counts, so it cannot retry forever."""
    booking = (
        await session.exec(
            select(Reservation)
            .where(
                col(Reservation.tenant_id) == context.tenant_id, col(Reservation.id) == booking_id
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).one()
    state = (booking.source_detail or {}).get("confirmation") or {}
    if state.get("status") == PENDING:
        attempts = int(state.get("attempts", 0)) + 1
        wait = BASE_BACKOFF_SECONDS * 2 ** (attempts - 1)
        retry = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=wait)
        status = FAILED if attempts >= MAX_ATTEMPTS else PENDING
        _set_state(
            booking, status=status, attempts=attempts, error="internal", next_at=retry.isoformat()
        )
        session.add(booking)
    await session.commit()


async def _fail_stuck(session: AsyncSession, context: TenantContext) -> None:
    """A send interrupted midway: tell staff instead of risking a second message."""
    rows = (
        await session.exec(
            select(Reservation)
            .where(col(Reservation.tenant_id) == context.tenant_id, _AWAITING, _IS_SENDING)
            .with_for_update(skip_locked=True)
            .limit(BATCH)
        )
    ).all()
    now = dt.datetime.now(dt.UTC)
    for booking in rows:
        started = (booking.source_detail.get("confirmation") or {}).get("started_at")
        if started and now - dt.datetime.fromisoformat(started) >= STUCK_AFTER:
            _set_state(booking, status=FAILED, error="interrupted")
            session.add(booking)
    await session.commit()


async def send_pending(session: AsyncSession, context: TenantContext) -> int:
    """Send every confirmation that is due. Returns how many were accepted."""
    await _fail_stuck(session, context)
    rows = (
        await session.exec(
            select(col(Reservation.id), col(Reservation.source_detail))
            .where(
                col(Reservation.tenant_id) == context.tenant_id,
                col(Reservation.status) == CONFIRMED,
                _AWAITING,
                _IS_PENDING,
            )
            .limit(BATCH)
        )
    ).all()
    await session.commit()
    now = dt.datetime.now(dt.UTC)
    sent = 0
    for booking_id, detail in rows:
        next_at = (detail.get("confirmation") or {}).get("next_at")
        if next_at and dt.datetime.fromisoformat(next_at) > now:
            continue
        try:
            claimed = await _claim(session, context, booking_id)
            if claimed is None:
                continue
            message, account, phone, params, language = claimed
            result = await _deliver(account, phone, params, language)
            await _record(session, context, booking_id, message, result)
            sent += int(result.accepted)
        except Exception:  # noqa: BLE001 — one booking must not stop the others
            await session.rollback()
            log.exception("Confirmation failed booking=%s", booking_id)
            await _note_failure(session, context, booking_id)
    return sent
