"""ChannelConnection entity — table ``channelconnection``.

Tenant database, K. Distribution (channel manager).

Property ↔ channel link, status, payment model.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    ForeignKeyConstraint,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

ChannelConnectionConnectionVia = Literal[
    "direct_api",
    "partner",
    "ical",
]
ChannelConnectionStatus = Literal[
    "draft",
    "testing",
    "live",
    "paused",
    "error",
    "disconnected",
]
ChannelConnectionPaymentCollectModel = Literal[
    "property",
    "channel",
    "mixed",
]


class ChannelConnection(TenantEntity, table=True):
    """Property ↔ channel link, status, payment model."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="channelconnection_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "property_id",
            "channel_id",
            "external_property_id",
            name="channelconnection_tenant_id_property_id_channel_id_external_key",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="channelconnection_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "channel_id"],
            ["channel.tenant_id", "channel.id"],
            name="channelconnection_tenant_id_channel_id_fkey",
        ),
        CheckConstraint(
            "connection_via IN ('direct_api', 'partner', 'ical')",
            name="channelconnection_connection_via_check",
        ),
        CheckConstraint(
            ("status IN ('draft', 'testing', 'live', 'paused', 'error', 'disconnected')"),
            name="channelconnection_status_check",
        ),
        CheckConstraint(
            "payment_collect_model IN ('property', 'channel', 'mixed')",
            name="channelconnection_payment_collect_model_check",
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    channel_id: UUID = Field(sa_type=Uuid)
    external_property_id: str | None = Field(default=None, sa_type=Text)
    connection_via: str = Field(sa_type=Text)
    partner_name: str | None = Field(default=None, sa_type=Text)
    credentials_secret_ref: str | None = Field(default=None, sa_type=Text)
    status: str = Field(
        default="draft", sa_type=Text, sa_column_kwargs={"server_default": text("'draft'::text")}
    )
    currency: str = Field(
        default="IDR", sa_type=CHAR(3), sa_column_kwargs={"server_default": text("'IDR'::bpchar")}
    )
    rate_markup_pct: Decimal = Field(
        default=Decimal("0"),
        max_digits=6,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    payment_collect_model: str = Field(
        default="property",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'property'::text")},
    )
    last_ari_success_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    last_booking_pull_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    error_message: str | None = Field(default=None, sa_type=Text)
    settings: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
    )


class ChannelConnectionCreate(SQLModel):
    """Fields accepted when creating a ChannelConnection."""

    property_id: UUID
    channel_id: UUID
    external_property_id: str | None = None
    connection_via: ChannelConnectionConnectionVia
    partner_name: str | None = None
    credentials_secret_ref: str | None = None
    status: ChannelConnectionStatus = "draft"
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    rate_markup_pct: Decimal = Field(default=Decimal("0"), max_digits=6, decimal_places=2)
    payment_collect_model: ChannelConnectionPaymentCollectModel = "property"
    last_ari_success_at: dt.datetime | None = None
    last_booking_pull_at: dt.datetime | None = None
    error_message: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)


class ChannelConnectionUpdate(SQLModel):
    """Fields accepted when patching a ChannelConnection (all optional)."""

    property_id: UUID | None = None
    channel_id: UUID | None = None
    external_property_id: str | None = None
    connection_via: ChannelConnectionConnectionVia | None = None
    partner_name: str | None = None
    credentials_secret_ref: str | None = None
    status: ChannelConnectionStatus | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    rate_markup_pct: Decimal | None = Field(default=None, max_digits=6, decimal_places=2)
    payment_collect_model: ChannelConnectionPaymentCollectModel | None = None
    last_ari_success_at: dt.datetime | None = None
    last_booking_pull_at: dt.datetime | None = None
    error_message: str | None = None
    settings: dict[str, Any] | None = None


class ChannelConnectionRead(SQLModel):
    """Fields returned when reading a ChannelConnection."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    channel_id: UUID
    external_property_id: str | None
    connection_via: str
    partner_name: str | None
    credentials_secret_ref: str | None
    status: str
    currency: str
    rate_markup_pct: Decimal
    payment_collect_model: str
    last_ari_success_at: dt.datetime | None
    last_booking_pull_at: dt.datetime | None
    error_message: str | None
    settings: dict[str, Any]
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
