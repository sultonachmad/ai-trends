"""Shapes for the inbox: conversations, messages, replies, simulated inbound."""

import datetime as dt
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

MAX_MESSAGE_LENGTH = 4096  # WhatsApp text limit
PREVIEW_LENGTH = 140

MessageBody = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_LENGTH)
]
GuestName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
PhoneInput = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]

ConversationFilter = Literal["open", "resolved"]


class ReplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: MessageBody


class SimulatedInboundRequest(BaseModel):
    """A tester acting as a guest (development only)."""

    model_config = ConfigDict(extra="forbid")

    from_phone: PhoneInput
    guest_name: GuestName | None = None
    body: MessageBody


class GuestSummary(BaseModel):
    id: UUID | None
    name: str
    phone: str | None


class MessageRead(BaseModel):
    id: UUID
    conversation_id: UUID
    direction: str
    sender_kind: str
    sender_name: str | None
    body: str | None
    status: str
    error: str | None
    created_at: dt.datetime


class LastMessage(BaseModel):
    preview: str
    direction: str
    created_at: dt.datetime


class ConversationRead(BaseModel):
    id: UUID
    status: str
    guest: GuestSummary
    unread_count: int
    last_message_at: dt.datetime | None
    last_message: LastMessage | None
    can_reply: bool
    reply_blocked_reason: Literal["resolved", "window_closed"] | None
    service_window_expires_at: dt.datetime | None


class ConversationPage(BaseModel):
    items: list[ConversationRead]
    next_cursor: str | None


class InboxSummary(BaseModel):
    unread_conversations: int


class InboundResult(BaseModel):
    conversation_id: UUID
    message_id: UUID
    duplicate: bool
