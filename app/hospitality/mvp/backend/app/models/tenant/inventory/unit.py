"""Unit entity — table ``unit``.

Tenant database, C. Inventory.

Physical, assignable unit. parent_unit_id models beds-in-a-dorm and bedrooms-in-a-villa
(combinable units).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Any, Literal
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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

UnitGenderRestriction = Literal[
    "male",
    "female",
    "mixed",
]
UnitHkStatus = Literal[
    "dirty",
    "in_progress",
    "clean",
    "inspected",
]
UnitFoStatus = Literal[
    "vacant",
    "occupied",
]
UnitServiceStatus = Literal[
    "in_service",
    "out_of_order",
    "out_of_service",
]


class Unit(TenantEntity, table=True):
    """
    Physical, assignable unit. parent_unit_id models beds-in-a-dorm and bedrooms-in-a-villa
    (combinable units).
    """

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="unit_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id", "property_id", "code", name="unit_tenant_id_property_id_code_key"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="unit_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_type_id"],
            ["unittype.tenant_id", "unittype.id"],
            name="unit_tenant_id_unit_type_id_fkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "area_id"],
            ["propertyarea.tenant_id", "propertyarea.id"],
            name="unit_tenant_id_area_id_fkey",
            ondelete="SET NULL (area_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "parent_unit_id"],
            ["unit.tenant_id", "unit.id"],
            name="unit_tenant_id_parent_unit_id_fkey",
            ondelete="SET NULL (parent_unit_id)",
        ),
        CheckConstraint(
            "gender_restriction IN ('male', 'female', 'mixed')",
            name="unit_gender_restriction_check",
        ),
        CheckConstraint(
            "hk_status IN ('dirty', 'in_progress', 'clean', 'inspected')",
            name="unit_hk_status_check",
        ),
        CheckConstraint("fo_status IN ('vacant', 'occupied')", name="unit_fo_status_check"),
        CheckConstraint(
            "service_status IN ('in_service', 'out_of_order', 'out_of_service')",
            name="unit_service_status_check",
        ),
        CheckConstraint("((parent_unit_id IS NULL) OR (parent_unit_id <> id))", name="unit_check"),
        Index("ix_unit_type", "tenant_id", "unit_type_id"),
        Index(
            "ix_unit_parent",
            "tenant_id",
            "parent_unit_id",
            postgresql_where=text("parent_unit_id IS NOT NULL"),
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    unit_type_id: UUID = Field(sa_type=Uuid)
    area_id: UUID | None = Field(default=None, sa_type=Uuid)
    parent_unit_id: UUID | None = Field(default=None, sa_type=Uuid)
    code: str = Field(sa_type=Text, description="room number / bed label / pitch no.")
    name: str | None = Field(default=None, sa_type=Text)
    floor: str | None = Field(default=None, sa_type=Text)
    features: list[str] = Field(
        default_factory=list,
        sa_type=ARRAY(Text),
        sa_column_kwargs={"server_default": text("'{}'::text[]")},
        description="'sea_view','smoking','pet_friendly','connecting'",
    )
    is_accessible: bool = Field(default=False, sa_column_kwargs={"server_default": text("false")})
    is_sellable: bool = Field(
        default=True,
        sa_column_kwargs={"server_default": text("true")},
        description="false = staff/owner/model unit",
    )
    gender_restriction: str | None = Field(default=None, sa_type=Text)
    max_vehicle_length_m: Decimal | None = Field(
        default=None, max_digits=4, decimal_places=1, description="pitches / berths"
    )
    hookups: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description='{"electric_amp":16,"water":true}',
    )
    hk_status: str = Field(
        default="clean", sa_type=Text, sa_column_kwargs={"server_default": text("'clean'::text")}
    )
    fo_status: str = Field(
        default="vacant", sa_type=Text, sa_column_kwargs={"server_default": text("'vacant'::text")}
    )
    service_status: str = Field(
        default="in_service",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'in_service'::text")},
    )
    hk_status_changed_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    sort_order: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class UnitCreate(SQLModel):
    """Fields accepted when creating a Unit."""

    property_id: UUID
    unit_type_id: UUID
    area_id: UUID | None = None
    parent_unit_id: UUID | None = None
    code: str
    name: str | None = None
    floor: str | None = None
    features: list[str] = Field(default_factory=list)
    is_accessible: bool = False
    is_sellable: bool = True
    gender_restriction: UnitGenderRestriction | None = None
    max_vehicle_length_m: Decimal | None = Field(default=None, max_digits=4, decimal_places=1)
    hookups: dict[str, Any] = Field(default_factory=dict)
    hk_status: UnitHkStatus = "clean"
    fo_status: UnitFoStatus = "vacant"
    service_status: UnitServiceStatus = "in_service"
    hk_status_changed_at: dt.datetime | None = None
    sort_order: int = 0
    is_active: bool = True


class UnitUpdate(SQLModel):
    """Fields accepted when patching a Unit (all optional)."""

    property_id: UUID | None = None
    unit_type_id: UUID | None = None
    area_id: UUID | None = None
    parent_unit_id: UUID | None = None
    code: str | None = None
    name: str | None = None
    floor: str | None = None
    features: list[str] | None = None
    is_accessible: bool | None = None
    is_sellable: bool | None = None
    gender_restriction: UnitGenderRestriction | None = None
    max_vehicle_length_m: Decimal | None = Field(default=None, max_digits=4, decimal_places=1)
    hookups: dict[str, Any] | None = None
    hk_status: UnitHkStatus | None = None
    fo_status: UnitFoStatus | None = None
    service_status: UnitServiceStatus | None = None
    hk_status_changed_at: dt.datetime | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class UnitRead(SQLModel):
    """Fields returned when reading a Unit."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    unit_type_id: UUID
    area_id: UUID | None
    parent_unit_id: UUID | None
    code: str
    name: str | None
    floor: str | None
    features: list[str]
    is_accessible: bool
    is_sellable: bool
    gender_restriction: str | None
    max_vehicle_length_m: Decimal | None
    hookups: dict[str, Any]
    hk_status: str
    fo_status: str
    service_status: str
    hk_status_changed_at: dt.datetime | None
    sort_order: int
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
