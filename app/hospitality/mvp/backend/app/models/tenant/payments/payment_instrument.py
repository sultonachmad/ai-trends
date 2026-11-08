"""PaymentInstrument entity — table ``paymentinstrument``.

Tenant database, I. Payments.

Stored, tokenised instrument (card token, OTA virtual card, e-wallet binding). No PAN ever.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    SmallInteger,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

PaymentInstrumentKind = Literal[
    "card",
    "network_token",
    "ewallet",
    "bank_account",
    "ota_vcc",
]
PaymentInstrumentStatus = Literal[
    "active",
    "expired",
    "revoked",
]


class PaymentInstrument(TenantEntity, table=True):
    """
    Stored, tokenised instrument (card token, OTA virtual card, e-wallet binding). No PAN ever.
    """

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="paymentinstrument_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "gateway_account_id"],
            ["paymentgatewayaccount.tenant_id", "paymentgatewayaccount.id"],
            name="paymentinstrument_tenant_id_gateway_account_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "guest_id"],
            ["guest.tenant_id", "guest.id"],
            name="paymentinstrument_tenant_id_guest_id_fkey",
            ondelete="SET NULL (guest_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "account_id"],
            ["account.tenant_id", "account.id"],
            name="paymentinstrument_tenant_id_account_id_fkey",
            ondelete="SET NULL (account_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_id"],
            ["reservation.tenant_id", "reservation.id"],
            name="paymentinstrument_tenant_id_reservation_id_fkey",
            ondelete="SET NULL (reservation_id)",
        ),
        CheckConstraint(
            "kind IN ('card', 'network_token', 'ewallet', 'bank_account', 'ota_vcc')",
            name="paymentinstrument_kind_check",
        ),
        CheckConstraint(
            "((expiry_month >= 1) AND (expiry_month <= 12))",
            name="paymentinstrument_expiry_month_check",
        ),
        CheckConstraint(
            "status IN ('active', 'expired', 'revoked')", name="paymentinstrument_status_check"
        ),
        MIGRATION_ONLY,
    )

    gateway_account_id: UUID = Field(sa_type=Uuid)
    guest_id: UUID | None = Field(default=None, sa_type=Uuid)
    account_id: UUID | None = Field(default=None, sa_type=Uuid)
    reservation_id: UUID | None = Field(
        default=None, sa_type=Uuid, description="OTA VCC belongs to one reservation"
    )
    kind: str = Field(sa_type=Text)
    token: str = Field(sa_type=Text)
    brand: str | None = Field(default=None, sa_type=Text)
    last4: str | None = Field(default=None, sa_type=Text)
    expiry_month: int | None = Field(default=None, sa_type=SmallInteger)
    expiry_year: int | None = Field(default=None, sa_type=SmallInteger)
    holder_name: str | None = Field(default=None, sa_type=Text)
    vcc_activation_on: dt.date | None = Field(default=None)
    vcc_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    consent_scope: list[str] = Field(
        default_factory=list,
        sa_type=ARRAY(Text),
        sa_column_kwargs={"server_default": text("'{}'::text[]")},
        description="'guarantee','incidentals','scheduled_payments'",
    )
    status: str = Field(
        default="active", sa_type=Text, sa_column_kwargs={"server_default": text("'active'::text")}
    )


class PaymentInstrumentCreate(SQLModel):
    """Fields accepted when creating a PaymentInstrument."""

    gateway_account_id: UUID
    guest_id: UUID | None = None
    account_id: UUID | None = None
    reservation_id: UUID | None = None
    kind: PaymentInstrumentKind
    token: str
    brand: str | None = None
    last4: str | None = None
    expiry_month: int | None = Field(default=None, ge=1, le=12)
    expiry_year: int | None = None
    holder_name: str | None = None
    vcc_activation_on: dt.date | None = None
    vcc_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    consent_scope: list[str] = Field(default_factory=list)
    status: PaymentInstrumentStatus = "active"


class PaymentInstrumentUpdate(SQLModel):
    """Fields accepted when patching a PaymentInstrument (all optional)."""

    gateway_account_id: UUID | None = None
    guest_id: UUID | None = None
    account_id: UUID | None = None
    reservation_id: UUID | None = None
    kind: PaymentInstrumentKind | None = None
    token: str | None = None
    brand: str | None = None
    last4: str | None = None
    expiry_month: int | None = Field(default=None, ge=1, le=12)
    expiry_year: int | None = None
    holder_name: str | None = None
    vcc_activation_on: dt.date | None = None
    vcc_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    consent_scope: list[str] | None = None
    status: PaymentInstrumentStatus | None = None


class PaymentInstrumentRead(SQLModel):
    """Fields returned when reading a PaymentInstrument (never returns: token)."""

    id: UUID
    tenant_id: UUID
    gateway_account_id: UUID
    guest_id: UUID | None
    account_id: UUID | None
    reservation_id: UUID | None
    kind: str
    brand: str | None
    last4: str | None
    expiry_month: int | None
    expiry_year: int | None
    holder_name: str | None
    vcc_activation_on: dt.date | None
    vcc_amount: Decimal | None
    consent_scope: list[str]
    status: str
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
