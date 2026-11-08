"""Promotion entity — table ``promotion``.

Tenant database, E. Rates, policies, products & restrictions.

Promo codes.

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

PromotionDiscountKind = Literal[
    "percent",
    "amount",
    "free_nights",
]


class Promotion(TenantEntity, table=True):
    """Promo codes."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="promotion_tenant_id_id_key"),
        UniqueConstraint("tenant_id", "code", name="promotion_tenant_id_code_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="promotion_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "discount_kind IN ('percent', 'amount', 'free_nights')",
            name="promotion_discount_kind_check",
        ),
        CheckConstraint("(discount_value >= (0)::numeric)", name="promotion_discount_value_check"),
        MIGRATION_ONLY,
    )

    property_id: UUID | None = Field(
        default=None, sa_type=Uuid, description="NULL = all properties"
    )
    code: str = Field(sa_type=Text, description="promo code the guest types (stored upper-case)")
    name: str = Field(sa_type=Text)
    discount_kind: str = Field(sa_type=Text)
    discount_value: Decimal = Field(max_digits=18, decimal_places=2)
    booking_from: dt.date | None = Field(default=None)
    booking_to: dt.date | None = Field(default=None)
    stay_from: dt.date | None = Field(default=None)
    stay_to: dt.date | None = Field(default=None)
    max_uses: int | None = Field(default=None)
    uses_count: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})
    is_combinable: bool = Field(default=False, sa_column_kwargs={"server_default": text("false")})
    conditions: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description='{"min_nights":2,"rate_plan_ids":[...],"channels":["direct_web"]}',
    )
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class PromotionCreate(SQLModel):
    """Fields accepted when creating a Promotion."""

    property_id: UUID | None = None
    code: str
    name: str
    discount_kind: PromotionDiscountKind
    discount_value: Decimal = Field(max_digits=18, decimal_places=2, ge=0)
    booking_from: dt.date | None = None
    booking_to: dt.date | None = None
    stay_from: dt.date | None = None
    stay_to: dt.date | None = None
    max_uses: int | None = None
    uses_count: int = 0
    is_combinable: bool = False
    conditions: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class PromotionUpdate(SQLModel):
    """Fields accepted when patching a Promotion (all optional)."""

    property_id: UUID | None = None
    code: str | None = None
    name: str | None = None
    discount_kind: PromotionDiscountKind | None = None
    discount_value: Decimal | None = Field(default=None, max_digits=18, decimal_places=2, ge=0)
    booking_from: dt.date | None = None
    booking_to: dt.date | None = None
    stay_from: dt.date | None = None
    stay_to: dt.date | None = None
    max_uses: int | None = None
    uses_count: int | None = None
    is_combinable: bool | None = None
    conditions: dict[str, Any] | None = None
    is_active: bool | None = None


class PromotionRead(SQLModel):
    """Fields returned when reading a Promotion."""

    id: UUID
    tenant_id: UUID
    property_id: UUID | None
    code: str
    name: str
    discount_kind: str
    discount_value: Decimal
    booking_from: dt.date | None
    booking_to: dt.date | None
    stay_from: dt.date | None
    stay_to: dt.date | None
    max_uses: int | None
    uses_count: int
    is_combinable: bool
    conditions: dict[str, Any]
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
