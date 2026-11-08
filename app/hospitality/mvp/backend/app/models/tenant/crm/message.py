"""Message entity — table ``message``.

Tenant database, L. CRM, messaging & reputation.

Unified inbox.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field

MessageDirection = Literal[
    "inbound",
    "outbound",
    "internal_note",
]
MessageSenderKind = Literal[
    "guest",
    "staff",
    "system",
    "ai_auto",
]
MessageStatus = Literal[
    "received",
    "queued",
    "sent",
    "delivered",
    "read",
    "failed",
]


class Message(TenantRecord, table=True):
    """Unified inbox."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="message_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "conversation_id"],
            ["conversation.tenant_id", "conversation.id"],
            name="message_tenant_id_conversation_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "sender_staff_id"],
            ["staffmember.tenant_id", "staffmember.id"],
            name="message_tenant_id_sender_staff_id_fkey",
            ondelete="SET NULL (sender_staff_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "template_id"],
            ["messagetemplate.tenant_id", "messagetemplate.id"],
            name="message_tenant_id_template_id_fkey",
            ondelete="SET NULL (template_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "ai_suggestion_id"],
            ["aisuggestion.tenant_id", "aisuggestion.id"],
            name="message_tenant_id_ai_suggestion_id_fkey",
            ondelete="SET NULL (ai_suggestion_id)",
            use_alter=True,
        ),
        CheckConstraint(
            "direction IN ('inbound', 'outbound', 'internal_note')", name="message_direction_check"
        ),
        CheckConstraint(
            "sender_kind IN ('guest', 'staff', 'system', 'ai_auto')",
            name="message_sender_kind_check",
        ),
        CheckConstraint(
            "status IN ('received', 'queued', 'sent', 'delivered', 'read', 'failed')",
            name="message_status_check",
        ),
        Index("ix_message_conversation", "tenant_id", "conversation_id", "created_at"),
        Index(
            "ux_message_provider_id",
            "tenant_id",
            "provider_message_id",
            unique=True,
            postgresql_where=text("provider_message_id IS NOT NULL"),
        ),
        MIGRATION_ONLY,
    )

    conversation_id: UUID = Field(sa_type=Uuid)
    direction: str = Field(sa_type=Text)
    sender_kind: str = Field(sa_type=Text)
    sender_staff_id: UUID | None = Field(default=None, sa_type=Uuid)
    body: str | None = Field(default=None, sa_type=Text)
    body_translations: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description='{"en":"…","id":"…"}',
    )
    language: str | None = Field(default=None, sa_type=Text)
    attachment_document_ids: list[UUID] = Field(
        default_factory=list,
        sa_type=ARRAY(Uuid),
        sa_column_kwargs={"server_default": text("'{}'::uuid[]")},
    )
    template_id: UUID | None = Field(default=None, sa_type=Uuid)
    provider_message_id: str | None = Field(default=None, sa_type=Text)
    status: str = Field(
        default="queued", sa_type=Text, sa_column_kwargs={"server_default": text("'queued'::text")}
    )
    error: str | None = Field(default=None, sa_type=Text)
    ai_suggestion_id: UUID | None = Field(
        default=None, sa_type=Uuid, description="FK added after aisuggestion"
    )
    sent_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    delivered_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    read_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    created_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]


class MessageCreate(SQLModel):
    """Fields accepted when creating a Message."""

    conversation_id: UUID
    direction: MessageDirection
    sender_kind: MessageSenderKind
    sender_staff_id: UUID | None = None
    body: str | None = None
    body_translations: dict[str, Any] = Field(default_factory=dict)
    language: str | None = None
    attachment_document_ids: list[UUID] = Field(default_factory=list)
    template_id: UUID | None = None
    provider_message_id: str | None = None
    status: MessageStatus = "queued"
    error: str | None = None
    ai_suggestion_id: UUID | None = None
    sent_at: dt.datetime | None = None
    delivered_at: dt.datetime | None = None
    read_at: dt.datetime | None = None


class MessageUpdate(SQLModel):
    """Fields accepted when patching a Message (all optional)."""

    conversation_id: UUID | None = None
    direction: MessageDirection | None = None
    sender_kind: MessageSenderKind | None = None
    sender_staff_id: UUID | None = None
    body: str | None = None
    body_translations: dict[str, Any] | None = None
    language: str | None = None
    attachment_document_ids: list[UUID] | None = None
    template_id: UUID | None = None
    provider_message_id: str | None = None
    status: MessageStatus | None = None
    error: str | None = None
    ai_suggestion_id: UUID | None = None
    sent_at: dt.datetime | None = None
    delivered_at: dt.datetime | None = None
    read_at: dt.datetime | None = None


class MessageRead(SQLModel):
    """Fields returned when reading a Message."""

    id: UUID
    tenant_id: UUID
    conversation_id: UUID
    direction: str
    sender_kind: str
    sender_staff_id: UUID | None
    body: str | None
    body_translations: dict[str, Any]
    language: str | None
    attachment_document_ids: list[UUID]
    template_id: UUID | None
    provider_message_id: str | None
    status: str
    error: str | None
    ai_suggestion_id: UUID | None
    sent_at: dt.datetime | None
    delivered_at: dt.datetime | None
    read_at: dt.datetime | None
    created_at: dt.datetime
