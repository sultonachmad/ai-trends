"""Plan entity — table ``plan``.

Control-plane database, Control plane.

Subscription plans.

Mirrors .ttest/contexts/schema-control-plane.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import CHAR, CheckConstraint, Text, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, UUIDEntity

PlanBillingBasis = Literal[
    "per_unit",
    "flat",
    "usage",
    "free",
]
PlanBillingPeriod = Literal[
    "monthly",
    "yearly",
]


class Plan(UUIDEntity, table=True):
    """Subscription plans."""

    __table_args__ = (
        UniqueConstraint("code", name="plan_code_key"),
        CheckConstraint(
            "billing_basis IN ('per_unit', 'flat', 'usage', 'free')",
            name="plan_billing_basis_check",
        ),
        CheckConstraint(
            "billing_period IN ('monthly', 'yearly')", name="plan_billing_period_check"
        ),
        MIGRATION_ONLY,
    )

    code: str = Field(sa_type=Text)
    name: str = Field(sa_type=Text)
    billing_basis: str = Field(sa_type=Text)
    price_amount: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    currency: str = Field(
        default="IDR", sa_type=CHAR(3), sa_column_kwargs={"server_default": text("'IDR'::bpchar")}
    )
    billing_period: str = Field(
        default="monthly",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'monthly'::text")},
    )
    is_public: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class PlanCreate(SQLModel):
    """Fields accepted when creating a Plan."""

    code: str
    name: str
    billing_basis: PlanBillingBasis
    price_amount: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    billing_period: PlanBillingPeriod = "monthly"
    is_public: bool = True
    is_active: bool = True


class PlanUpdate(SQLModel):
    """Fields accepted when patching a Plan (all optional)."""

    code: str | None = None
    name: str | None = None
    billing_basis: PlanBillingBasis | None = None
    price_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    billing_period: PlanBillingPeriod | None = None
    is_public: bool | None = None
    is_active: bool | None = None


class PlanRead(SQLModel):
    """Fields returned when reading a Plan."""

    id: UUID
    code: str
    name: str
    billing_basis: str
    price_amount: Decimal
    currency: str
    billing_period: str
    is_public: bool
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
