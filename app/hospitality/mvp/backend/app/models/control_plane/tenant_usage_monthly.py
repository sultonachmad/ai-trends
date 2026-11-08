"""TenantUsageMonthly entity — table ``tenantusagemonthly``.

Control-plane database, Control plane.

Detailed per-call AI usage lives in the tenant DB (aiusage). This rolls it up per tenant per
month for billing and platform cost control.

Mirrors .ttest/contexts/schema-control-plane.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CHAR, CheckConstraint, ForeignKeyConstraint, Text, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, utc_datetime_field


class TenantUsageMonthly(SQLModel, table=True):
    """
    Detailed per-call AI usage lives in the tenant DB (aiusage). This rolls it up per tenant per
    month for billing and platform cost control.
    """

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
            name="tenantusagemonthly_tenant_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            ("((date_trunc('month'::text, (month)::timestamp with time zone))::date = month)"),
            name="tenantusagemonthly_month_check",
        ),
        MIGRATION_ONLY,
    )

    tenant_id: UUID = Field(primary_key=True, sa_type=Uuid)
    month: dt.date = Field(primary_key=True)
    metric: str = Field(
        primary_key=True,
        sa_type=Text,
        description="'ai_cost_idr','ai_tokens','whatsapp_messages','active_units'",
    )
    quantity: Decimal = Field(
        default=Decimal("0"),
        max_digits=20,
        decimal_places=4,
        sa_column_kwargs={"server_default": text("0")},
    )
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    currency: str | None = Field(default=None, sa_type=CHAR(3))
    updated_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, onupdate_now=True, server_default_now=True
    )  # type: ignore[assignment]


class TenantUsageMonthlyCreate(SQLModel):
    """Fields accepted when creating a TenantUsageMonthly."""

    tenant_id: UUID
    month: dt.date
    metric: str
    quantity: Decimal = Field(default=Decimal("0"), max_digits=20, decimal_places=4)
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class TenantUsageMonthlyUpdate(SQLModel):
    """Fields accepted when patching a TenantUsageMonthly (all optional)."""

    quantity: Decimal | None = Field(default=None, max_digits=20, decimal_places=4)
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class TenantUsageMonthlyRead(SQLModel):
    """Fields returned when reading a TenantUsageMonthly."""

    tenant_id: UUID
    month: dt.date
    metric: str
    quantity: Decimal
    amount: Decimal | None
    currency: str | None
    updated_at: dt.datetime
