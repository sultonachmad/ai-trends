"""PaymentSchedule entity — table ``paymentschedule``.

Tenant database, I. Payments.

Deposit / balance / instalment schedule (DP 50% culture).

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
    SmallInteger,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

PaymentScheduleStatus = Literal[
    "pending",
    "paid",
    "overdue",
    "failed",
    "waived",
    "cancelled",
]


class PaymentSchedule(TenantEntity, table=True):
    """Deposit / balance / instalment schedule (DP 50% culture)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="paymentschedule_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "reservation_id",
            "sequence",
            name="paymentschedule_tenant_id_reservation_id_sequence_key",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_id"],
            ["reservation.tenant_id", "reservation.id"],
            name="paymentschedule_tenant_id_reservation_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "instrument_id"],
            ["paymentinstrument.tenant_id", "paymentinstrument.id"],
            name="paymentschedule_tenant_id_instrument_id_fkey",
            ondelete="SET NULL (instrument_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "payment_link_id"],
            ["paymentlink.tenant_id", "paymentlink.id"],
            name="paymentschedule_tenant_id_payment_link_id_fkey",
            ondelete="SET NULL (payment_link_id)",
        ),
        CheckConstraint("(amount > (0)::numeric)", name="paymentschedule_amount_check"),
        CheckConstraint(
            ("status IN ('pending', 'paid', 'overdue', 'failed', 'waived', 'cancelled')"),
            name="paymentschedule_status_check",
        ),
        Index(
            "ix_paymentschedule_due",
            "tenant_id",
            "due_at",
            postgresql_where=text(
                "status = ANY (ARRAY['pending'::text, 'overdue'::text, 'failed'::text])"
            ),
        ),
        MIGRATION_ONLY,
    )

    reservation_id: UUID = Field(sa_type=Uuid)
    sequence: int = Field(sa_type=SmallInteger)
    due_at: dt.datetime = utc_datetime_field(nullable=False)  # type: ignore[assignment]
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    description: str | None = Field(default=None, sa_type=Text)
    auto_charge: bool = Field(default=False, sa_column_kwargs={"server_default": text("false")})
    instrument_id: UUID | None = Field(default=None, sa_type=Uuid)
    payment_link_id: UUID | None = Field(default=None, sa_type=Uuid)
    status: str = Field(
        default="pending",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'pending'::text")},
    )
    attempts: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})
    last_attempt_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]


class PaymentScheduleCreate(SQLModel):
    """Fields accepted when creating a PaymentSchedule."""

    reservation_id: UUID
    sequence: int
    due_at: dt.datetime
    amount: Decimal = Field(max_digits=18, decimal_places=2, gt=0)
    description: str | None = None
    auto_charge: bool = False
    instrument_id: UUID | None = None
    payment_link_id: UUID | None = None
    status: PaymentScheduleStatus = "pending"
    attempts: int = 0
    last_attempt_at: dt.datetime | None = None


class PaymentScheduleUpdate(SQLModel):
    """Fields accepted when patching a PaymentSchedule (all optional)."""

    reservation_id: UUID | None = None
    sequence: int | None = None
    due_at: dt.datetime | None = None
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2, gt=0)
    description: str | None = None
    auto_charge: bool | None = None
    instrument_id: UUID | None = None
    payment_link_id: UUID | None = None
    status: PaymentScheduleStatus | None = None
    attempts: int | None = None
    last_attempt_at: dt.datetime | None = None


class PaymentScheduleRead(SQLModel):
    """Fields returned when reading a PaymentSchedule."""

    id: UUID
    tenant_id: UUID
    reservation_id: UUID
    sequence: int
    due_at: dt.datetime
    amount: Decimal
    description: str | None
    auto_charge: bool
    instrument_id: UUID | None
    payment_link_id: UUID | None
    status: str
    attempts: int
    last_attempt_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
