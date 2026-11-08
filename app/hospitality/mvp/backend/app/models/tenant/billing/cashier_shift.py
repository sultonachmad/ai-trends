"""CashierShift entity — table ``cashiershift``.

Tenant database, H. Folios, postings, invoices, end-of-day.

Cash drawer per user/shift.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Column,
    Computed,
    ForeignKeyConstraint,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

CashierShiftStatus = Literal[
    "open",
    "closed",
    "reconciled",
]


class CashierShift(TenantEntity, table=True):
    """Cash drawer per user/shift."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="cashiershift_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="cashiershift_tenant_id_property_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "staff_member_id"],
            ["staffmember.tenant_id", "staffmember.id"],
            name="cashiershift_tenant_id_staff_member_id_fkey",
        ),
        CheckConstraint(
            "status IN ('open', 'closed', 'reconciled')", name="cashiershift_status_check"
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    staff_member_id: UUID = Field(sa_type=Uuid)
    outlet_code: str | None = Field(
        default=None, sa_type=Text, description="front desk / bar / shop"
    )
    business_date: dt.date = Field()
    opened_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]
    closed_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    opening_float: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    expected_cash: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    counted_cash: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    variance: Decimal | None = Field(
        default=None,
        sa_column=Column(
            "variance", Numeric(18, 2), Computed("(counted_cash - expected_cash)", persisted=True)
        ),
    )
    status: str = Field(
        default="open", sa_type=Text, sa_column_kwargs={"server_default": text("'open'::text")}
    )
    notes: str | None = Field(default=None, sa_type=Text)


class CashierShiftCreate(SQLModel):
    """Fields accepted when creating a CashierShift."""

    property_id: UUID
    staff_member_id: UUID
    outlet_code: str | None = None
    business_date: dt.date
    opened_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))
    closed_at: dt.datetime | None = None
    opening_float: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    expected_cash: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    counted_cash: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    status: CashierShiftStatus = "open"
    notes: str | None = None


class CashierShiftUpdate(SQLModel):
    """Fields accepted when patching a CashierShift (all optional)."""

    property_id: UUID | None = None
    staff_member_id: UUID | None = None
    outlet_code: str | None = None
    business_date: dt.date | None = None
    opened_at: dt.datetime | None = None
    closed_at: dt.datetime | None = None
    opening_float: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    expected_cash: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    counted_cash: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    status: CashierShiftStatus | None = None
    notes: str | None = None


class CashierShiftRead(SQLModel):
    """Fields returned when reading a CashierShift."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    staff_member_id: UUID
    outlet_code: str | None
    business_date: dt.date
    opened_at: dt.datetime
    closed_at: dt.datetime | None
    opening_float: Decimal
    expected_cash: Decimal | None
    counted_cash: Decimal | None
    variance: Decimal | None
    status: str
    notes: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
