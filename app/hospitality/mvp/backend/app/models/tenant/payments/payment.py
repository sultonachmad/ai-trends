"""Payment entity — table ``payment``.

Tenant database, I. Payments.

QRIS, VA, e-wallet, card, cash, transfer, refunds.

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
    Index,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

PaymentDirection = Literal[
    "inbound",
    "refund",
]
PaymentMethod = Literal[
    "qris",
    "virtual_account",
    "ewallet",
    "card",
    "bank_transfer",
    "cash",
    "voucher",
    "ota_vcc",
    "direct_bill",
    "points",
    "other",
]
PaymentStatus = Literal[
    "pending",
    "requires_action",
    "authorized",
    "captured",
    "partially_refunded",
    "refunded",
    "failed",
    "cancelled",
    "expired",
    "awaiting_verification",
]


class Payment(TenantEntity, table=True):
    """QRIS, VA, e-wallet, card, cash, transfer, refunds."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="payment_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id", "idempotency_key", name="payment_tenant_id_idempotency_key_key"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="payment_tenant_id_property_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "folio_id"],
            ["folio.tenant_id", "folio.id"],
            name="payment_tenant_id_folio_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_id"],
            ["reservation.tenant_id", "reservation.id"],
            name="payment_tenant_id_reservation_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "gateway_account_id"],
            ["paymentgatewayaccount.tenant_id", "paymentgatewayaccount.id"],
            name="payment_tenant_id_gateway_account_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "instrument_id"],
            ["paymentinstrument.tenant_id", "paymentinstrument.id"],
            name="payment_tenant_id_instrument_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "payment_link_id"],
            ["paymentlink.tenant_id", "paymentlink.id"],
            name="payment_tenant_id_payment_link_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "payment_schedule_id"],
            ["paymentschedule.tenant_id", "paymentschedule.id"],
            name="payment_tenant_id_payment_schedule_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "refund_of_payment_id"],
            ["payment.tenant_id", "payment.id"],
            name="payment_tenant_id_refund_of_payment_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "cashier_shift_id"],
            ["cashiershift.tenant_id", "cashiershift.id"],
            name="payment_tenant_id_cashier_shift_id_fkey",
        ),
        CheckConstraint("direction IN ('inbound', 'refund')", name="payment_direction_check"),
        CheckConstraint(
            (
                "method IN ('qris', 'virtual_account', 'ewallet', 'card', "
                "'bank_transfer', 'cash', 'voucher', 'ota_vcc', 'direct_bill', 'points', "
                "'other')"
            ),
            name="payment_method_check",
        ),
        CheckConstraint(
            (
                "status IN ('pending', 'requires_action', 'authorized', 'captured', "
                "'partially_refunded', 'refunded', 'failed', 'cancelled', 'expired', "
                "'awaiting_verification')"
            ),
            name="payment_status_check",
        ),
        CheckConstraint("(amount > (0)::numeric)", name="payment_amount_check"),
        CheckConstraint(
            ("((captured_amount <= authorized_amount) OR (authorized_amount = (0)::numeric))"),
            name="payment_check",
        ),
        CheckConstraint(
            "((refunded_amount <= captured_amount) OR (direction = 'refund'::text))",
            name="payment_check1",
        ),
        CheckConstraint(
            "((direction = 'refund'::text) = (refund_of_payment_id IS NOT NULL))",
            name="payment_check2",
        ),
        Index(
            "ix_payment_reservation",
            "tenant_id",
            "reservation_id",
            postgresql_where=text("reservation_id IS NOT NULL"),
        ),
        Index(
            "ix_payment_gateway_ref",
            "tenant_id",
            "gateway_reference",
            postgresql_where=text("gateway_reference IS NOT NULL"),
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    folio_id: UUID | None = Field(default=None, sa_type=Uuid)
    reservation_id: UUID | None = Field(default=None, sa_type=Uuid)
    gateway_account_id: UUID | None = Field(default=None, sa_type=Uuid)
    instrument_id: UUID | None = Field(default=None, sa_type=Uuid)
    payment_link_id: UUID | None = Field(default=None, sa_type=Uuid)
    payment_schedule_id: UUID | None = Field(default=None, sa_type=Uuid)
    refund_of_payment_id: UUID | None = Field(default=None, sa_type=Uuid)
    direction: str = Field(
        default="inbound",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'inbound'::text")},
    )
    method: str = Field(sa_type=Text)
    method_detail: str | None = Field(
        default=None, sa_type=Text, description="'BCA','GoPay','VISA'"
    )
    status: str = Field(
        default="pending",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'pending'::text")},
    )
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    currency: str = Field(
        default="IDR", sa_type=CHAR(3), sa_column_kwargs={"server_default": text("'IDR'::bpchar")}
    )
    authorized_amount: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    captured_amount: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    refunded_amount: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    fee_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    gateway_reference: str | None = Field(default=None, sa_type=Text)
    idempotency_key: str = Field(sa_type=Text)
    authorization_expires_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    captured_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    cashier_shift_id: UUID | None = Field(default=None, sa_type=Uuid)
    failure_reason: str | None = Field(default=None, sa_type=Text)
    metadata_: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb"), "name": "metadata"},
    )
    version: int = Field(default=1, sa_column_kwargs={"server_default": text("1")})


