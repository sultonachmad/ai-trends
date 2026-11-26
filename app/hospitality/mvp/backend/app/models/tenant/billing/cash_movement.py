"""CashMovement entity — table ``cashmovement``.

Tenant database, billing.

Money that left the property outside a booking's payments: refunds sent back to guests
and paid-outs (petty cash). Cash movements of today belong to the drawer of the person
who recorded them. Rows are never changed; a mistake is answered by a new row.

Created by migration 0019.
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

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field

CashMovementKind = Literal["refund", "paid_out"]
CashMovementMethod = Literal["cash", "bank_transfer", "other"]


class CashMovement(TenantRecord, table=True):
    """A refund or a paid-out."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="cashmovement_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="cashmovement_tenant_id_property_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "cashier_shift_id"],
            ["cashiershift.tenant_id", "cashiershift.id"],
            name="cashmovement_tenant_id_cashier_shift_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_id"],
            ["reservation.tenant_id", "reservation.id"],
            name="cashmovement_tenant_id_reservation_id_fkey",
        ),
        CheckConstraint("kind IN ('refund', 'paid_out')", name="cashmovement_kind_check"),
        CheckConstraint(
            "method IN ('cash', 'bank_transfer', 'other')", name="cashmovement_method_check"
        ),
        CheckConstraint("amount > 0", name="cashmovement_amount_check"),
        Index("ix_cashmovement_day", "tenant_id", "property_id", "occurred_at"),
        Index(
            "ix_cashmovement_reservation",
            "tenant_id",
            "reservation_id",
            postgresql_where=text("reservation_id IS NOT NULL"),
        ),
        Index(
            "ix_cashmovement_shift",
            "tenant_id",
            "cashier_shift_id",
            postgresql_where=text("cashier_shift_id IS NOT NULL"),
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    cashier_shift_id: UUID | None = Field(default=None, sa_type=Uuid)
    reservation_id: UUID | None = Field(default=None, sa_type=Uuid)
    kind: str = Field(sa_type=Text)
    method: str = Field(sa_type=Text)
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    occurred_at: dt.datetime = utc_datetime_field(nullable=False)  # type: ignore[assignment]
    reason: str | None = Field(default=None, sa_type=Text)
    recorded_by: str = Field(sa_type=Text)
    created_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]


class CashMovementCreate(SQLModel):
    """Fields accepted when creating a CashMovement."""

    property_id: UUID
    cashier_shift_id: UUID | None = None
    reservation_id: UUID | None = None
    kind: CashMovementKind
    method: CashMovementMethod
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    occurred_at: dt.datetime
    reason: str | None = None
    recorded_by: str


class CashMovementUpdate(SQLModel):
    """Cash movements are never changed; a mistake is answered by a new row."""


class CashMovementRead(SQLModel):
    """Fields returned when reading a CashMovement."""

    id: UUID
    property_id: UUID
    cashier_shift_id: UUID | None
    reservation_id: UUID | None
    kind: str
    method: str
    amount: Decimal
    occurred_at: dt.datetime
    reason: str | None
    recorded_by: str
    created_at: dt.datetime
