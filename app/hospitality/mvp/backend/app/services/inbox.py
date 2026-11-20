"""Inbox: list conversations, read a thread, reply, mark read, resolve / reopen.

Every query filters on `tenant_id` and the caller's property explicitly, on top of
row-level security.
"""

import datetime as dt
import logging
from uuid import UUID

from sqlalchemy import tuple_
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.messaging.provider import SendResult, get_provider
from app.models.tenant import Conversation, Guest, Message, MessagingAccount, StaffMember
from app.schemas.inbox import (
    PREVIEW_LENGTH,
    ConversationFilter,
    ConversationPage,
    ConversationRead,
    GuestSummary,
    LastMessage,
    MessageRead,
)
from app.services.inbound import next_message_time
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 30
MAX_PAGE_SIZE = 50
MAX_THREAD_MESSAGES = 200
PROVIDER_FAILURE = "The message could not be sent. Please try again."
_CURSOR_SEPARATOR = "|"
_EPOCH = dt.datetime(1970, 1, 1, tzinfo=dt.UTC)


class ConversationNotFoundError(LookupError):
    """No such conversation in the caller's property."""


class ConversationResolvedError(Exception):
    """The conversation is resolved; reopen it before replying."""


class ReplyWindowClosedError(Exception):
    """WhatsApp's 24-hour window has passed; only a template may be sent."""


class ReopenConflictError(Exception):
    """The guest already has another open conversation, so this one cannot be reopened."""


class InvalidCursorError(ValueError):
    """The paging cursor is malformed."""


def reply_block_reason(conversation: Conversation, now: dt.datetime) -> str | None:
    """Why a free-text reply is not allowed right now, or None when it is."""
    if conversation.status == "resolved":
        return "resolved"
    expires = conversation.service_window_expires_at
    if expires is None or expires <= now:
        return "window_closed"
    return None


def _preview(body: str | None) -> str:
    text = " ".join((body or "").split())
    return text if len(text) <= PREVIEW_LENGTH else text[: PREVIEW_LENGTH - 1] + "…"


def encode_cursor(conversation: Conversation) -> str:
    stamp = (conversation.last_message_at or _EPOCH).isoformat()
    return f"{stamp}{_CURSOR_SEPARATOR}{conversation.id}"


def decode_cursor(cursor: str) -> tuple[dt.datetime, UUID]:
    try:
        stamp, identifier = cursor.split(_CURSOR_SEPARATOR, 1)
        moment, conversation_id = dt.datetime.fromisoformat(stamp), UUID(identifier)
    except ValueError as exc:
        raise InvalidCursorError("invalid cursor") from exc
    if moment.tzinfo is None:
        raise InvalidCursorError("invalid cursor")
    return moment, conversation_id


async def _last_messages(
    session: AsyncSession, tenant_id: UUID, conversation_ids: list[UUID]
) -> dict[UUID, Message]:
    """Newest message of each conversation, in one query."""
    if not conversation_ids:
        return {}
    statement = (
        select(Message)
        .where(
            col(Message.tenant_id) == tenant_id,
            col(Message.conversation_id).in_(conversation_ids),
        )
        .distinct(col(Message.conversation_id))
        .order_by(
            col(Message.conversation_id), col(Message.created_at).desc(), col(Message.id).desc()
        )
    )
    return {m.conversation_id: m for m in (await session.exec(statement)).all()}


async def _guests(
    session: AsyncSession, tenant_id: UUID, guest_ids: set[UUID]
) -> dict[UUID, Guest]:
    if not guest_ids:
        return {}
    rows = await session.exec(
        select(Guest).where(col(Guest.tenant_id) == tenant_id, col(Guest.id).in_(guest_ids))
    )
    return {g.id: g for g in rows.all()}


def _to_read(
    conversation: Conversation, guest: Guest | None, last: Message | None, now: dt.datetime
) -> ConversationRead:
    phone = conversation.external_thread_id
    blocked = reply_block_reason(conversation, now)
    return ConversationRead(
        id=conversation.id,
        status=conversation.status,
        guest=GuestSummary(
            id=guest.id if guest else None,
            name=guest.full_name if guest else (phone or "—"),
            phone=phone,
        ),
        unread_count=conversation.unread_count,
        last_message_at=conversation.last_message_at,
        last_message=(
            LastMessage(
                preview=_preview(last.body), direction=last.direction, created_at=last.created_at
            )
            if last
            else None
        ),
        can_reply=blocked is None,
        reply_blocked_reason=blocked,  # type: ignore[arg-type]
        service_window_expires_at=conversation.service_window_expires_at,
    )


