"""ChannelMessage entity — table ``channelmessage``.

Tenant database, K. Distribution (channel manager).

Outbound/inbound message log (ARI pushes, acks, errors). High volume -> partition later.

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

ChannelMessageDirection = Literal[
    "outbound",
    "inbound",
]
ChannelMessageMessageType = Literal[
    "ari_delta",
    "ari_full_sync",
    "booking",
    "booking_ack",
    "content",
    "ping",
    "error",
]
ChannelMessageStatus = Literal[
    "queued",
    "sent",
    "acked",
    "failed",
    "dead",
]


class ChannelMessage(TenantRecord, table=True):
    """
    Outbound/inbound message log (ARI pushes, acks, errors). High volume -> partition later.
    """

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="channelmessage_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "channel_connection_id"],
            ["channelconnection.tenant_id", "channelconnection.id"],
            name="channelmessage_tenant_id_channel_connection_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "direction IN ('outbound', 'inbound')", name="channelmessage_direction_check"
        ),
        CheckConstraint(
            (
                "message_type IN ('ari_delta', 'ari_full_sync', 'booking', "
                "'booking_ack', 'content', 'ping', 'error')"
            ),
            name="channelmessage_message_type_check",
        ),
        CheckConstraint(
            "status IN ('queued', 'sent', 'acked', 'failed', 'dead')",
            name="channelmessage_status_check",
        ),
        Index(
            "ix_channelmessage_queue",
            "next_attempt_at",
            postgresql_where=text("status = ANY (ARRAY['queued'::text, 'failed'::text])"),
        ),
        Index("ix_channelmessage_conn", "tenant_id", "channel_connection_id", "created_at"),
        MIGRATION_ONLY,
    )

    channel_connection_id: UUID = Field(sa_type=Uuid)
    direction: str = Field(sa_type=Text)
    message_type: str = Field(sa_type=Text)
    status: str = Field(
        default="queued", sa_type=Text, sa_column_kwargs={"server_default": text("'queued'::text")}
    )
    attempts: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})
    next_attempt_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    date_from: dt.date | None = Field(default=None)
    date_to: dt.date | None = Field(default=None)
    correlation_id: str | None = Field(default=None, sa_type=Text)
    request_payload: Any = Field(default=None, sa_type=JSONB, nullable=True)
    response_payload: Any = Field(default=None, sa_type=JSONB, nullable=True)
    error: str | None = Field(default=None, sa_type=Text)
    created_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]
    sent_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]


class ChannelMessageCreate(SQLModel):
    """Fields accepted when creating a ChannelMessage."""

    channel_connection_id: UUID
    direction: ChannelMessageDirection
    message_type: ChannelMessageMessageType
    status: ChannelMessageStatus = "queued"
    attempts: int = 0
    next_attempt_at: dt.datetime | None = None
    date_from: dt.date | None = None
    date_to: dt.date | None = None
    correlation_id: str | None = None
    request_payload: Any = None
    response_payload: Any = None
    error: str | None = None
    sent_at: dt.datetime | None = None


class ChannelMessageUpdate(SQLModel):
    """Fields accepted when patching a ChannelMessage (all optional)."""

    channel_connection_id: UUID | None = None
    direction: ChannelMessageDirection | None = None
    message_type: ChannelMessageMessageType | None = None
    status: ChannelMessageStatus | None = None
    attempts: int | None = None
    next_attempt_at: dt.datetime | None = None
    date_from: dt.date | None = None
    date_to: dt.date | None = None
    correlation_id: str | None = None
    request_payload: Any = None
    response_payload: Any = None
    error: str | None = None
    sent_at: dt.datetime | None = None


class ChannelMessageRead(SQLModel):
    """Fields returned when reading a ChannelMessage."""

    id: UUID
    tenant_id: UUID
    channel_connection_id: UUID
    direction: str
    message_type: str
    status: str
    attempts: int
    next_attempt_at: dt.datetime | None
    date_from: dt.date | None
    date_to: dt.date | None
    correlation_id: str | None
    request_payload: Any
    response_payload: Any
    error: str | None
    created_at: dt.datetime
    sent_at: dt.datetime | None
