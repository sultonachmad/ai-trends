"""PaymentGatewayAccount entity — table ``paymentgatewayaccount``.

Tenant database, I. Payments.

Midtrans / Xendit / DOKU / … config (secret refs).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

PaymentGatewayAccountProvider = Literal[
    "midtrans",
    "xendit",
    "doku",
    "faspay",
    "stripe",
    "adyen",
    "manual_bank",
    "other",
]
PaymentGatewayAccountStatus = Literal[
    "setup",
    "active",
    "disabled",
    "error",
]


class PaymentGatewayAccount(TenantEntity, table=True):
    """Midtrans / Xendit / DOKU / … config (secret refs)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="paymentgatewayaccount_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="paymentgatewayaccount_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            (
                "provider IN ('midtrans', 'xendit', 'doku', 'faspay', 'stripe', 'adyen', "
                "'manual_bank', 'other')"
            ),
            name="paymentgatewayaccount_provider_check",
        ),
        CheckConstraint(
            "status IN ('setup', 'active', 'disabled', 'error')",
            name="paymentgatewayaccount_status_check",
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID | None = Field(default=None, sa_type=Uuid, description="NULL = tenant-wide")
    provider: str = Field(sa_type=Text)
    display_name: str = Field(sa_type=Text)
    merchant_ref: str | None = Field(default=None, sa_type=Text)
    credentials_secret_ref: str | None = Field(
        default=None, sa_type=Text, description="secret-manager key; never the key itself"
    )
    supported_methods: list[str] = Field(
        default_factory=list,
        sa_type=ARRAY(Text),
        sa_column_kwargs={"server_default": text("'{}'::text[]")},
        description="'qris','virtual_account','ewallet','card'",
    )
    settlement_currency: str = Field(
        default="IDR", sa_type=CHAR(3), sa_column_kwargs={"server_default": text("'IDR'::bpchar")}
    )
    is_default: bool = Field(default=False, sa_column_kwargs={"server_default": text("false")})
    status: str = Field(
        default="active", sa_type=Text, sa_column_kwargs={"server_default": text("'active'::text")}
    )
    settings: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
    )


class PaymentGatewayAccountCreate(SQLModel):
    """Fields accepted when creating a PaymentGatewayAccount."""

    property_id: UUID | None = None
    provider: PaymentGatewayAccountProvider
    display_name: str
    merchant_ref: str | None = None
    credentials_secret_ref: str | None = None
    supported_methods: list[str] = Field(default_factory=list)
    settlement_currency: str = Field(default="IDR", min_length=3, max_length=3)
    is_default: bool = False
    status: PaymentGatewayAccountStatus = "active"
    settings: dict[str, Any] = Field(default_factory=dict)


class PaymentGatewayAccountUpdate(SQLModel):
    """Fields accepted when patching a PaymentGatewayAccount (all optional)."""

    property_id: UUID | None = None
    provider: PaymentGatewayAccountProvider | None = None
    display_name: str | None = None
    merchant_ref: str | None = None
    credentials_secret_ref: str | None = None
    supported_methods: list[str] | None = None
    settlement_currency: str | None = Field(default=None, min_length=3, max_length=3)
    is_default: bool | None = None
    status: PaymentGatewayAccountStatus | None = None
    settings: dict[str, Any] | None = None


class PaymentGatewayAccountRead(SQLModel):
    """Fields returned when reading a PaymentGatewayAccount."""

    id: UUID
    tenant_id: UUID
    property_id: UUID | None
    provider: str
    display_name: str
    merchant_ref: str | None
    credentials_secret_ref: str | None
    supported_methods: list[str]
    settlement_currency: str
    is_default: bool
    status: str
    settings: dict[str, Any]
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
