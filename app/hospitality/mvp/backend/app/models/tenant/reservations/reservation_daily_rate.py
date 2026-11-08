"""ReservationDailyRate entity — table ``reservationdailyrate``.

Tenant database, G. Groups & reservations.

Price per stay date, frozen at booking (BR-04). Night audit posts from here.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field


class ReservationDailyRate(TenantRecord, table=True):
    """Price per stay date, frozen at booking (BR-04). Night audit posts from here."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="reservationdailyrate_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "reservation_unit_id",
            "stay_date",
            name="reservationdailyrate_tenant_id_reservation_unit_id_stay_dat_key",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_unit_id"],
            ["reservationunit.tenant_id", "reservationunit.id"],
            name="reservationdailyrate_tenant_id_reservation_unit_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "rate_plan_id"],
            ["rateplan.tenant_id", "rateplan.id"],
            name="reservationdailyrate_tenant_id_rate_plan_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_type_id"],
            ["unittype.tenant_id", "unittype.id"],
            name="reservationdailyrate_tenant_id_unit_type_id_fkey",
        ),
        CheckConstraint("(amount >= (0)::numeric)", name="reservationdailyrate_amount_check"),
        MIGRATION_ONLY,
    )

    reservation_unit_id: UUID = Field(sa_type=Uuid)
    stay_date: dt.date = Field()
    rate_plan_id: UUID = Field(sa_type=Uuid)
    unit_type_id: UUID = Field(sa_type=Uuid)
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    discount_amount: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    is_price_locked: bool = Field(default=False, sa_column_kwargs={"server_default": text("false")})
    posted_at: dt.datetime | None = utc_datetime_field(
        nullable=True, description="set when night audit posts the charge"
    )  # type: ignore[assignment]


class ReservationDailyRateCreate(SQLModel):
    """Fields accepted when creating a ReservationDailyRate."""

    reservation_unit_id: UUID
    stay_date: dt.date
    rate_plan_id: UUID
    unit_type_id: UUID
    amount: Decimal = Field(max_digits=18, decimal_places=2, ge=0)
    discount_amount: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    is_price_locked: bool = False
    posted_at: dt.datetime | None = None


class ReservationDailyRateUpdate(SQLModel):
    """Fields accepted when patching a ReservationDailyRate (all optional)."""

    reservation_unit_id: UUID | None = None
    stay_date: dt.date | None = None
    rate_plan_id: UUID | None = None
    unit_type_id: UUID | None = None
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2, ge=0)
    discount_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    is_price_locked: bool | None = None
    posted_at: dt.datetime | None = None


class ReservationDailyRateRead(SQLModel):
    """Fields returned when reading a ReservationDailyRate."""

    id: UUID
    tenant_id: UUID
    reservation_unit_id: UUID
    stay_date: dt.date
    rate_plan_id: UUID
    unit_type_id: UUID
    amount: Decimal
    discount_amount: Decimal
    is_price_locked: bool
    posted_at: dt.datetime | None
