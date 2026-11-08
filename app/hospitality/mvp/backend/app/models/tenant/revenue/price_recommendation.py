"""PriceRecommendation entity — table ``pricerecommendation``.

Tenant database, R. Revenue management.

Explainable forecasts, recommendations, budgets.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import (
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

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field

PriceRecommendationStatus = Literal[
    "pending",
    "accepted",
    "rejected",
    "auto_applied",
    "superseded",
    "expired",
]


class PriceRecommendation(TenantRecord, table=True):
    """Explainable forecasts, recommendations, budgets."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="pricerecommendation_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="pricerecommendation_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_type_id"],
            ["unittype.tenant_id", "unittype.id"],
            name="pricerecommendation_tenant_id_unit_type_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "rate_plan_id"],
            ["rateplan.tenant_id", "rateplan.id"],
            name="pricerecommendation_tenant_id_rate_plan_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            (
                "status IN ('pending', 'accepted', 'rejected', 'auto_applied', "
                "'superseded', 'expired')"
            ),
            name="pricerecommendation_status_check",
        ),
        Index(
            "ix_pricerecommendation_pending",
            "tenant_id",
            "property_id",
            "stay_date",
            postgresql_where=text("status = 'pending'::text"),
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    unit_type_id: UUID = Field(sa_type=Uuid)
    rate_plan_id: UUID = Field(sa_type=Uuid)
    stay_date: dt.date = Field()
    current_amount: Decimal = Field(max_digits=18, decimal_places=2)
    recommended_amount: Decimal = Field(max_digits=18, decimal_places=2)
    reasons: list[Any] = Field(
        default_factory=list,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'[]'::jsonb")},
    )
    explanation: str | None = Field(
        default=None, sa_type=Text, description="AI plain-language summary"
    )
    status: str = Field(
        default="pending",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'pending'::text")},
    )
    decided_by: str | None = Field(default=None, sa_type=Text)
    decided_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    applied_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    created_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]


class PriceRecommendationCreate(SQLModel):
    """Fields accepted when creating a PriceRecommendation."""

    property_id: UUID
    unit_type_id: UUID
    rate_plan_id: UUID
    stay_date: dt.date
    current_amount: Decimal = Field(max_digits=18, decimal_places=2)
    recommended_amount: Decimal = Field(max_digits=18, decimal_places=2)
    reasons: list[Any] = Field(default_factory=list)
    explanation: str | None = None
    status: PriceRecommendationStatus = "pending"
    decided_by: str | None = None
    decided_at: dt.datetime | None = None
    applied_at: dt.datetime | None = None


class PriceRecommendationUpdate(SQLModel):
    """Fields accepted when patching a PriceRecommendation (all optional)."""

    property_id: UUID | None = None
    unit_type_id: UUID | None = None
    rate_plan_id: UUID | None = None
    stay_date: dt.date | None = None
    current_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    recommended_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    reasons: list[Any] | None = None
    explanation: str | None = None
    status: PriceRecommendationStatus | None = None
    decided_by: str | None = None
    decided_at: dt.datetime | None = None
    applied_at: dt.datetime | None = None


class PriceRecommendationRead(SQLModel):
    """Fields returned when reading a PriceRecommendation."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    unit_type_id: UUID
    rate_plan_id: UUID
    stay_date: dt.date
    current_amount: Decimal
    recommended_amount: Decimal
    reasons: list[Any]
    explanation: str | None
    status: str
    decided_by: str | None
    decided_at: dt.datetime | None
    applied_at: dt.datetime | None
    created_at: dt.datetime
