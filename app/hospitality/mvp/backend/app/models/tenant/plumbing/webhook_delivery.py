"""WebhookDelivery entity — table ``webhookdelivery``.

Tenant database, T. Platform plumbing.

Events and outbound webhooks.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field

WebhookDeliveryStatus = Literal[
    "pending",
    "delivered",
    "failed",
    "dead",
]


class WebhookDelivery(TenantRecord, table=True):
    """Events and outbound webhooks."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="webhookdelivery_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "endpoint_id"],
            ["webhookendpoint.tenant_id", "webhookendpoint.id"],
            name="webhookdelivery_tenant_id_endpoint_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "outbox_event_id"],
            ["outboxevent.tenant_id", "outboxevent.id"],
            name="webhookdelivery_tenant_id_outbox_event_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('pending', 'delivered', 'failed', 'dead')",
            name="webhookdelivery_status_check",
        ),
        MIGRATION_ONLY,
    )

    endpoint_id: UUID = Field(sa_type=Uuid)
    outbox_event_id: UUID = Field(sa_type=Uuid)
    status: str = Field(
        default="pending",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'pending'::text")},
    )
    attempts: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})
    next_attempt_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    response_code: int | None = Field(default=None)
    response_body: str | None = Field(default=None, sa_type=Text)
    created_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]


class WebhookDeliveryCreate(SQLModel):
    """Fields accepted when creating a WebhookDelivery."""

    endpoint_id: UUID
    outbox_event_id: UUID
    status: WebhookDeliveryStatus = "pending"
    attempts: int = 0
    next_attempt_at: dt.datetime | None = None
    response_code: int | None = None
    response_body: str | None = None


class WebhookDeliveryUpdate(SQLModel):
    """Fields accepted when patching a WebhookDelivery (all optional)."""

    endpoint_id: UUID | None = None
    outbox_event_id: UUID | None = None
    status: WebhookDeliveryStatus | None = None
    attempts: int | None = None
    next_attempt_at: dt.datetime | None = None
    response_code: int | None = None
    response_body: str | None = None


class WebhookDeliveryRead(SQLModel):
    """Fields returned when reading a WebhookDelivery."""

    id: UUID
    tenant_id: UUID
    endpoint_id: UUID
    outbox_event_id: UUID
    status: str
    attempts: int
    next_attempt_at: dt.datetime | None
    response_code: int | None
    response_body: str | None
    created_at: dt.datetime
