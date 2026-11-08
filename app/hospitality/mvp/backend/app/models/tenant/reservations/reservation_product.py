"""ReservationProduct entity — table ``reservationproduct``.

Tenant database, G. Groups & reservations.

Extras booked with the stay (breakfast, parking, cot, transfer …).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

ReservationProductStatus = Literal[
    "active",
    "cancelled",
    "consumed",
]


class ReservationProduct(TenantEntity, table=True):
    """Extras booked with the stay (breakfast, parking, cot, transfer …)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="reservationproduct_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_id"],
            ["reservation.tenant_id", "reservation.id"],
            name="reservationproduct_tenant_id_reservation_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_unit_id"],
            ["reservationunit.tenant_id", "reservationunit.id"],
            name="reservationproduct_tenant_id_reservation_unit_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["product.tenant_id", "product.id"],
            name="reservationproduct_tenant_id_product_id_fkey",
        ),
        CheckConstraint("(quantity > (0)::numeric)", name="reservationproduct_quantity_check"),
        CheckConstraint("(unit_price >= (0)::numeric)", name="reservationproduct_unit_price_check"),
        CheckConstraint(
            "status IN ('active', 'cancelled', 'consumed')", name="reservationproduct_status_check"
        ),
        MIGRATION_ONLY,
    )

    reservation_id: UUID = Field(sa_type=Uuid)
    reservation_unit_id: UUID | None = Field(default=None, sa_type=Uuid)
    product_id: UUID = Field(sa_type=Uuid)
    quantity: Decimal = Field(
        default=Decimal("1"),
        max_digits=10,
        decimal_places=2,
        sa_column_kwargs={"server_default": text("1")},
    )
    unit_price: Decimal = Field(max_digits=18, decimal_places=2)
    start_date: dt.date | None = Field(default=None)
    end_date: dt.date | None = Field(default=None)
    is_included_in_rate: bool = Field(
        default=False, sa_column_kwargs={"server_default": text("false")}
    )
    status: str = Field(
        default="active", sa_type=Text, sa_column_kwargs={"server_default": text("'active'::text")}
    )


class ReservationProductCreate(SQLModel):
    """Fields accepted when creating a ReservationProduct."""

    reservation_id: UUID
    reservation_unit_id: UUID | None = None
    product_id: UUID
    quantity: Decimal = Field(default=Decimal("1"), max_digits=10, decimal_places=2, gt=0)
    unit_price: Decimal = Field(max_digits=18, decimal_places=2, ge=0)
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    is_included_in_rate: bool = False
    status: ReservationProductStatus = "active"


class ReservationProductUpdate(SQLModel):
    """Fields accepted when patching a ReservationProduct (all optional)."""

    reservation_id: UUID | None = None
    reservation_unit_id: UUID | None = None
    product_id: UUID | None = None
    quantity: Decimal | None = Field(default=None, max_digits=10, decimal_places=2, gt=0)
    unit_price: Decimal | None = Field(default=None, max_digits=18, decimal_places=2, ge=0)
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    is_included_in_rate: bool | None = None
    status: ReservationProductStatus | None = None


class ReservationProductRead(SQLModel):
    """Fields returned when reading a ReservationProduct."""

    id: UUID
    tenant_id: UUID
    reservation_id: UUID
    reservation_unit_id: UUID | None
    product_id: UUID
    quantity: Decimal
    unit_price: Decimal
    start_date: dt.date | None
    end_date: dt.date | None
    is_included_in_rate: bool
    status: str
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
