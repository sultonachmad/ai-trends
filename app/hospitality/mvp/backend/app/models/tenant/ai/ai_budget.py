"""AiBudget entity — table ``aibudget``.

Tenant database, S. AI assistant layer.

Enablement, autonomy, monthly cap.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    ForeignKeyConstraint,
    SmallInteger,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field


class AiBudget(TenantRecord, table=True):
    """Enablement, autonomy, monthly cap."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="aibudget_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "property_id",
            "month",
            name="aibudget_tenant_id_property_id_month_key",
            postgresql_nulls_not_distinct=True,
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="aibudget_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            ("((date_trunc('month'::text, (month)::timestamp with time zone))::date = month)"),
            name="aibudget_month_check",
        ),
        CheckConstraint("(limit_amount >= (0)::numeric)", name="aibudget_limit_amount_check"),
        MIGRATION_ONLY,
    )

    property_id: UUID | None = Field(default=None, sa_type=Uuid)
    month: dt.date = Field()
    limit_amount: Decimal = Field(max_digits=18, decimal_places=2)
    spent_amount: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=6,
        sa_column_kwargs={"server_default": text("0")},
    )
    currency: str = Field(
        default="IDR", sa_type=CHAR(3), sa_column_kwargs={"server_default": text("'IDR'::bpchar")}
    )
    alert_threshold_pct: int = Field(
        default=80, sa_type=SmallInteger, sa_column_kwargs={"server_default": text("80")}
    )
    alerted_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    exhausted_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    updated_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, onupdate_now=True, server_default_now=True
    )  # type: ignore[assignment]


class AiBudgetCreate(SQLModel):
    """Fields accepted when creating a AiBudget."""

    property_id: UUID | None = None
    month: dt.date
    limit_amount: Decimal = Field(max_digits=18, decimal_places=2, ge=0)
    spent_amount: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=6)
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    alert_threshold_pct: int = 80
    alerted_at: dt.datetime | None = None
    exhausted_at: dt.datetime | None = None


class AiBudgetUpdate(SQLModel):
    """Fields accepted when patching a AiBudget (all optional)."""

    property_id: UUID | None = None
    month: dt.date | None = None
    limit_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2, ge=0)
    spent_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=6)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    alert_threshold_pct: int | None = None
    alerted_at: dt.datetime | None = None
    exhausted_at: dt.datetime | None = None


class AiBudgetRead(SQLModel):
    """Fields returned when reading a AiBudget."""

    id: UUID
    tenant_id: UUID
    property_id: UUID | None
    month: dt.date
    limit_amount: Decimal
    spent_amount: Decimal
    currency: str
    alert_threshold_pct: int
    alerted_at: dt.datetime | None
    exhausted_at: dt.datetime | None
    updated_at: dt.datetime
