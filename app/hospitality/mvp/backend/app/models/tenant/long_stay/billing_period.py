"""BillingPeriod entity — table ``billingperiod``.

Tenant database, O. Long stay, kos & leases.

One billing period of a lease (monthly kos invoice + pay link + reminders).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

BillingPeriodStatus = Literal[
    "scheduled",
    "invoiced",
    "paid",
    "overdue",
    "waived",
    "cancelled",
]


class BillingPeriod(TenantEntity, table=True):
    """One billing period of a lease (monthly kos invoice + pay link + reminders)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="billingperiod_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "lease_id",
            "period_start",
            name="billingperiod_tenant_id_lease_id_period_start_key",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "lease_id"],
            ["lease.tenant_id", "lease.id"],
            name="billingperiod_tenant_id_lease_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "invoice_id"],
            ["invoice.tenant_id", "invoice.id"],
            name="billingperiod_tenant_id_invoice_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "payment_link_id"],
            ["paymentlink.tenant_id", "paymentlink.id"],
            name="billingperiod_tenant_id_payment_link_id_fkey",
            ondelete="SET NULL (payment_link_id)",
        ),
        CheckConstraint(
            ("status IN ('scheduled', 'invoiced', 'paid', 'overdue', 'waived', 'cancelled')"),
            name="billingperiod_status_check",
        ),
        CheckConstraint("(period_end >= period_start)", name="billingperiod_check"),
        MIGRATION_ONLY,
    )

    lease_id: UUID = Field(sa_type=Uuid)
    period_start: dt.date = Field()
    period_end: dt.date = Field()
    due_on: dt.date = Field()
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    invoice_id: UUID | None = Field(default=None, sa_type=Uuid)
    payment_link_id: UUID | None = Field(default=None, sa_type=Uuid)
    status: str = Field(
        default="scheduled",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'scheduled'::text")},
    )
    reminder_count: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})
    last_reminded_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]


class BillingPeriodCreate(SQLModel):
    """Fields accepted when creating a BillingPeriod."""

    lease_id: UUID
    period_start: dt.date
    period_end: dt.date
    due_on: dt.date
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    invoice_id: UUID | None = None
    payment_link_id: UUID | None = None
    status: BillingPeriodStatus = "scheduled"
    reminder_count: int = 0
    last_reminded_at: dt.datetime | None = None


class BillingPeriodUpdate(SQLModel):
    """Fields accepted when patching a BillingPeriod (all optional)."""

    lease_id: UUID | None = None
    period_start: dt.date | None = None
    period_end: dt.date | None = None
    due_on: dt.date | None = None
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    invoice_id: UUID | None = None
    payment_link_id: UUID | None = None
    status: BillingPeriodStatus | None = None
    reminder_count: int | None = None
    last_reminded_at: dt.datetime | None = None


class BillingPeriodRead(SQLModel):
    """Fields returned when reading a BillingPeriod."""

    id: UUID
    tenant_id: UUID
    lease_id: UUID
    period_start: dt.date
    period_end: dt.date
    due_on: dt.date
    amount: Decimal
    invoice_id: UUID | None
    payment_link_id: UUID | None
    status: str
    reminder_count: int
    last_reminded_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
