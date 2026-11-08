"""Settlement entity — table ``settlement``.

Tenant database, I. Payments.

Reconciliation and disputes.

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

SettlementStatus = Literal[
    "imported",
    "reconciled",
    "exceptions",
]


class Settlement(TenantEntity, table=True):
    """Reconciliation and disputes."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="settlement_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "gateway_account_id",
            "settlement_ref",
            name="settlement_tenant_id_gateway_account_id_settlement_ref_key",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "gateway_account_id"],
            ["paymentgatewayaccount.tenant_id", "paymentgatewayaccount.id"],
            name="settlement_tenant_id_gateway_account_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "source_document_id"],
            ["document.tenant_id", "document.id"],
            name="settlement_tenant_id_source_document_id_fkey",
            ondelete="SET NULL (source_document_id)",
        ),
        CheckConstraint(
            "status IN ('imported', 'reconciled', 'exceptions')", name="settlement_status_check"
        ),
        MIGRATION_ONLY,
    )

    gateway_account_id: UUID = Field(sa_type=Uuid)
    settlement_ref: str = Field(sa_type=Text)
    settled_on: dt.date = Field()
    currency: str = Field(sa_type=CHAR(3))
    gross_amount: Decimal = Field(max_digits=18, decimal_places=2)
    fee_amount: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    net_amount: Decimal = Field(max_digits=18, decimal_places=2)
    status: str = Field(
        default="imported",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'imported'::text")},
    )
    source_document_id: UUID | None = Field(default=None, sa_type=Uuid)


class SettlementCreate(SQLModel):
    """Fields accepted when creating a Settlement."""

    gateway_account_id: UUID
    settlement_ref: str
    settled_on: dt.date
    currency: str = Field(min_length=3, max_length=3)
    gross_amount: Decimal = Field(max_digits=18, decimal_places=2)
    fee_amount: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    net_amount: Decimal = Field(max_digits=18, decimal_places=2)
    status: SettlementStatus = "imported"
    source_document_id: UUID | None = None


class SettlementUpdate(SQLModel):
    """Fields accepted when patching a Settlement (all optional)."""

    gateway_account_id: UUID | None = None
    settlement_ref: str | None = None
    settled_on: dt.date | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    gross_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    fee_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    net_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    status: SettlementStatus | None = None
    source_document_id: UUID | None = None


class SettlementRead(SQLModel):
    """Fields returned when reading a Settlement."""

    id: UUID
    tenant_id: UUID
    gateway_account_id: UUID
    settlement_ref: str
    settled_on: dt.date
    currency: str
    gross_amount: Decimal
    fee_amount: Decimal
    net_amount: Decimal
    status: str
    source_document_id: UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
