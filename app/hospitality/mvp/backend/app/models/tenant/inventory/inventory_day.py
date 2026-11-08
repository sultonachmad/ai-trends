"""InventoryDay entity — table ``inventoryday``.

Tenant database, C. Inventory.

Per unit-type per date availability counters. Booking flows lock the row (SELECT … FOR UPDATE)
and bump `sold`; channel overbookings are allowed and flagged by the application, so there is no
hard capacity CHECK here.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Column,
    Computed,
    ForeignKeyConstraint,
    Index,
    Integer,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field


class InventoryDay(TenantRecord, table=True):
    """
    Per unit-type per date availability counters. Booking flows lock the row (SELECT … FOR
    UPDATE) and bump `sold`; channel overbookings are allowed and flagged by the application, so
    there is no hard capacity CHECK here.
    """

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="inventoryday_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "unit_type_id",
            "stay_date",
            name="inventoryday_tenant_id_unit_type_id_stay_date_key",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="inventoryday_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_type_id"],
            ["unittype.tenant_id", "unittype.id"],
            name="inventoryday_tenant_id_unit_type_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint("(physical >= 0)", name="inventoryday_physical_check"),
        CheckConstraint("(sold >= 0)", name="inventoryday_sold_check"),
        CheckConstraint("(blocked >= 0)", name="inventoryday_blocked_check"),
        CheckConstraint("(out_of_order >= 0)", name="inventoryday_out_of_order_check"),
        CheckConstraint("(overbook_limit >= 0)", name="inventoryday_overbook_limit_check"),
        Index("ix_inventoryday_property_date", "tenant_id", "property_id", "stay_date"),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    unit_type_id: UUID = Field(sa_type=Uuid)
    stay_date: dt.date = Field()
    physical: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})
    sold: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})
    blocked: int = Field(
        default=0,
        sa_column_kwargs={"server_default": text("0")},
        description="group/allotment holds",
    )
    out_of_order: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})
    overbook_limit: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})
    available: int | None = Field(
        default=None,
        sa_column=Column(
            "available",
            Integer,
            Computed(
                "((((physical + overbook_limit) - sold) - blocked) - out_of_order)", persisted=True
            ),
        ),
    )
    version: int = Field(default=1, sa_column_kwargs={"server_default": text("1")})
    updated_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, onupdate_now=True, server_default_now=True
    )  # type: ignore[assignment]


class InventoryDayCreate(SQLModel):
    """Fields accepted when creating a InventoryDay."""

    property_id: UUID
    unit_type_id: UUID
    stay_date: dt.date
    physical: int = Field(default=0, ge=0)
    sold: int = Field(default=0, ge=0)
    blocked: int = Field(default=0, ge=0)
    out_of_order: int = Field(default=0, ge=0)
    overbook_limit: int = Field(default=0, ge=0)


class InventoryDayUpdate(SQLModel):
    """Fields accepted when patching a InventoryDay (all optional)."""

    property_id: UUID | None = None
    unit_type_id: UUID | None = None
    stay_date: dt.date | None = None
    physical: int | None = Field(default=None, ge=0)
    sold: int | None = Field(default=None, ge=0)
    blocked: int | None = Field(default=None, ge=0)
    out_of_order: int | None = Field(default=None, ge=0)
    overbook_limit: int | None = Field(default=None, ge=0)


class InventoryDayRead(SQLModel):
    """Fields returned when reading a InventoryDay."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    unit_type_id: UUID
    stay_date: dt.date
    physical: int
    sold: int
    blocked: int
    out_of_order: int
    overbook_limit: int
    available: int | None
    version: int
    updated_at: dt.datetime
