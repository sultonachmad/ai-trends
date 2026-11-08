"""Voucher entity — table ``voucher``.

Tenant database, Q. Ancillary / POS lite.

POS Lite, services, gift vouchers.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Literal
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
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

VoucherKind = Literal[
    "monetary",
    "experience",
]
VoucherStatus = Literal[
    "active",
    "redeemed",
    "expired",
    "cancelled",
]


class Voucher(TenantEntity, table=True):
    """POS Lite, services, gift vouchers."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="voucher_tenant_id_id_key"),
        UniqueConstraint("tenant_id", "code", name="voucher_tenant_id_code_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="voucher_tenant_id_property_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "buyer_guest_id"],
            ["guest.tenant_id", "guest.id"],
            name="voucher_tenant_id_buyer_guest_id_fkey",
            ondelete="SET NULL (buyer_guest_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "payment_id"],
            ["payment.tenant_id", "payment.id"],
            name="voucher_tenant_id_payment_id_fkey",
        ),
        CheckConstraint("kind IN ('monetary', 'experience')", name="voucher_kind_check"),
        CheckConstraint("(initial_value >= (0)::numeric)", name="voucher_initial_value_check"),
        CheckConstraint("(balance >= (0)::numeric)", name="voucher_balance_check"),
        CheckConstraint(
            "status IN ('active', 'redeemed', 'expired', 'cancelled')", name="voucher_status_check"
        ),
        CheckConstraint("(balance <= initial_value)", name="voucher_check"),
        MIGRATION_ONLY,
    )

    property_id: UUID | None = Field(default=None, sa_type=Uuid)
    code: str = Field(sa_type=Text)
    kind: str = Field(sa_type=Text)
    initial_value: Decimal = Field(max_digits=18, decimal_places=2)
    balance: Decimal = Field(max_digits=18, decimal_places=2)
    currency: str = Field(
        default="IDR", sa_type=CHAR(3), sa_column_kwargs={"server_default": text("'IDR'::bpchar")}
    )
    expires_on: dt.date | None = Field(default=None)
    buyer_guest_id: UUID | None = Field(default=None, sa_type=Uuid)
    payment_id: UUID | None = Field(default=None, sa_type=Uuid)
    status: str = Field(
        default="active", sa_type=Text, sa_column_kwargs={"server_default": text("'active'::text")}
    )


class VoucherCreate(SQLModel):
    """Fields accepted when creating a Voucher."""

    property_id: UUID | None = None
    code: str
    kind: VoucherKind
    initial_value: Decimal = Field(max_digits=18, decimal_places=2, ge=0)
    balance: Decimal = Field(max_digits=18, decimal_places=2, ge=0)
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    expires_on: dt.date | None = None
    buyer_guest_id: UUID | None = None
    payment_id: UUID | None = None
    status: VoucherStatus = "active"


class VoucherUpdate(SQLModel):
    """Fields accepted when patching a Voucher (all optional)."""

    property_id: UUID | None = None
    code: str | None = None
    kind: VoucherKind | None = None
    initial_value: Decimal | None = Field(default=None, max_digits=18, decimal_places=2, ge=0)
    balance: Decimal | None = Field(default=None, max_digits=18, decimal_places=2, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    expires_on: dt.date | None = None
    buyer_guest_id: UUID | None = None
    payment_id: UUID | None = None
    status: VoucherStatus | None = None


class VoucherRead(SQLModel):
    """Fields returned when reading a Voucher."""

    id: UUID
    tenant_id: UUID
    property_id: UUID | None
    code: str
    kind: str
    initial_value: Decimal
    balance: Decimal
    currency: str
    expires_on: dt.date | None
    buyer_guest_id: UUID | None
    payment_id: UUID | None
    status: str
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