class PaymentCreate(SQLModel):
    """Fields accepted when creating a Payment."""

    property_id: UUID
    folio_id: UUID | None = None
    reservation_id: UUID | None = None
    gateway_account_id: UUID | None = None
    instrument_id: UUID | None = None
    payment_link_id: UUID | None = None
    payment_schedule_id: UUID | None = None
    refund_of_payment_id: UUID | None = None
    direction: PaymentDirection = "inbound"
    method: PaymentMethod
    method_detail: str | None = None
    status: PaymentStatus = "pending"
    amount: Decimal = Field(max_digits=18, decimal_places=2, gt=0)
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    authorized_amount: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    captured_amount: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    refunded_amount: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    fee_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    gateway_reference: str | None = None
    idempotency_key: str
    authorization_expires_at: dt.datetime | None = None
    captured_at: dt.datetime | None = None
    cashier_shift_id: UUID | None = None
    failure_reason: str | None = None
    metadata_: dict[str, Any] = Field(default_factory=dict)


class PaymentUpdate(SQLModel):
    """Fields accepted when patching a Payment (all optional)."""

    property_id: UUID | None = None
    folio_id: UUID | None = None
    reservation_id: UUID | None = None
    gateway_account_id: UUID | None = None
    instrument_id: UUID | None = None
    payment_link_id: UUID | None = None
    payment_schedule_id: UUID | None = None
    refund_of_payment_id: UUID | None = None
    direction: PaymentDirection | None = None
    method: PaymentMethod | None = None
    method_detail: str | None = None
    status: PaymentStatus | None = None
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    authorized_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    captured_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    refunded_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    fee_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    gateway_reference: str | None = None
    idempotency_key: str | None = None
    authorization_expires_at: dt.datetime | None = None
    captured_at: dt.datetime | None = None
    cashier_shift_id: UUID | None = None
    failure_reason: str | None = None
    metadata_: dict[str, Any] | None = None


class PaymentRead(SQLModel):
    """Fields returned when reading a Payment."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    folio_id: UUID | None
    reservation_id: UUID | None
    gateway_account_id: UUID | None
    instrument_id: UUID | None
    payment_link_id: UUID | None
    payment_schedule_id: UUID | None
    refund_of_payment_id: UUID | None
    direction: str
    method: str
    method_detail: str | None
    status: str
    amount: Decimal
    currency: str
    authorized_amount: Decimal
    captured_amount: Decimal
    refunded_amount: Decimal
    fee_amount: Decimal | None
    gateway_reference: str | None
    idempotency_key: str
    authorization_expires_at: dt.datetime | None
    captured_at: dt.datetime | None
    cashier_shift_id: UUID | None
    failure_reason: str | None
    metadata_: dict[str, Any]
    version: int
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
