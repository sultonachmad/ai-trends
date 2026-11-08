"""TaxRule entity — table ``taxrule``.

Tenant database, D. Finance configuration.

PBJT, service charge, tourist tax, VAT; effective-dated; per region.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

TaxRuleReportCategory = Literal[
    "pbjt_hotel",
    "pbjt_restaurant",
    "vat",
    "service_charge",
    "tourist_tax",
    "other",
]
TaxRuleCalcKind = Literal[
    "percent",
    "fixed_per_unit_night",
    "fixed_per_person_night",
    "fixed_per_stay",
    "fixed_per_item",
]


class TaxRule(TenantEntity, table=True):
    """PBJT, service charge, tourist tax, VAT; effective-dated; per region."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="taxrule_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id", "code", "effective_from", name="taxrule_tenant_id_code_effective_from_key"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="taxrule_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            (
                "report_category IN ('pbjt_hotel', 'pbjt_restaurant', 'vat', "
                "'service_charge', 'tourist_tax', 'other')"
            ),
            name="taxrule_report_category_check",
        ),
        CheckConstraint(
            (
                "calc_kind IN ('percent', 'fixed_per_unit_night', "
                "'fixed_per_person_night', 'fixed_per_stay', 'fixed_per_item')"
            ),
            name="taxrule_calc_kind_check",
        ),
        CheckConstraint(
            "((effective_to IS NULL) OR (effective_to >= effective_from))", name="taxrule_check"
        ),
        CheckConstraint(
            (
                "(((calc_kind = 'percent'::text) AND (rate_pct IS NOT NULL)) OR "
                "((calc_kind <> 'percent'::text) AND (fixed_amount IS NOT NULL)))"
            ),
            name="taxrule_check1",
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID | None = Field(default=None, sa_type=Uuid, description="NULL = tenant-wide")
    code: str = Field(sa_type=Text)
    name: str = Field(sa_type=Text)
    report_category: str = Field(sa_type=Text)
    calc_kind: str = Field(sa_type=Text)
    rate_pct: Decimal | None = Field(default=None, max_digits=7, decimal_places=4)
    fixed_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    is_inclusive: bool = Field(
        default=False,
        sa_column_kwargs={"server_default": text("false")},
        description='included in price ("nett") vs added ("++")',
    )
    compound_order: int = Field(
        default=0,
        sa_column_kwargs={"server_default": text("0")},
        description="service charge (0) before PBJT (1) when PBJT applies on top",
    )
    region_code: str | None = Field(default=None, sa_type=Text)
    effective_from: dt.date = Field()
    effective_to: dt.date | None = Field(default=None)
    exemptions: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description='{"max_nights":30,"min_age":12,"long_stay_exempt_after":30}',
    )
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class TaxRuleCreate(SQLModel):
    """Fields accepted when creating a TaxRule."""

    property_id: UUID | None = None
    code: str
    name: str
    report_category: TaxRuleReportCategory
    calc_kind: TaxRuleCalcKind
    rate_pct: Decimal | None = Field(default=None, max_digits=7, decimal_places=4)
    fixed_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    is_inclusive: bool = False
    compound_order: int = 0
    region_code: str | None = None
    effective_from: dt.date
    effective_to: dt.date | None = None
    exemptions: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class TaxRuleUpdate(SQLModel):
    """Fields accepted when patching a TaxRule (all optional)."""

    property_id: UUID | None = None
    code: str | None = None
    name: str | None = None
    report_category: TaxRuleReportCategory | None = None
    calc_kind: TaxRuleCalcKind | None = None
    rate_pct: Decimal | None = Field(default=None, max_digits=7, decimal_places=4)
    fixed_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    is_inclusive: bool | None = None
    compound_order: int | None = None
    region_code: str | None = None
    effective_from: dt.date | None = None
    effective_to: dt.date | None = None
    exemptions: dict[str, Any] | None = None
    is_active: bool | None = None


class TaxRuleRead(SQLModel):
    """Fields returned when reading a TaxRule."""

    id: UUID
    tenant_id: UUID
    property_id: UUID | None
    code: str
    name: str
    report_category: str
    calc_kind: str
    rate_pct: Decimal | None
    fixed_amount: Decimal | None
    is_inclusive: bool
    compound_order: int
    region_code: str | None
    effective_from: dt.date
    effective_to: dt.date | None
    exemptions: dict[str, Any]
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
