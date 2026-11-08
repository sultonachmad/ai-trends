"""ReservationGuest entity — table ``reservationguest``.

Tenant database, G. Groups & reservations.

Occupants per reservation unit.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
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

ReservationGuestAgeCategory = Literal[
    "adult",
    "teen",
    "child",
    "infant",
]
ReservationGuestRegistrationStatus = Literal[
    "pending",
    "pre_checked_in",
    "registered",
]


class ReservationGuest(TenantEntity, table=True):
    """Occupants per reservation unit."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="reservationguest_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "reservation_unit_id",
            "guest_id",
            name="reservationguest_tenant_id_reservation_unit_id_guest_id_key",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_unit_id"],
            ["reservationunit.tenant_id", "reservationunit.id"],
            name="reservationguest_tenant_id_reservation_unit_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "guest_id"],
            ["guest.tenant_id", "guest.id"],
            name="reservationguest_tenant_id_guest_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "registration_card_id"],
            ["document.tenant_id", "document.id"],
            name="reservationguest_tenant_id_registration_card_id_fkey",
            ondelete="SET NULL (registration_card_id)",
        ),
        CheckConstraint(
            "age_category IN ('adult', 'teen', 'child', 'infant')",
            name="reservationguest_age_category_check",
        ),
        CheckConstraint(
            "registration_status IN ('pending', 'pre_checked_in', 'registered')",
            name="reservationguest_registration_status_check",
        ),
        Index(
            "ux_reservationguest_primary",
            "tenant_id",
            "reservation_unit_id",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
        MIGRATION_ONLY,
    )

    reservation_unit_id: UUID = Field(sa_type=Uuid)
    guest_id: UUID = Field(sa_type=Uuid)
    is_primary: bool = Field(default=False, sa_column_kwargs={"server_default": text("false")})
    age_category: str = Field(
        default="adult", sa_type=Text, sa_column_kwargs={"server_default": text("'adult'::text")}
    )
    registration_status: str = Field(
        default="pending",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'pending'::text")},
    )
    registration_card_id: UUID | None = Field(
        default=None, sa_type=Uuid, description="signed card (document)"
    )


class ReservationGuestCreate(SQLModel):
    """Fields accepted when creating a ReservationGuest."""

    reservation_unit_id: UUID
    guest_id: UUID
    is_primary: bool = False
    age_category: ReservationGuestAgeCategory = "adult"
    registration_status: ReservationGuestRegistrationStatus = "pending"
    registration_card_id: UUID | None = None


class ReservationGuestUpdate(SQLModel):
    """Fields accepted when patching a ReservationGuest (all optional)."""

    reservation_unit_id: UUID | None = None
    guest_id: UUID | None = None
    is_primary: bool | None = None
    age_category: ReservationGuestAgeCategory | None = None
    registration_status: ReservationGuestRegistrationStatus | None = None
    registration_card_id: UUID | None = None


class ReservationGuestRead(SQLModel):
    """Fields returned when reading a ReservationGuest."""

    id: UUID
    tenant_id: UUID
    reservation_unit_id: UUID
    guest_id: UUID
    is_primary: bool
    age_category: str
    registration_status: str
    registration_card_id: UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
