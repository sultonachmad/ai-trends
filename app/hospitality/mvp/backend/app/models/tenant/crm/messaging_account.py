"""MessagingAccount entity — table ``messagingaccount``.

Tenant database, L. CRM, messaging & reputation.

WhatsApp / SMS / email / Instagram / Google Business senders.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

MessagingAccountChannelKind = Literal[
    "whatsapp",
    "sms",
    "email",
    "instagram",
    "google_business",
    "ota",
    "web_chat",
]
MessagingAccountStatus = Literal[
    "setup",
    "active",
    "disabled",
    "error",
]


class MessagingAccount(TenantEntity, table=True):
    """WhatsApp / SMS / email / Instagram / Google Business senders."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="messagingaccount_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "channel_kind",
            "sender_identity",
            name="messagingaccount_tenant_id_channel_kind_sender_identity_key",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="messagingaccount_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            (
                "channel_kind IN ('whatsapp', 'sms', 'email', 'instagram', "
                "'google_business', 'ota', 'web_chat')"
            ),
            name="messagingaccount_channel_kind_check",
        ),
        CheckConstraint(
            "status IN ('setup', 'active', 'disabled', 'error')",
            name="messagingaccount_status_check",
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID | None = Field(default=None, sa_type=Uuid)
    channel_kind: str = Field(sa_type=Text)
    provider: str = Field(
        sa_type=Text, description="'meta_cloud','twilio','smtp','ses','booking_com',…"
    )
    sender_identity: str = Field(sa_type=Text, description="phone number / email / page id")
    credentials_secret_ref: str | None = Field(default=None, sa_type=Text)
    status: str = Field(
        default="active", sa_type=Text, sa_column_kwargs={"server_default": text("'active'::text")}
    )
    settings: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
    )


class MessagingAccountCreate(SQLModel):
    """Fields accepted when creating a MessagingAccount."""

    property_id: UUID | None = None
    channel_kind: MessagingAccountChannelKind
    provider: str
    sender_identity: str
    credentials_secret_ref: str | None = None
    status: MessagingAccountStatus = "active"
    settings: dict[str, Any] = Field(default_factory=dict)


class MessagingAccountUpdate(SQLModel):
    """Fields accepted when patching a MessagingAccount (all optional)."""

    property_id: UUID | None = None
    channel_kind: MessagingAccountChannelKind | None = None
    provider: str | None = None
    sender_identity: str | None = None
    credentials_secret_ref: str | None = None
    status: MessagingAccountStatus | None = None
    settings: dict[str, Any] | None = None


class MessagingAccountRead(SQLModel):
    """Fields returned when reading a MessagingAccount."""

    id: UUID
    tenant_id: UUID
    property_id: UUID | None
    channel_kind: str
    provider: str
    sender_identity: str
    credentials_secret_ref: str | None
    status: str
    settings: dict[str, Any]
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
