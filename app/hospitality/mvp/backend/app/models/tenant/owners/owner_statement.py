"""OwnerStatement entity — table ``ownerstatement``.

Tenant database, N. Owners.

Owner accounting.

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

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

OwnerStatementStatus = Literal[
    "draft",
    "approved",
    "sent",
    "paid",
    "void",
]


class OwnerStatement(TenantEntity, table=True):
    """Owner accounting."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="ownerstatement_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "owner_id",
            "property_id",
            "period_start",
            name="ownerstatement_tenant_id_owner_id_property_id_period_start_key",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "owner_id"],
            ["owner.tenant_id", "owner.id"],
            name="ownerstatement_tenant_id_owner_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="ownerstatement_tenant_id_property_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "pdf_document_id"],
            ["document.tenant_id", "document.id"],
            name="ownerstatement_tenant_id_pdf_document_id_fkey",
            ondelete="SET NULL (pdf_document_id)",
        ),
        CheckConstraint(
            "status IN ('draft', 'approved', 'sent', 'paid', 'void')",
            name="ownerstatement_status_check",
        ),
        CheckConstraint("(period_end >= period_start)", name="ownerstatement_check"),
        MIGRATION_ONLY,
    )

    owner_id: UUID = Field(sa_type=Uuid)
    property_id: UUID = Field(sa_type=Uuid)
    number: str | None = Field(default=None, sa_type=Text)
    period_start: dt.date = Field()
    period_end: dt.date = Field()
    currency: str = Field(
        default="IDR", sa_type=CHAR(3), sa_column_kwargs={"server_default": text("'IDR'::bpchar")}
    )
    gross_revenue: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    commission_total: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    expense_total: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    withholding_tax: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    net_payable: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    fx_rate_reporting: Decimal | None = Field(
        default=None, max_digits=20, decimal_places=8, description="to owner's reporting currency"
    )
    status: str = Field(
        default="draft", sa_type=Text, sa_column_kwargs={"server_default": text("'draft'::text")}
    )
    approved_by: str | None = Field(default=None, sa_type=Text)
    approved_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    pdf_document_id: UUID | None = Field(default=None, sa_type=Uuid)


class OwnerStatementCreate(SQLModel):
    """Fields accepted when creating a OwnerStatement."""

    owner_id: UUID
    property_id: UUID
    number: str | None = None
    period_start: dt.date
    period_end: dt.date
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    gross_revenue: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    commission_total: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    expense_total: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    withholding_tax: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    net_payable: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    fx_rate_reporting: Decimal | None = Field(default=None, max_digits=20, decimal_places=8)
    status: OwnerStatementStatus = "draft"
    approved_by: str | None = None
    approved_at: dt.datetime | None = None
    pdf_document_id: UUID | None = None


class OwnerStatementUpdate(SQLModel):
    """Fields accepted when patching a OwnerStatement (all optional)."""

    owner_id: UUID | None = None
    property_id: UUID | None = None
    number: str | None = None
    period_start: dt.date | None = None
    period_end: dt.date | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    gross_revenue: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    commission_total: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    expense_total: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    withholding_tax: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    net_payable: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    fx_rate_reporting: Decimal | None = Field(default=None, max_digits=20, decimal_places=8)
    status: OwnerStatementStatus | None = None
    approved_by: str | None = None
    approved_at: dt.datetime | None = None
    pdf_document_id: UUID | None = None


class OwnerStatementRead(SQLModel):
    """Fields returned when reading a OwnerStatement."""

    id: UUID
    tenant_id: UUID
    owner_id: UUID
    property_id: UUID
    number: str | None
    period_start: dt.date
    period_end: dt.date
    currency: str
    gross_revenue: Decimal
    commission_total: Decimal
    expense_total: Decimal
    withholding_tax: Decimal
    net_payable: Decimal
    fx_rate_reporting: Decimal | None
    status: str
    approved_by: str | None
    approved_at: dt.datetime | None
    pdf_document_id: UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
