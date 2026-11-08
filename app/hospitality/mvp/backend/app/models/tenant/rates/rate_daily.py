"""RateDaily entity — table ``ratedaily``.

Tenant database, E. Rates, policies, products & restrictions.

Price per rate plan x unit type x date. Amount = one time unit of the unit type's grain (night,
day, hour block, month) starting on stay_date.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field

RateDailySource = Literal[
    "manual",
    "bulk",
    "rms",
    "rule",
    "import",
    "derived",
]


class RateDaily(TenantRecord, table=True):
    """
    Price per rate plan x unit type x date. Amount = one time unit of the unit type's grain
    (night, day, hour block, month) starting on stay_date.
    """

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="ratedaily_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "rate_plan_id",
            "unit_type_id",
            "stay_date",
            name="ratedaily_tenant_id_rate_plan_id_unit_type_id_stay_date_key",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "rate_plan_id"],
            ["rateplan.tenant_id", "rateplan.id"],
            name="ratedaily_tenant_id_rate_plan_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_type_id"],
            ["unittype.tenant_id", "unittype.id"],
            name="ratedaily_tenant_id_unit_type_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint("(amount >= (0)::numeric)", name="ratedaily_amount_check"),
        CheckConstraint(
            "source IN ('manual', 'bulk', 'rms', 'rule', 'import', 'derived')",
            name="ratedaily_source_check",
        ),
        MIGRATION_ONLY,
    )

    rate_plan_id: UUID = Field(sa_type=Uuid)
    unit_type_id: UUID = Field(sa_type=Uuid)
    stay_date: dt.date = Field()
    amount: Decimal = Field(max_digits=18, decimal_places=2, description="base occupancy price")
    occupancy_prices: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description='{"1":450000,"3":650000}',
    )
    extra_adult: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    extra_child: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    source: str = Field(
        default="manual", sa_type=Text, sa_column_kwargs={"server_default": text("'manual'::text")}
    )
    updated_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, onupdate_now=True, server_default_now=True
    )  # type: ignore[assignment]
    updated_by: str | None = Field(default=None, sa_type=Text)


class RateDailyCreate(SQLModel):
    """Fields accepted when creating a RateDaily."""

    rate_plan_id: UUID
    unit_type_id: UUID
    stay_date: dt.date
    amount: Decimal = Field(max_digits=18, decimal_places=2, ge=0)
    occupancy_prices: dict[str, Any] = Field(default_factory=dict)
    extra_adult: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    extra_child: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    source: RateDailySource = "manual"


class RateDailyUpdate(SQLModel):
    """Fields accepted when patching a RateDaily (all optional)."""

    rate_plan_id: UUID | None = None
    unit_type_id: UUID | None = None
    stay_date: dt.date | None = None
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2, ge=0)
    occupancy_prices: dict[str, Any] | None = None
    extra_adult: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    extra_child: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    source: RateDailySource | None = None


class RateDailyRead(SQLModel):
    """Fields returned when reading a RateDaily."""

    id: UUID
    tenant_id: UUID
    rate_plan_id: UUID
    unit_type_id: UUID
    stay_date: dt.date
    amount: Decimal
    occupancy_prices: dict[str, Any]
    extra_adult: Decimal | None
    extra_child: Decimal | None
    source: str
    updated_at: dt.datetime
    updated_by: str | None
