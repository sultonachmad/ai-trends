"""ServiceBooking entity — table ``servicebooking``.

Tenant database, Q. Ancillary / POS lite.

Bookable services (spa, tours, transfers, equipment) in time slots.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

ServiceBookingStatus = Literal[
    "booked",
    "completed",
    "cancelled",
    "no_show",
]


class ServiceBooking(TenantEntity, table=True):
    """Bookable services (spa, tours, transfers, equipment) in time slots."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="servicebooking_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="servicebooking_tenant_id_property_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["product.tenant_id", "product.id"],
            name="servicebooking_tenant_id_product_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "guest_id"],
            ["guest.tenant_id", "guest.id"],
            name="servicebooking_tenant_id_guest_id_fkey",
            ondelete="SET NULL (guest_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_id"],
            ["reservation.tenant_id", "reservation.id"],
            name="servicebooking_tenant_id_reservation_id_fkey",
            ondelete="SET NULL (reservation_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "folio_transaction_id"],
            ["foliotransaction.tenant_id", "foliotransaction.id"],
            name="servicebooking_tenant_id_folio_transaction_id_fkey",
        ),
        CheckConstraint(
            "status IN ('booked', 'completed', 'cancelled', 'no_show')",
            name="servicebooking_status_check",
        ),
        CheckConstraint("(end_at > start_at)", name="servicebooking_check"),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    product_id: UUID = Field(sa_type=Uuid)
    resource_label: str | None = Field(
        default=None, sa_type=Text, description="therapist / guide / vehicle"
    )
    start_at: dt.datetime = utc_datetime_field(nullable=False)  # type: ignore[assignment]
    end_at: dt.datetime = utc_datetime_field(nullable=False)  # type: ignore[assignment]
    guest_id: UUID | None = Field(default=None, sa_type=Uuid)
    reservation_id: UUID | None = Field(default=None, sa_type=Uuid)
    participants: int = Field(default=1, sa_column_kwargs={"server_default": text("1")})
    status: str = Field(
        default="booked", sa_type=Text, sa_column_kwargs={"server_default": text("'booked'::text")}
    )
    folio_transaction_id: UUID | None = Field(default=None, sa_type=Uuid)


class ServiceBookingCreate(SQLModel):
    """Fields accepted when creating a ServiceBooking."""

    property_id: UUID
    product_id: UUID
    resource_label: str | None = None
    start_at: dt.datetime
    end_at: dt.datetime
    guest_id: UUID | None = None
    reservation_id: UUID | None = None
    participants: int = 1
    status: ServiceBookingStatus = "booked"
    folio_transaction_id: UUID | None = None


class ServiceBookingUpdate(SQLModel):
    """Fields accepted when patching a ServiceBooking (all optional)."""

    property_id: UUID | None = None
    product_id: UUID | None = None
    resource_label: str | None = None
    start_at: dt.datetime | None = None
    end_at: dt.datetime | None = None
    guest_id: UUID | None = None
    reservation_id: UUID | None = None
    participants: int | None = None
    status: ServiceBookingStatus | None = None
    folio_transaction_id: UUID | None = None


class ServiceBookingRead(SQLModel):
    """Fields returned when reading a ServiceBooking."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    product_id: UUID
    resource_label: str | None
    start_at: dt.datetime
    end_at: dt.datetime
    guest_id: UUID | None
    reservation_id: UUID | None
    participants: int
    status: str
    folio_transaction_id: UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
