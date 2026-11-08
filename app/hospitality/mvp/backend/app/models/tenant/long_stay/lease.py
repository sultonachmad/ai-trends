"""Lease entity — table ``lease``.

Tenant database, O. Long stay, kos & leases.

Kos / serviced-apartment leases and recurring billing.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    ForeignKeyConstraint,
    SmallInteger,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

LeaseStatus = Literal[
    "draft",
    "signed",
    "active",
    "notice_given",
    "ended",
    "settled",
    "cancelled",
]
LeaseBillingCycle = Literal[
    "weekly",
    "monthly",
    "quarterly",
    "yearly",
    "custom",
]


class Lease(TenantEntity, table=True):
    """Kos / serviced-apartment leases and recurring billing."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="lease_tenant_id_id_key"),
        UniqueConstraint("tenant_id", "reservation_id", name="lease_tenant_id_reservation_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="lease_tenant_id_property_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_id"],
            ["reservation.tenant_id", "reservation.id"],
            name="lease_tenant_id_reservation_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "resident_guest_id"],
            ["guest.tenant_id", "guest.id"],
            name="lease_tenant_id_resident_guest_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "payer_guest_id"],
            ["guest.tenant_id", "guest.id"],
            name="lease_tenant_id_payer_guest_id_fkey",
            ondelete="SET NULL (payer_guest_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "payer_account_id"],
            ["account.tenant_id", "account.id"],
            name="lease_tenant_id_payer_account_id_fkey",
            ondelete="SET NULL (payer_account_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "contract_document_id"],
            ["document.tenant_id", "document.id"],
            name="lease_tenant_id_contract_document_id_fkey",
            ondelete="SET NULL (contract_document_id)",
        ),
        CheckConstraint(
            (
                "status IN ('draft', 'signed', 'active', 'notice_given', 'ended', "
                "'settled', 'cancelled')"
            ),
            name="lease_status_check",
        ),
        CheckConstraint(
            "billing_cycle IN ('weekly', 'monthly', 'quarterly', 'yearly', 'custom')",
            name="lease_billing_cycle_check",
        ),
        CheckConstraint(
            "((billing_day >= 1) AND (billing_day <= 28))", name="lease_billing_day_check"
        ),
        CheckConstraint("(rent_amount >= (0)::numeric)", name="lease_rent_amount_check"),
        CheckConstraint("((end_date IS NULL) OR (end_date > start_date))", name="lease_check"),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    reservation_id: UUID = Field(
        sa_type=Uuid, description="the long-stay reservation that holds the unit"
    )
    resident_guest_id: UUID = Field(sa_type=Uuid)
    payer_guest_id: UUID | None = Field(
        default=None, sa_type=Uuid, description="e.g. parent paying for a student"
    )
    payer_account_id: UUID | None = Field(default=None, sa_type=Uuid)
    status: str = Field(
        default="draft", sa_type=Text, sa_column_kwargs={"server_default": text("'draft'::text")}
    )
    start_date: dt.date = Field()
    end_date: dt.date | None = Field(default=None, description="NULL = open-ended")
    notice_days: int = Field(default=30, sa_column_kwargs={"server_default": text("30")})
    billing_cycle: str = Field(
        default="monthly",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'monthly'::text")},
    )
    billing_day: int | None = Field(default=None, sa_type=SmallInteger)
    rent_amount: Decimal = Field(max_digits=18, decimal_places=2)
    currency: str = Field(
        default="IDR", sa_type=CHAR(3), sa_column_kwargs={"server_default": text("'IDR'::bpchar")}
    )
    deposit_amount: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    deposit_held: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    included_utilities: list[str] = Field(
        default_factory=list,
        sa_type=ARRAY(Text),
        sa_column_kwargs={"server_default": text("'{}'::text[]")},
        description="'water','wifi','electricity'",
    )
    house_rules_version: str | None = Field(default=None, sa_type=Text)
    contract_document_id: UUID | None = Field(default=None, sa_type=Uuid)
    signed_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    notice_given_on: dt.date | None = Field(default=None)
    move_out_on: dt.date | None = Field(default=None)


class LeaseCreate(SQLModel):
    """Fields accepted when creating a Lease."""

    property_id: UUID
    reservation_id: UUID
    resident_guest_id: UUID
    payer_guest_id: UUID | None = None
    payer_account_id: UUID | None = None
    status: LeaseStatus = "draft"
    start_date: dt.date
    end_date: dt.date | None = None
    notice_days: int = 30
    billing_cycle: LeaseBillingCycle = "monthly"
    billing_day: int | None = Field(default=None, ge=1, le=28)
    rent_amount: Decimal = Field(max_digits=18, decimal_places=2, ge=0)
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    deposit_amount: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    deposit_held: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    included_utilities: list[str] = Field(default_factory=list)
    house_rules_version: str | None = None
    contract_document_id: UUID | None = None
    signed_at: dt.datetime | None = None
    notice_given_on: dt.date | None = None
    move_out_on: dt.date | None = None


class LeaseUpdate(SQLModel):
    """Fields accepted when patching a Lease (all optional)."""

    property_id: UUID | None = None
    reservation_id: UUID | None = None
    resident_guest_id: UUID | None = None
    payer_guest_id: UUID | None = None
    payer_account_id: UUID | None = None
    status: LeaseStatus | None = None
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    notice_days: int | None = None
    billing_cycle: LeaseBillingCycle | None = None
    billing_day: int | None = Field(default=None, ge=1, le=28)
    rent_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    deposit_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    deposit_held: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    included_utilities: list[str] | None = None
    house_rules_version: str | None = None
    contract_document_id: UUID | None = None
    signed_at: dt.datetime | None = None
    notice_given_on: dt.date | None = None
    move_out_on: dt.date | None = None


class LeaseRead(SQLModel):
    """Fields returned when reading a Lease."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    reservation_id: UUID
    resident_guest_id: UUID
    payer_guest_id: UUID | None
    payer_account_id: UUID | None
    status: str
    start_date: dt.date
    end_date: dt.date | None
    notice_days: int
    billing_cycle: str
    billing_day: int | None
    rent_amount: Decimal
    currency: str
    deposit_amount: Decimal
    deposit_held: Decimal
    included_utilities: list[str]
    house_rules_version: str | None
    contract_document_id: UUID | None
    signed_at: dt.datetime | None
    notice_given_on: dt.date | None
    move_out_on: dt.date | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