async def list_conversations(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    status_filter: ConversationFilter = "open",
    limit: int = DEFAULT_PAGE_SIZE,
    cursor: str | None = None,
) -> ConversationPage:
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    # Keyset paging on (last_message_at, id). Every conversation is created together
    # with its first message, so last_message_at is set; the filter below keeps a
    # NULL from breaking the ordering if one ever appears.
    sort_key = tuple_(col(Conversation.last_message_at), col(Conversation.id))
    statement = select(Conversation).where(
        col(Conversation.tenant_id) == context.tenant_id,
        col(Conversation.property_id) == property_id,
        col(Conversation.last_message_at).is_not(None),
    )
    if status_filter == "resolved":
        statement = statement.where(col(Conversation.status) == "resolved")
    else:
        statement = statement.where(col(Conversation.status).not_in(("resolved", "spam")))
    if cursor:
        statement = statement.where(sort_key < decode_cursor(cursor))
    statement = statement.order_by(
        col(Conversation.last_message_at).desc(), col(Conversation.id).desc()
    ).limit(limit + 1)

    rows = list((await session.exec(statement)).all())
    page, has_more = rows[:limit], len(rows) > limit
    last = await _last_messages(session, context.tenant_id, [c.id for c in page])
    guests = await _guests(session, context.tenant_id, {c.guest_id for c in page if c.guest_id})
    now = dt.datetime.now(dt.UTC)
    return ConversationPage(
        items=[_to_read(c, guests.get(c.guest_id), last.get(c.id), now) for c in page],  # type: ignore[arg-type]
        next_cursor=encode_cursor(page[-1]) if has_more else None,
    )


async def _get_conversation(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    conversation_id: UUID,
    *,
    lock: bool = False,
) -> Conversation:
    statement = select(Conversation).where(
        col(Conversation.tenant_id) == context.tenant_id,
        col(Conversation.property_id) == property_id,
        col(Conversation.id) == conversation_id,
    )
    if lock:
        statement = statement.with_for_update()
    conversation = (await session.exec(statement)).first()
    if conversation is None:
        raise ConversationNotFoundError
    return conversation


async def read_conversation(
    session: AsyncSession, context: TenantContext, property_id: UUID, conversation_id: UUID
) -> ConversationRead:
    conversation = await _get_conversation(session, context, property_id, conversation_id)
    last = await _last_messages(session, context.tenant_id, [conversation.id])
    guests = await _guests(
        session, context.tenant_id, {conversation.guest_id} if conversation.guest_id else set()
    )
    return _to_read(
        conversation,
        guests.get(conversation.guest_id),  # type: ignore[arg-type]
        last.get(conversation.id),
        dt.datetime.now(dt.UTC),
    )


async def _staff_names(
    session: AsyncSession, tenant_id: UUID, staff_ids: set[UUID]
) -> dict[UUID, str]:
    if not staff_ids:
        return {}
    rows = await session.exec(
        select(StaffMember.id, StaffMember.display_name).where(
            col(StaffMember.tenant_id) == tenant_id, col(StaffMember.id).in_(staff_ids)
        )
    )
    return dict(rows.all())


def _message_read(message: Message, staff_names: dict[UUID, str]) -> MessageRead:
    return MessageRead(
        id=message.id,
        conversation_id=message.conversation_id,
        direction=message.direction,
        sender_kind=message.sender_kind,
        sender_name=staff_names.get(message.sender_staff_id) if message.sender_staff_id else None,
        body=message.body,
        status=message.status,
        error=message.error,
        created_at=message.created_at,
    )


