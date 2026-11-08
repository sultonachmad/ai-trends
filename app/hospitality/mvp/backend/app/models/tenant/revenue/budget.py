"""Budget entity — table ``budget``.

Tenant database, R. Revenue management.

Explainable forecasts, recommendations, budgets.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

BudgetMetric = Literal[
    "occupancy",
    "adr",
    "revpar",
    "room_revenue",
    "total_revenue",
    "room_nights",
]
BudgetKind = Literal[
    "budget",
    "forecast",
    "target",
]


class Budget(TenantEntity, table=True):
    """Explainable forecasts, recommendations, budgets."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="budget_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "property_id",
            "month",
            "metric",
            "segment_code",
            "kind",
            name="budget_tenant_id_property_id_month_metric_segment_code_kind_key",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="budget_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            ("((date_trunc('month'::text, (month)::timestamp with time zone))::date = month)"),
            name="budget_month_check",
        ),
        CheckConstraint(
            (
                "metric IN ('occupancy', 'adr', 'revpar', 'room_revenue', "
                "'total_revenue', 'room_nights')"
            ),
            name="budget_metric_check",
        ),
        CheckConstraint("kind IN ('budget', 'forecast', 'target')", name="budget_kind_check"),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    month: dt.date = Field()
    metric: str = Field(sa_type=Text)
    segment_code: str = Field(
        default="", sa_type=Text, sa_column_kwargs={"server_default": text("''::text")}
    )
    amount: Decimal = Field(max_digits=18, decimal_places=4)
    kind: str = Field(
        default="budget", sa_type=Text, sa_column_kwargs={"server_default": text("'budget'::text")}
    )


class BudgetCreate(SQLModel):
    """Fields accepted when creating a Budget."""

    property_id: UUID
    month: dt.date
    metric: BudgetMetric
    segment_code: str = ""
    amount: Decimal = Field(max_digits=18, decimal_places=4)
    kind: BudgetKind = "budget"


class BudgetUpdate(SQLModel):
    """Fields accepted when patching a Budget (all optional)."""

    property_id: UUID | None = None
    month: dt.date | None = None
    metric: BudgetMetric | None = None
    segment_code: str | None = None
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=4)
    kind: BudgetKind | None = None


class BudgetRead(SQLModel):
    """Fields returned when reading a Budget."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    month: dt.date
    metric: str
    segment_code: str
    amount: Decimal
    kind: str
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
