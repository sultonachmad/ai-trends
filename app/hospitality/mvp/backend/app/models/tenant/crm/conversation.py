"""Conversation entity — table ``conversation``.

Tenant database, L. CRM, messaging & reputation.

Unified inbox.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
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
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

ConversationStatus = Literal[
    "open",
    "pending",
    "snoozed",
    "resolved",
    "spam",
]
ConversationPriority = Literal[
    "low",
    "normal",
    "high",
    "urgent",
]
ConversationSentiment = Literal[
    "positive",
    "neutral",
    "negative",
]


class Conversation(TenantEntity, table=True):
    """Unified inbox."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="conversation_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="conversation_tenant_id_property_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "messaging_account_id"],
            ["messagingaccount.tenant_id", "messagingaccount.id"],
            name="conversation_tenant_id_messaging_account_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "guest_id"],
            ["guest.tenant_id", "guest.id"],
            name="conversation_tenant_id_guest_id_fkey",
            ondelete="SET NULL (guest_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_id"],
            ["reservation.tenant_id", "reservation.id"],
            name="conversation_tenant_id_reservation_id_fkey",
            ondelete="SET NULL (reservation_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "assigned_staff_id"],
            ["staffmember.tenant_id", "staffmember.id"],
            name="conversation_tenant_id_assigned_staff_id_fkey",
            ondelete="SET NULL (assigned_staff_id)",
        ),
        CheckConstraint(
            "status IN ('open', 'pending', 'snoozed', 'resolved', 'spam')",
            name="conversation_status_check",
        ),
        CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')", name="conversation_priority_check"
        ),
        CheckConstraint(
            "sentiment IN ('positive', 'neutral', 'negative')", name="conversation_sentiment_check"
        ),
        Index(
            "ux_conversation_thread",
            "tenant_id",
            "messaging_account_id",
            "external_thread_id",
            unique=True,
            postgresql_where=text(
                "(external_thread_id IS NOT NULL) AND (status <> 'resolved'::text)"
            ),
        ),
        Index(
            "ix_conversation_inbox",
            "tenant_id",
            "property_id",
            "status",
            text("last_message_at DESC"),
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    messaging_account_id: UUID = Field(sa_type=Uuid)
    channel_kind: str = Field(sa_type=Text)
    external_thread_id: str | None = Field(
        default=None, sa_type=Text, description="wa_id / OTA thread id / email thread"
    )
    guest_id: UUID | None = Field(default=None, sa_type=Uuid)
    reservation_id: UUID | None = Field(default=None, sa_type=Uuid)
    status: str = Field(
        default="open", sa_type=Text, sa_column_kwargs={"server_default": text("'open'::text")}
    )
    assigned_staff_id: UUID | None = Field(default=None, sa_type=Uuid)
    priority: str = Field(
        default="normal", sa_type=Text, sa_column_kwargs={"server_default": text("'normal'::text")}
    )
    intent: str | None = Field(default=None, sa_type=Text, description="AI classification")
    sentiment: str | None = Field(default=None, sa_type=Text)
    language: str | None = Field(default=None, sa_type=Text)
    last_message_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    last_inbound_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    service_window_expires_at: dt.datetime | None = utc_datetime_field(
        nullable=True, description="WhatsApp 24h customer-service window"
    )  # type: ignore[assignment]
    sla_due_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    unread_count: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})
    snoozed_until: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]


class ConversationCreate(SQLModel):
    """Fields accepted when creating a Conversation."""

    property_id: UUID
    messaging_account_id: UUID
    channel_kind: str
    external_thread_id: str | None = None
    guest_id: UUID | None = None
    reservation_id: UUID | None = None
    status: ConversationStatus = "open"
    assigned_staff_id: UUID | None = None
    priority: ConversationPriority = "normal"
    intent: str | None = None
    sentiment: ConversationSentiment | None = None
    language: str | None = None
    last_message_at: dt.datetime | None = None
    last_inbound_at: dt.datetime | None = None
    service_window_expires_at: dt.datetime | None = None
    sla_due_at: dt.datetime | None = None
    unread_count: int = 0
    snoozed_until: dt.datetime | None = None


class ConversationUpdate(SQLModel):
    """Fields accepted when patching a Conversation (all optional)."""

    property_id: UUID | None = None
    messaging_account_id: UUID | None = None
    channel_kind: str | None = None
    external_thread_id: str | None = None
    guest_id: UUID | None = None
    reservation_id: UUID | None = None
    status: ConversationStatus | None = None
    assigned_staff_id: UUID | None = None
    priority: ConversationPriority | None = None
    intent: str | None = None
    sentiment: ConversationSentiment | None = None
    language: str | None = None
    last_message_at: dt.datetime | None = None
    last_inbound_at: dt.datetime | None = None
    service_window_expires_at: dt.datetime | None = None
    sla_due_at: dt.datetime | None = None
    unread_count: int | None = None
    snoozed_until: dt.datetime | None = None


class ConversationRead(SQLModel):
    """Fields returned when reading a Conversation."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    messaging_account_id: UUID
    channel_kind: str
    external_thread_id: str | None
    guest_id: UUID | None
    reservation_id: UUID | None
    status: str
    assigned_staff_id: UUID | None
    priority: str
    intent: str | None
    sentiment: str | None
    language: str | None
    last_message_at: dt.datetime | None
    last_inbound_at: dt.datetime | None
    service_window_expires_at: dt.datetime | None
    sla_due_at: dt.datetime | None
    unread_count: int
    snoozed_until: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
