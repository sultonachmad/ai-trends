"""ReservationUnit entity — table ``reservationunit``.

Tenant database, G. Groups & reservations.

One line per unit (room/bed/villa/pitch/slot) in a reservation. The EXCLUDE constraint makes it
impossible to assign the same unit to two overlapping active stays (including turnaround
buffer).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Column,
    Computed,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, TSTZRANGE, ExcludeConstraint
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

ReservationUnitStatus = Literal[
    "quote",
    "tentative",
    "waitlisted",
    "confirmed",
    "guaranteed",
    "in_house",
    "checked_out",
    "cancelled",
    "no_show",
    "expired",
]


class ReservationUnit(TenantEntity, table=True):
    """
    One line per unit (room/bed/villa/pitch/slot) in a reservation. The EXCLUDE constraint makes
    it impossible to assign the same unit to two overlapping active stays (including turnaround
    buffer).
    """

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="reservationunit_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_id"],
            ["reservation.tenant_id", "reservation.id"],
            name="reservationunit_tenant_id_reservation_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="reservationunit_tenant_id_property_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_type_id"],
            ["unittype.tenant_id", "unittype.id"],
            name="reservationunit_tenant_id_unit_type_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["unit.tenant_id", "unit.id"],
            name="reservationunit_tenant_id_unit_id_fkey",
            ondelete="SET NULL (unit_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "rate_plan_id"],
            ["rateplan.tenant_id", "rateplan.id"],
            name="reservationunit_tenant_id_rate_plan_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "upgrade_reason_id"],
            ["reasoncode.tenant_id", "reasoncode.id"],
            name="reservationunit_tenant_id_upgrade_reason_id_fkey",
            ondelete="SET NULL (upgrade_reason_id)",
        ),
        CheckConstraint(
            (
                "status IN ('quote', 'tentative', 'waitlisted', 'confirmed', "
                "'guaranteed', 'in_house', 'checked_out', 'cancelled', 'no_show', "
                "'expired')"
            ),
            name="reservationunit_status_check",
        ),
        CheckConstraint("(adults >= 0)", name="reservationunit_adults_check"),
        CheckConstraint("(children >= 0)", name="reservationunit_children_check"),
        CheckConstraint("(infants >= 0)", name="reservationunit_infants_check"),
        CheckConstraint("(departure_date >= arrival_date)", name="reservationunit_check"),
        CheckConstraint(
            "((end_at > start_at) AND (blocked_until >= end_at))", name="reservationunit_check1"
        ),
        ExcludeConstraint(
            ("unit_id", "="),
            ("occupancy", "&&"),
            using="gist",
            name="ex_reservationunit_no_double_booking",
            where=text(
                "((unit_id IS NOT NULL) AND (status = ANY (ARRAY['tentative'::text, "
                "'confirmed'::text, 'guaranteed'::text, 'in_house'::text])))"
            ),
        ),
        Index("ix_reservationunit_reservation", "tenant_id", "reservation_id"),
        Index(
            "ix_reservationunit_dates", "tenant_id", "property_id", "arrival_date", "departure_date"
        ),
        Index(
            "ix_reservationunit_unit",
            "tenant_id",
            "unit_id",
            postgresql_where=text("unit_id IS NOT NULL"),
        ),
        MIGRATION_ONLY,
    )

    reservation_id: UUID = Field(sa_type=Uuid)
    property_id: UUID = Field(sa_type=Uuid)
    unit_type_id: UUID = Field(sa_type=Uuid)
    unit_id: UUID | None = Field(default=None, sa_type=Uuid, description="NULL until assigned")
    rate_plan_id: UUID = Field(sa_type=Uuid)
    status: str = Field(
        default="confirmed",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'confirmed'::text")},
    )
    arrival_date: dt.date = Field()
    departure_date: dt.date = Field()
    start_at: dt.datetime = utc_datetime_field(
        nullable=False, description="arrival date + check-in time (or hour-block start)"
    )  # type: ignore[assignment]
    end_at: dt.datetime = utc_datetime_field(
        nullable=False, description="departure date + check-out time (or block end)"
    )  # type: ignore[assignment]
    blocked_until: dt.datetime = utc_datetime_field(
        nullable=False, description="end_at + turnaround buffer (set by app)"
    )  # type: ignore[assignment]
    occupancy: Any = Field(
        default=None,
        sa_column=Column(
            "occupancy",
            TSTZRANGE,
            Computed("tstzrange(start_at, blocked_until, '[)'::text)", persisted=True),
        ),
    )
    adults: int = Field(default=1, sa_column_kwargs={"server_default": text("1")})
    children: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})
    infants: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})
    child_ages: list[int] = Field(
        default_factory=list,
        sa_type=ARRAY(Integer),
        sa_column_kwargs={"server_default": text("'{}'::integer[]")},
    )
    is_assignment_locked: bool = Field(
        default=False,
        sa_column_kwargs={"server_default": text("false")},
        description='"do not move"',
    )
    upgrade_reason_id: UUID | None = Field(default=None, sa_type=Uuid)
    total_amount: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("0")},
    )
    checked_in_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    checked_in_by: str | None = Field(default=None, sa_type=Text)
    checked_out_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    checked_out_by: str | None = Field(default=None, sa_type=Text)
    version: int = Field(default=1, sa_column_kwargs={"server_default": text("1")})


class ReservationUnitCreate(SQLModel):
    """Fields accepted when creating a ReservationUnit."""

    reservation_id: UUID
    property_id: UUID
    unit_type_id: UUID
    unit_id: UUID | None = None
    rate_plan_id: UUID
    status: ReservationUnitStatus = "confirmed"
    arrival_date: dt.date
    departure_date: dt.date
    start_at: dt.datetime
    end_at: dt.datetime
    blocked_until: dt.datetime
    adults: int = Field(default=1, ge=0)
    children: int = Field(default=0, ge=0)
    infants: int = Field(default=0, ge=0)
    child_ages: list[int] = Field(default_factory=list)
    is_assignment_locked: bool = False
    upgrade_reason_id: UUID | None = None
    total_amount: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    checked_in_at: dt.datetime | None = None
    checked_in_by: str | None = None
    checked_out_at: dt.datetime | None = None
    checked_out_by: str | None = None


class ReservationUnitUpdate(SQLModel):
    """Fields accepted when patching a ReservationUnit (all optional)."""

    reservation_id: UUID | None = None
    property_id: UUID | None = None
    unit_type_id: UUID | None = None
    unit_id: UUID | None = None
    rate_plan_id: UUID | None = None
    status: ReservationUnitStatus | None = None
    arrival_date: dt.date | None = None
    departure_date: dt.date | None = None
    start_at: dt.datetime | None = None
    end_at: dt.datetime | None = None
    blocked_until: dt.datetime | None = None
    adults: int | None = Field(default=None, ge=0)
    children: int | None = Field(default=None, ge=0)
    infants: int | None = Field(default=None, ge=0)
    child_ages: list[int] | None = None
    is_assignment_locked: bool | None = None
    upgrade_reason_id: UUID | None = None
    total_amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    checked_in_at: dt.datetime | None = None
    checked_in_by: str | None = None
    checked_out_at: dt.datetime | None = None
    checked_out_by: str | None = None


class ReservationUnitRead(SQLModel):
    """Fields returned when reading a ReservationUnit (never returns: occupancy)."""

    id: UUID
    tenant_id: UUID
    reservation_id: UUID
    property_id: UUID
    unit_type_id: UUID
    unit_id: UUID | None
    rate_plan_id: UUID
    status: str
    arrival_date: dt.date
    departure_date: dt.date
    start_at: dt.datetime
    end_at: dt.datetime
    blocked_until: dt.datetime
    adults: int
    children: int
    infants: int
    child_ages: list[int]
    is_assignment_locked: bool
    upgrade_reason_id: UUID | None
    total_amount: Decimal
    checked_in_at: dt.datetime | None
    checked_in_by: str | None
    checked_out_at: dt.datetime | None
    checked_out_by: str | None
    version: int
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
