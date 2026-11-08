"""PaymentEvent entity — table ``paymentevent``.

Tenant database, I. Payments.

Raw gateway callbacks / webhooks (append-only).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKeyConstraint, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field


class PaymentEvent(TenantRecord, table=True):
    """Raw gateway callbacks / webhooks (append-only)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="paymentevent_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "gateway_account_id",
            "gateway_event_id",
            name="paymentevent_tenant_id_gateway_account_id_gateway_event_id_key",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "payment_id"],
            ["payment.tenant_id", "payment.id"],
            name="paymentevent_tenant_id_payment_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "gateway_account_id"],
            ["paymentgatewayaccount.tenant_id", "paymentgatewayaccount.id"],
            name="paymentevent_tenant_id_gateway_account_id_fkey",
        ),
        MIGRATION_ONLY,
    )

    payment_id: UUID | None = Field(default=None, sa_type=Uuid)
    gateway_account_id: UUID = Field(sa_type=Uuid)
    gateway_event_id: str = Field(sa_type=Text)
    event_type: str = Field(sa_type=Text)
    status: str | None = Field(default=None, sa_type=Text)
    raw: Any = Field(sa_type=JSONB, nullable=False)
    signature_valid: bool = Field()
    received_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]
    processed_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]


class PaymentEventCreate(SQLModel):
    """Fields accepted when creating a PaymentEvent."""

    payment_id: UUID | None = None
    gateway_account_id: UUID
    gateway_event_id: str
    event_type: str
    status: str | None = None
    raw: Any
    signature_valid: bool
    received_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))
    processed_at: dt.datetime | None = None


class PaymentEventUpdate(SQLModel):
    """Fields accepted when patching a PaymentEvent (all optional)."""

    payment_id: UUID | None = None
    gateway_account_id: UUID | None = None
    gateway_event_id: str | None = None
    event_type: str | None = None
    status: str | None = None
    raw: Any = None
    signature_valid: bool | None = None
    received_at: dt.datetime | None = None
    processed_at: dt.datetime | None = None


class PaymentEventRead(SQLModel):
    """Fields returned when reading a PaymentEvent."""

    id: UUID
    tenant_id: UUID
    payment_id: UUID | None
    gateway_account_id: UUID
    gateway_event_id: str
    event_type: str
    status: str | None
    raw: Any
    signature_valid: bool
    received_at: dt.datetime
    processed_at: dt.datetime | None
