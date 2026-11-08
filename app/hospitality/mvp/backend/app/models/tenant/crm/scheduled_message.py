"""ScheduledMessage entity — table ``scheduledmessage``.

Tenant database, L. CRM, messaging & reputation.

Lifecycle journeys with review-before-send.

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

ScheduledMessageStatus = Literal[
    "scheduled",
    "awaiting_approval",
    "sent",
    "cancelled",
    "failed",
    "suppressed",
]


class ScheduledMessage(TenantEntity, table=True):
    """Lifecycle journeys with review-before-send."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="scheduledmessage_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "automation_id"],
            ["automation.tenant_id", "automation.id"],
            name="scheduledmessage_tenant_id_automation_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "campaign_id"],
            ["campaign.tenant_id", "campaign.id"],
            name="scheduledmessage_tenant_id_campaign_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_id"],
            ["reservation.tenant_id", "reservation.id"],
            name="scheduledmessage_tenant_id_reservation_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "guest_id"],
            ["guest.tenant_id", "guest.id"],
            name="scheduledmessage_tenant_id_guest_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "template_id"],
            ["messagetemplate.tenant_id", "messagetemplate.id"],
            name="scheduledmessage_tenant_id_template_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "message_id"],
            ["message.tenant_id", "message.id"],
            name="scheduledmessage_tenant_id_message_id_fkey",
            ondelete="SET NULL (message_id)",
        ),
        CheckConstraint(
            (
                "status IN ('scheduled', 'awaiting_approval', 'sent', 'cancelled', "
                "'failed', 'suppressed')"
            ),
            name="scheduledmessage_status_check",
        ),
        CheckConstraint(
            "((automation_id IS NOT NULL) OR (campaign_id IS NOT NULL))",
            name="scheduledmessage_check",
        ),
        Index(
            "ix_scheduledmessage_due",
            "send_at",
            postgresql_where=text("status = 'scheduled'::text"),
        ),
        MIGRATION_ONLY,
    )

    automation_id: UUID | None = Field(default=None, sa_type=Uuid)
    campaign_id: UUID | None = Field(default=None, sa_type=Uuid)
    reservation_id: UUID | None = Field(default=None, sa_type=Uuid)
    guest_id: UUID = Field(sa_type=Uuid)
    template_id: UUID = Field(sa_type=Uuid)
    channel_kind: str = Field(sa_type=Text)
    send_at: dt.datetime = utc_datetime_field(nullable=False)  # type: ignore[assignment]
    status: str = Field(
        default="scheduled",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'scheduled'::text")},
    )
    suppress_reason: str | None = Field(
        default=None, sa_type=Text, description="'no_consent','quiet_hours','active_conversation'"
    )
    message_id: UUID | None = Field(default=None, sa_type=Uuid)
    approved_by: str | None = Field(default=None, sa_type=Text)


class ScheduledMessageCreate(SQLModel):
    """Fields accepted when creating a ScheduledMessage."""

    automation_id: UUID | None = None
    campaign_id: UUID | None = None
    reservation_id: UUID | None = None
    guest_id: UUID
    template_id: UUID
    channel_kind: str
    send_at: dt.datetime
    status: ScheduledMessageStatus = "scheduled"
    suppress_reason: str | None = None
    message_id: UUID | None = None
    approved_by: str | None = None


class ScheduledMessageUpdate(SQLModel):
    """Fields accepted when patching a ScheduledMessage (all optional)."""

    automation_id: UUID | None = None
    campaign_id: UUID | None = None
    reservation_id: UUID | None = None
    guest_id: UUID | None = None
    template_id: UUID | None = None
    channel_kind: str | None = None
    send_at: dt.datetime | None = None
    status: ScheduledMessageStatus | None = None
    suppress_reason: str | None = None
    message_id: UUID | None = None
    approved_by: str | None = None


class ScheduledMessageRead(SQLModel):
    """Fields returned when reading a ScheduledMessage."""

    id: UUID
    tenant_id: UUID
    automation_id: UUID | None
    campaign_id: UUID | None
    reservation_id: UUID | None
    guest_id: UUID
    template_id: UUID
    channel_kind: str
    send_at: dt.datetime
    status: str
    suppress_reason: str | None
    message_id: UUID | None
    approved_by: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