async def list_messages(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    conversation_id: UUID,
    after_id: UUID | None = None,
) -> list[MessageRead]:
    """Messages oldest-first: the newest `MAX_THREAD_MESSAGES`, or only those after `after_id`."""
    await _get_conversation(session, context, property_id, conversation_id)
    base = select(Message).where(
        col(Message.tenant_id) == context.tenant_id,
        col(Message.conversation_id) == conversation_id,
    )
    if after_id is not None:
        anchor = (await session.exec(base.where(col(Message.id) == after_id))).first()
        if anchor is not None:
            base = base.where(
                tuple_(col(Message.created_at), col(Message.id)) > (anchor.created_at, anchor.id)
            )
    newest_first = base.order_by(col(Message.created_at).desc(), col(Message.id).desc()).limit(
        MAX_THREAD_MESSAGES
    )
    messages = list(reversed((await session.exec(newest_first)).all()))
    names = await _staff_names(
        session, context.tenant_id, {m.sender_staff_id for m in messages if m.sender_staff_id}
    )
    return [_message_read(m, names) for m in messages]


async def _deliver(account: MessagingAccount, recipient: str, body: str) -> SendResult:
    """Hand the message to the provider; any failure becomes a refused result."""
    try:
        return await get_provider(account.provider).send_text(
            sender=account.sender_identity, recipient=recipient, body=body
        )
    except Exception:  # noqa: BLE001 — a provider fault must not lose the stored message
        log.exception("Provider call failed for account=%s", account.id)
        return SendResult(accepted=False, error=PROVIDER_FAILURE)


async def _queue_reply(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    conversation_id: UUID,
    body: str,
) -> tuple[Message, MessagingAccount, str]:
    """Check the reply is allowed and store it as `queued`. Commits (releases the lock)."""
    conversation = await _get_conversation(
        session, context, property_id, conversation_id, lock=True
    )
    blocked = reply_block_reason(conversation, dt.datetime.now(dt.UTC))
    if blocked == "resolved":
        raise ConversationResolvedError
    if blocked == "window_closed":
        raise ReplyWindowClosedError
    account = (
        await session.exec(
            select(MessagingAccount).where(
                col(MessagingAccount.tenant_id) == context.tenant_id,
                col(MessagingAccount.id) == conversation.messaging_account_id,
            )
        )
    ).one()
    stored_at = next_message_time(conversation.last_message_at)
    message = Message(
        tenant_id=context.tenant_id,
        conversation_id=conversation.id,
        direction="outbound",
        sender_kind="staff",
        sender_staff_id=context.staff_member_id,
        body=body,
        status="queued",
        created_at=stored_at,
    )
    session.add(message)
    conversation.last_message_at = stored_at
    conversation.unread_count = 0
    session.add(conversation)
    recipient = conversation.external_thread_id or ""
    await session.commit()
    return message, account, recipient


async def send_reply(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    conversation_id: UUID,
    body: str,
) -> MessageRead:
    """Send a free-text reply.

    The reply is stored first (`queued`), then handed to the provider with no database
    lock held, then marked `sent` or `failed`. So a message the guest received always
    has a record, and a provider fault never loses what the staff member wrote.
    """
    message, account, recipient = await _queue_reply(
        session, context, property_id, conversation_id, body
    )
    result = await _deliver(account, recipient, body)

    message.provider_message_id = result.provider_message_id
    message.status = "sent" if result.accepted else "failed"
    message.error = None if result.accepted else (result.error or PROVIDER_FAILURE)
    message.sent_at = dt.datetime.now(dt.UTC) if result.accepted else None
    session.add(message)
    await session.commit()
    if not result.accepted:
        log.warning("Reply not accepted by provider conversation=%s", conversation_id)
    names = await _staff_names(
        session, context.tenant_id, {message.sender_staff_id} if message.sender_staff_id else set()
    )
    return _message_read(message, names)


async def mark_read(
    session: AsyncSession, context: TenantContext, property_id: UUID, conversation_id: UUID
) -> ConversationRead:
    conversation = await _get_conversation(
        session, context, property_id, conversation_id, lock=True
    )
    if conversation.unread_count:
        conversation.unread_count = 0
        session.add(conversation)
    await session.commit()
    return await read_conversation(session, context, property_id, conversation_id)


async def set_resolved(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    conversation_id: UUID,
    *,
    resolved: bool,
) -> ConversationRead:
    conversation = await _get_conversation(
        session, context, property_id, conversation_id, lock=True
    )
    conversation.status = "resolved" if resolved else "open"
    if resolved:
        conversation.unread_count = 0
    session.add(conversation)
    try:
        await session.commit()
    except IntegrityError:
        # ux_conversation_thread: one open conversation per guest number.
        await session.rollback()
        raise ReopenConflictError from None
    return await read_conversation(session, context, property_id, conversation_id)
