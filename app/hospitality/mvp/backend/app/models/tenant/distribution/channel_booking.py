"""ChannelBooking entity — table ``channelbooking``.

Tenant database, K. Distribution (channel manager).

Inbound channel booking envelope (idempotent by external id + version).

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
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field

ChannelBookingEventKind = Literal[
    "new",
    "modify",
    "cancel",
]
ChannelBookingProcessingStatus = Literal[
    "pending",
    "applied",
    "needs_attention",
    "duplicate_ignored",
    "failed",
]


class ChannelBooking(TenantRecord, table=True):
    """Inbound channel booking envelope (idempotent by external id + version)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="channelbooking_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "channel_connection_id",
            "external_booking_id",
            "external_version",
            name="channelbooking_tenant_id_channel_connection_id_external_boo_key",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "channel_connection_id"],
            ["channelconnection.tenant_id", "channelconnection.id"],
            name="channelbooking_tenant_id_channel_connection_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_id"],
            ["reservation.tenant_id", "reservation.id"],
            name="channelbooking_tenant_id_reservation_id_fkey",
            ondelete="SET NULL (reservation_id)",
        ),
        CheckConstraint(
            "event_kind IN ('new', 'modify', 'cancel')", name="channelbooking_event_kind_check"
        ),
        CheckConstraint(
            (
                "processing_status IN ('pending', 'applied', 'needs_attention', "
                "'duplicate_ignored', 'failed')"
            ),
            name="channelbooking_processing_status_check",
        ),
        Index(
            "ix_channelbooking_attention",
            "tenant_id",
            "processing_status",
            postgresql_where=text(
                "processing_status = ANY (ARRAY['pending'::text, "
                "'needs_attention'::text, 'failed'::text])"
            ),
        ),
        MIGRATION_ONLY,
    )

    channel_connection_id: UUID = Field(sa_type=Uuid)
    external_booking_id: str = Field(sa_type=Text)
    external_version: str = Field(
        default="1", sa_type=Text, sa_column_kwargs={"server_default": text("'1'::text")}
    )
    event_kind: str = Field(sa_type=Text)
    raw: Any = Field(sa_type=JSONB, nullable=False)
    reservation_id: UUID | None = Field(default=None, sa_type=Uuid)
    processing_status: str = Field(
        default="pending",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'pending'::text")},
    )
    attention_reason: str | None = Field(
        default=None,
        sa_type=Text,
        description="'unmapped_product','overbooking_risk','price_mismatch'",
    )
    received_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]
    processed_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    acknowledged_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]


class ChannelBookingCreate(SQLModel):
    """Fields accepted when creating a ChannelBooking."""

    channel_connection_id: UUID
    external_booking_id: str
    external_version: str = "1"
    event_kind: ChannelBookingEventKind
    raw: Any
    reservation_id: UUID | None = None
    processing_status: ChannelBookingProcessingStatus = "pending"
    attention_reason: str | None = None
    received_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))
    processed_at: dt.datetime | None = None
    acknowledged_at: dt.datetime | None = None


class ChannelBookingUpdate(SQLModel):
    """Fields accepted when patching a ChannelBooking (all optional)."""

    channel_connection_id: UUID | None = None
    external_booking_id: str | None = None
    external_version: str | None = None
    event_kind: ChannelBookingEventKind | None = None
    raw: Any = None
    reservation_id: UUID | None = None
    processing_status: ChannelBookingProcessingStatus | None = None
    attention_reason: str | None = None
    received_at: dt.datetime | None = None
    processed_at: dt.datetime | None = None
    acknowledged_at: dt.datetime | None = None


class ChannelBookingRead(SQLModel):
    """Fields returned when reading a ChannelBooking."""

    id: UUID
    tenant_id: UUID
    channel_connection_id: UUID
    external_booking_id: str
    external_version: str
    event_kind: str
    raw: Any
    reservation_id: UUID | None
    processing_status: str
    attention_reason: str | None
    received_at: dt.datetime
    processed_at: dt.datetime | None
    acknowledged_at: dt.datetime | None
