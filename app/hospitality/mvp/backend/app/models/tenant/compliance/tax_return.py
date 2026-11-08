"""TaxReturn entity — table ``taxreturn``.

Tenant database, P. Compliance.

Periodic tax return (PBJT hotel/restaurant per kab/kota, tourist tax, VAT).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

TaxReturnTaxCategory = Literal[
    "pbjt_hotel",
    "pbjt_restaurant",
    "tourist_tax",
    "vat",
    "other",
]
TaxReturnStatus = Literal[
    "draft",
    "final",
    "filed",
    "paid",
]


class TaxReturn(TenantEntity, table=True):
    """Periodic tax return (PBJT hotel/restaurant per kab/kota, tourist tax, VAT)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="taxreturn_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "legal_entity_id",
            "property_id",
            "tax_category",
            "period_start",
            name="taxreturn_tenant_id_legal_entity_id_property_id_tax_categor_key",
            postgresql_nulls_not_distinct=True,
        ),
        ForeignKeyConstraint(
            ["tenant_id", "legal_entity_id"],
            ["legalentity.tenant_id", "legalentity.id"],
            name="taxreturn_tenant_id_legal_entity_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="taxreturn_tenant_id_property_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "export_document_id"],
            ["document.tenant_id", "document.id"],
            name="taxreturn_tenant_id_export_document_id_fkey",
            ondelete="SET NULL (export_document_id)",
        ),
        CheckConstraint(
            ("tax_category IN ('pbjt_hotel', 'pbjt_restaurant', 'tourist_tax', 'vat', 'other')"),
            name="taxreturn_tax_category_check",
        ),
        CheckConstraint(
            "status IN ('draft', 'final', 'filed', 'paid')", name="taxreturn_status_check"
        ),
        MIGRATION_ONLY,
    )

    legal_entity_id: UUID = Field(sa_type=Uuid)
    property_id: UUID | None = Field(default=None, sa_type=Uuid)
    region_code: str | None = Field(default=None, sa_type=Text)
    tax_category: str = Field(sa_type=Text)
    period_start: dt.date = Field()
    period_end: dt.date = Field()
    taxable_base: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    tax_amount: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
    )
    status: str = Field(
        default="draft", sa_type=Text, sa_column_kwargs={"server_default": text("'draft'::text")}
    )
    filed_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    filing_reference: str | None = Field(default=None, sa_type=Text)
    export_document_id: UUID | None = Field(default=None, sa_type=Uuid)


class TaxReturnCreate(SQLModel):
    """Fields accepted when creating a TaxReturn."""

    legal_entity_id: UUID
    property_id: UUID | None = None
    region_code: str | None = None
    tax_category: TaxReturnTaxCategory
    period_start: dt.date
    period_end: dt.date
    taxable_base: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    tax_amount: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    details: dict[str, Any] = Field(default_factory=dict)
    status: TaxReturnStatus = "draft"
    filed_at: dt.datetime | None = None
    filing_reference: str | None = None
    export_document_id: UUID | None = None


class TaxReturnUpdate(SQLModel):
    """Fields accepted when patching a TaxReturn (all optional)."""

    legal_entity_id: UUID | None = None
    property_id: UUID | None = None
    region_code: str | None = None
    tax_category: TaxReturnTaxCategory | None = None
    period_start: dt.date | None = None
    period_end: dt.date | None = None
    taxable_base: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    tax_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    details: dict[str, Any] | None = None
    status: TaxReturnStatus | None = None
    filed_at: dt.datetime | None = None
    filing_reference: str | None = None
    export_document_id: UUID | None = None


class TaxReturnRead(SQLModel):
    """Fields returned when reading a TaxReturn."""

    id: UUID
    tenant_id: UUID
    legal_entity_id: UUID
    property_id: UUID | None
    region_code: str | None
    tax_category: str
    period_start: dt.date
    period_end: dt.date
    taxable_base: Decimal
    tax_amount: Decimal
    details: dict[str, Any]
    status: str
    filed_at: dt.datetime | None
    filing_reference: str | None
    export_document_id: UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
