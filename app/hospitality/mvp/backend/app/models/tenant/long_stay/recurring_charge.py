"""RecurringCharge entity — table ``recurringcharge``.

Tenant database, O. Long stay, kos & leases.

Recurring charges for any reservation (daily parking, monthly laundry, kos rent lines).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Literal
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
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

RecurringChargeFrequency = Literal[
    "daily",
    "weekly",
    "monthly",
    "billing_cycle",
]


class RecurringCharge(TenantEntity, table=True):
    """
    Recurring charges for any reservation (daily parking, monthly laundry, kos rent lines).
    """

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="recurringcharge_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_id"],
            ["reservation.tenant_id", "reservation.id"],
            name="recurringcharge_tenant_id_reservation_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "lease_id"],
            ["lease.tenant_id", "lease.id"],
            name="recurringcharge_tenant_id_lease_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["product.tenant_id", "product.id"],
            name="recurringcharge_tenant_id_product_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "transaction_code_id"],
            ["transactioncode.tenant_id", "transactioncode.id"],
            name="recurringcharge_tenant_id_transaction_code_id_fkey",
        ),
        CheckConstraint(
            "frequency IN ('daily', 'weekly', 'monthly', 'billing_cycle')",
            name="recurringcharge_frequency_check",
        ),
        Index(
            "ix_recurringcharge_due", "tenant_id", "next_run_on", postgresql_where=text("is_active")
        ),
        MIGRATION_ONLY,
    )

    reservation_id: UUID = Field(sa_type=Uuid)
    lease_id: UUID | None = Field(default=None, sa_type=Uuid)
    product_id: UUID | None = Field(default=None, sa_type=Uuid)
    transaction_code_id: UUID = Field(sa_type=Uuid)
    description: str = Field(sa_type=Text)
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    frequency: str = Field(sa_type=Text)
    start_date: dt.date = Field()
    end_date: dt.date | None = Field(default=None)
    next_run_on: dt.date = Field()
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class RecurringChargeCreate(SQLModel):
    """Fields accepted when creating a RecurringCharge."""

    reservation_id: UUID
    lease_id: UUID | None = None
    product_id: UUID | None = None
    transaction_code_id: UUID
    description: str
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    frequency: RecurringChargeFrequency
    start_date: dt.date
    end_date: dt.date | None = None
    next_run_on: dt.date
    is_active: bool = True


class RecurringChargeUpdate(SQLModel):
    """Fields accepted when patching a RecurringCharge (all optional)."""

    reservation_id: UUID | None = None
    lease_id: UUID | None = None
    product_id: UUID | None = None
    transaction_code_id: UUID | None = None
    description: str | None = None
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    frequency: RecurringChargeFrequency | None = None
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    next_run_on: dt.date | None = None
    is_active: bool | None = None


class RecurringChargeRead(SQLModel):
    """Fields returned when reading a RecurringCharge."""

    id: UUID
    tenant_id: UUID
    reservation_id: UUID
    lease_id: UUID | None
    product_id: UUID | None
    transaction_code_id: UUID
    description: str
    amount: Decimal
    frequency: str
    start_date: dt.date
    end_date: dt.date | None
    next_run_on: dt.date
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
