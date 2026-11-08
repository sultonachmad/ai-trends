"""RatePlan entity — table ``rateplan``.

Tenant database, E. Rates, policies, products & restrictions.

Rate plans incl. derived rates, meal plan, nett/++.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

RatePlanDerivationKind = Literal[
    "none",
    "percent",
    "amount",
]
RatePlanPricingModel = Literal[
    "per_unit",
    "per_person",
    "per_bed",
    "base_plus_extra",
]
RatePlanMealPlan = Literal[
    "room_only",
    "breakfast",
    "half_board",
    "full_board",
    "all_inclusive",
]
RatePlanStatus = Literal[
    "draft",
    "active",
    "inactive",
    "archived",
]


class RatePlan(TenantEntity, table=True):
    """Rate plans incl. derived rates, meal plan, nett/++."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="rateplan_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id", "property_id", "code", name="rateplan_tenant_id_property_id_code_key"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="rateplan_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "parent_rate_plan_id"],
            ["rateplan.tenant_id", "rateplan.id"],
            name="rateplan_tenant_id_parent_rate_plan_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "cancellation_policy_id"],
            ["cancellationpolicy.tenant_id", "cancellationpolicy.id"],
            name="rateplan_tenant_id_cancellation_policy_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "payment_policy_id"],
            ["paymentpolicy.tenant_id", "paymentpolicy.id"],
            name="rateplan_tenant_id_payment_policy_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "market_segment_id"],
            ["marketsegment.tenant_id", "marketsegment.id"],
            name="rateplan_tenant_id_market_segment_id_fkey",
            ondelete="SET NULL (market_segment_id)",
        ),
        CheckConstraint(
            "derivation_kind IN ('none', 'percent', 'amount')",
            name="rateplan_derivation_kind_check",
        ),
        CheckConstraint(
            ("pricing_model IN ('per_unit', 'per_person', 'per_bed', 'base_plus_extra')"),
            name="rateplan_pricing_model_check",
        ),
        CheckConstraint(
            (
                "meal_plan IN ('room_only', 'breakfast', 'half_board', 'full_board', "
                "'all_inclusive')"
            ),
            name="rateplan_meal_plan_check",
        ),
        CheckConstraint(
            "status IN ('draft', 'active', 'inactive', 'archived')", name="rateplan_status_check"
        ),
        CheckConstraint(
            "((parent_rate_plan_id IS NULL) OR (parent_rate_plan_id <> id))", name="rateplan_check"
        ),
        CheckConstraint(
            "((derivation_kind = 'none'::text) = (parent_rate_plan_id IS NULL))",
            name="rateplan_check1",
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    code: str = Field(sa_type=Text)
    name: str = Field(sa_type=Text)
    parent_rate_plan_id: UUID | None = Field(
        default=None, sa_type=Uuid, description="derived rates"
    )
    derivation_kind: str = Field(
        default="none", sa_type=Text, sa_column_kwargs={"server_default": text("'none'::text")}
    )
    derivation_value: Decimal | None = Field(default=None, max_digits=18, decimal_places=4)
    pricing_model: str = Field(
        default="per_unit",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'per_unit'::text")},
    )
    meal_plan: str = Field(
        default="room_only",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'room_only'::text")},
    )
    cancellation_policy_id: UUID = Field(sa_type=Uuid)
    payment_policy_id: UUID = Field(sa_type=Uuid)
    market_segment_id: UUID | None = Field(default=None, sa_type=Uuid)
    price_includes_tax: bool = Field(
        default=True, sa_column_kwargs={"server_default": text("true")}, description="nett vs ++"
    )
    is_public: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})
    requires_code: bool = Field(
        default=False,
        sa_column_kwargs={"server_default": text("false")},
        description="corporate / member / promo-only",
    )
    restricted_account_ids: list[UUID] = Field(
        default_factory=list,
        sa_type=ARRAY(Uuid),
        sa_column_kwargs={"server_default": text("'{}'::uuid[]")},
        description="negotiated rates (validated in app)",
    )
    los_pricing: list[Any] = Field(
        default_factory=list,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'[]'::jsonb")},
        description='[{"min_nights":7,"discount_pct":10}]',
    )
    valid_from: dt.date | None = Field(default=None)
    valid_to: dt.date | None = Field(default=None)
    sort_order: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})
    content: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
    )
    status: str = Field(
        default="active", sa_type=Text, sa_column_kwargs={"server_default": text("'active'::text")}
    )


class RatePlanCreate(SQLModel):
    """Fields accepted when creating a RatePlan."""

    property_id: UUID
    code: str
    name: str
    parent_rate_plan_id: UUID | None = None
    derivation_kind: RatePlanDerivationKind = "none"
    derivation_value: Decimal | None = Field(default=None, max_digits=18, decimal_places=4)
    pricing_model: RatePlanPricingModel = "per_unit"
    meal_plan: RatePlanMealPlan = "room_only"
    cancellation_policy_id: UUID
    payment_policy_id: UUID
    market_segment_id: UUID | None = None
    price_includes_tax: bool = True
    is_public: bool = True
    requires_code: bool = False
    restricted_account_ids: list[UUID] = Field(default_factory=list)
    los_pricing: list[Any] = Field(default_factory=list)
    valid_from: dt.date | None = None
    valid_to: dt.date | None = None
    sort_order: int = 0
    content: dict[str, Any] = Field(default_factory=dict)
    status: RatePlanStatus = "active"


class RatePlanUpdate(SQLModel):
    """Fields accepted when patching a RatePlan (all optional)."""

    property_id: UUID | None = None
    code: str | None = None
    name: str | None = None
    parent_rate_plan_id: UUID | None = None
    derivation_kind: RatePlanDerivationKind | None = None
    derivation_value: Decimal | None = Field(default=None, max_digits=18, decimal_places=4)
    pricing_model: RatePlanPricingModel | None = None
    meal_plan: RatePlanMealPlan | None = None
    cancellation_policy_id: UUID | None = None
    payment_policy_id: UUID | None = None
    market_segment_id: UUID | None = None
    price_includes_tax: bool | None = None
    is_public: bool | None = None
    requires_code: bool | None = None
    restricted_account_ids: list[UUID] | None = None
    los_pricing: list[Any] | None = None
    valid_from: dt.date | None = None
    valid_to: dt.date | None = None
    sort_order: int | None = None
    content: dict[str, Any] | None = None
    status: RatePlanStatus | None = None


class RatePlanRead(SQLModel):
    """Fields returned when reading a RatePlan."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    code: str
    name: str
    parent_rate_plan_id: UUID | None
    derivation_kind: str
    derivation_value: Decimal | None
    pricing_model: str
    meal_plan: str
    cancellation_policy_id: UUID
    payment_policy_id: UUID
    market_segment_id: UUID | None
    price_includes_tax: bool
    is_public: bool
    requires_code: bool
    restricted_account_ids: list[UUID]
    los_pricing: list[Any]
    valid_from: dt.date | None
    valid_to: dt.date | None
    sort_order: int
    content: dict[str, Any]
    status: str
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
