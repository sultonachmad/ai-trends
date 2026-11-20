"""Receiving a guest message.

`receive_inbound` is the single entry point for inbound WhatsApp messages: the
simulator calls it today and the real provider webhook will call it later.

Rules
* The guest is matched by WhatsApp number within the tenant, or created.
* One open conversation per number per account; a message arriving after the
  conversation was resolved opens a new one (see index ux_conversation_thread).
* A provider message id is stored once: a repeated delivery changes nothing.
* Each inbound message reopens WhatsApp's 24-hour customer-service window.
* `message.created_at` is the time we stored the message and never goes backwards
  within a conversation (the thread's "newer than" paging relies on that); the
  provider's own timestamp is kept in `sent_at`.
"""

import datetime as dt
import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import Conversation, Guest, Message, MessagingAccount

log = logging.getLogger(__name__)

SERVICE_WINDOW = dt.timedelta(hours=24)
_TICK = dt.timedelta(microseconds=1)
_LOCK_THREAD = text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))")


@dataclass(frozen=True)
class InboundMessage:
    from_phone: str  # canonical form, see app.messaging.phone
    body: str
    provider_message_id: str
    guest_name: str | None = None
    received_at: dt.datetime | None = None  # the provider's timestamp, if it sent one


@dataclass(frozen=True)
class InboundOutcome:
    conversation_id: UUID
    message_id: UUID
    duplicate: bool


def next_message_time(last_message_at: dt.datetime | None) -> dt.datetime:
    """Now, but never at or before the conversation's previous message."""
    now = dt.datetime.now(dt.UTC)
    if last_message_at is not None and now <= last_message_at:
        return last_message_at + _TICK
    return now


async def _find_duplicate(
    session: AsyncSession, tenant_id: UUID, provider_message_id: str
) -> Message | None:
    return (
        await session.exec(
            select(Message).where(
                col(Message.tenant_id) == tenant_id,
                col(Message.provider_message_id) == provider_message_id,
            )
        )
    ).first()


async def _find_or_create_guest(
    session: AsyncSession, tenant_id: UUID, inbound: InboundMessage
) -> Guest:
    guest = (
        await session.exec(
            select(Guest)
            .where(
                col(Guest.tenant_id) == tenant_id,
                col(Guest.whatsapp_phone) == inbound.from_phone,
                col(Guest.merged_into_guest_id).is_(None),
            )
            .order_by(col(Guest.created_at))
            .limit(1)
        )
    ).first()
    if guest is not None:
        return guest
    guest = Guest(
        tenant_id=tenant_id,
        full_name=inbound.guest_name or inbound.from_phone,
        phone=inbound.from_phone,
        whatsapp_phone=inbound.from_phone,
    )
    session.add(guest)
    await session.flush()
    return guest


async def _find_or_create_conversation(
    session: AsyncSession, account: MessagingAccount, guest: Guest, phone: str
) -> Conversation:
    conversation = (
        await session.exec(
            select(Conversation)
            .where(
                col(Conversation.tenant_id) == account.tenant_id,
                col(Conversation.messaging_account_id) == account.id,
                col(Conversation.external_thread_id) == phone,
                col(Conversation.status) != "resolved",
            )
            # Wait for a reply / mark-read in progress, then read the fresh row.
            .with_for_update()
        )
    ).first()
    if conversation is not None:
        return conversation
    conversation = Conversation(
        tenant_id=account.tenant_id,
        property_id=account.property_id,
        messaging_account_id=account.id,
        channel_kind=account.channel_kind,
        external_thread_id=phone,
        guest_id=guest.id,
        status="open",
    )
    session.add(conversation)
    await session.flush()
    return conversation


async def receive_inbound(
    session: AsyncSession, account: MessagingAccount, inbound: InboundMessage
) -> InboundOutcome:
    """Store one inbound message. Commits; safe to call again with the same id."""
    tenant_id = account.tenant_id
    # Serialise messages of one thread so two first messages cannot open two conversations.
    await session.execute(_LOCK_THREAD, {"key": f"{account.id}:{inbound.from_phone}"})

    existing = await _find_duplicate(session, tenant_id, inbound.provider_message_id)
    if existing is not None:
        await session.commit()
        return InboundOutcome(existing.conversation_id, existing.id, duplicate=True)

    guest = await _find_or_create_guest(session, tenant_id, inbound)
    conversation = await _find_or_create_conversation(session, account, guest, inbound.from_phone)
    stored_at = next_message_time(conversation.last_message_at)  # after the row lock
    message = Message(
        tenant_id=tenant_id,
        conversation_id=conversation.id,
        direction="inbound",
        sender_kind="guest",
        body=inbound.body,
        provider_message_id=inbound.provider_message_id,
        status="received",
        sent_at=inbound.received_at,
        created_at=stored_at,
    )
    session.add(message)
    conversation.unread_count = conversation.unread_count + 1
    conversation.last_message_at = stored_at
    conversation.last_inbound_at = stored_at
    conversation.service_window_expires_at = stored_at + SERVICE_WINDOW
    session.add(conversation)
    try:
        await session.commit()
    except IntegrityError:
        # The same provider id arrived on another thread at the same moment.
        await session.rollback()
        existing = await _find_duplicate(session, tenant_id, inbound.provider_message_id)
        if existing is None:
            raise
        await session.commit()
        return InboundOutcome(existing.conversation_id, existing.id, duplicate=True)
    log.info("Inbound message stored conversation=%s message=%s", conversation.id, message.id)
    return InboundOutcome(conversation.id, message.id, duplicate=False)
