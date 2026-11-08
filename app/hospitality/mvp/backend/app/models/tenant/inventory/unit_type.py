"""UnitType entity — table ``unittype``.

Tenant database, C. Inventory.

Category (room, bed, villa, pitch …), time grain (night/day/hour/month), occupancy.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

UnitTypeCategory = Literal[
    "room",
    "bed",
    "apartment",
    "villa",
    "pitch",
    "cabin",
    "pod",
    "berth",
    "space",
    "other",
]
UnitTypeSellMode = Literal[
    "unit",
    "bed",
]
UnitTypeTimeGrain = Literal[
    "night",
    "day",
    "hour_block",
    "month",
]
UnitTypeGenderPolicy = Literal[
    "any",
    "male",
    "female",
    "mixed",
]


class UnitType(TenantEntity, table=True):
    """Category (room, bed, villa, pitch …), time grain (night/day/hour/month), occupancy."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="unittype_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id", "property_id", "code", name="unittype_tenant_id_property_id_code_key"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="unittype_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            (
                "category IN ('room', 'bed', 'apartment', 'villa', 'pitch', 'cabin', "
                "'pod', 'berth', 'space', 'other')"
            ),
            name="unittype_category_check",
        ),
        CheckConstraint("sell_mode IN ('unit', 'bed')", name="unittype_sell_mode_check"),
        CheckConstraint(
            "time_grain IN ('night', 'day', 'hour_block', 'month')",
            name="unittype_time_grain_check",
        ),
        CheckConstraint("(hour_block_minutes > 0)", name="unittype_hour_block_minutes_check"),
        CheckConstraint("(turnaround_minutes >= 0)", name="unittype_turnaround_minutes_check"),
        CheckConstraint("(base_occupancy > 0)", name="unittype_base_occupancy_check"),
        CheckConstraint("(max_adults > 0)", name="unittype_max_adults_check"),
        CheckConstraint("(max_children >= 0)", name="unittype_max_children_check"),
        CheckConstraint("(max_occupancy > 0)", name="unittype_max_occupancy_check"),
        CheckConstraint(
            "gender_policy IN ('any', 'male', 'female', 'mixed')",
            name="unittype_gender_policy_check",
        ),
        CheckConstraint(
            "((time_grain <> 'hour_block'::text) OR (hour_block_minutes IS NOT NULL))",
            name="unittype_check",
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    code: str = Field(sa_type=Text)
    name: str = Field(sa_type=Text)
    category: str = Field(sa_type=Text)
    sell_mode: str = Field(
        default="unit",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'unit'::text")},
        description="bed = dorm sold per bed",
    )
    time_grain: str = Field(
        default="night", sa_type=Text, sa_column_kwargs={"server_default": text("'night'::text")}
    )
    hour_block_minutes: int | None = Field(default=None)
    turnaround_minutes: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})
    base_occupancy: int = Field(default=2, sa_column_kwargs={"server_default": text("2")})
    max_adults: int = Field(default=2, sa_column_kwargs={"server_default": text("2")})
    max_children: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})
    max_occupancy: int = Field(default=2, sa_column_kwargs={"server_default": text("2")})
    gender_policy: str = Field(
        default="any", sa_type=Text, sa_column_kwargs={"server_default": text("'any'::text")}
    )
    bed_config: list[Any] = Field(
        default_factory=list,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'[]'::jsonb")},
        description='[{"type":"king","count":1}]',
    )
    size_sqm: Decimal | None = Field(default=None, max_digits=7, decimal_places=2)
    amenities: list[str] = Field(
        default_factory=list,
        sa_type=ARRAY(Text),
        sa_column_kwargs={"server_default": text("'{}'::text[]")},
    )
    content: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description="multilingual name/description/photos",
    )
    is_virtual: bool = Field(
        default=False,
        sa_column_kwargs={"server_default": text("false")},
        description="run-of-house",
    )
    sort_order: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class UnitTypeCreate(SQLModel):
    """Fields accepted when creating a UnitType."""

    property_id: UUID
    code: str
    name: str
    category: UnitTypeCategory
    sell_mode: UnitTypeSellMode = "unit"
    time_grain: UnitTypeTimeGrain = "night"
    hour_block_minutes: int | None = Field(default=None, gt=0)
    turnaround_minutes: int = Field(default=0, ge=0)
    base_occupancy: int = Field(default=2, gt=0)
    max_adults: int = Field(default=2, gt=0)
    max_children: int = Field(default=0, ge=0)
    max_occupancy: int = Field(default=2, gt=0)
    gender_policy: UnitTypeGenderPolicy = "any"
    bed_config: list[Any] = Field(default_factory=list)
    size_sqm: Decimal | None = Field(default=None, max_digits=7, decimal_places=2)
    amenities: list[str] = Field(default_factory=list)
    content: dict[str, Any] = Field(default_factory=dict)
    is_virtual: bool = False
    sort_order: int = 0
    is_active: bool = True


class UnitTypeUpdate(SQLModel):
    """Fields accepted when patching a UnitType (all optional)."""

    property_id: UUID | None = None
    code: str | None = None
    name: str | None = None
    category: UnitTypeCategory | None = None
    sell_mode: UnitTypeSellMode | None = None
    time_grain: UnitTypeTimeGrain | None = None
    hour_block_minutes: int | None = Field(default=None, gt=0)
    turnaround_minutes: int | None = Field(default=None, ge=0)
    base_occupancy: int | None = Field(default=None, gt=0)
    max_adults: int | None = Field(default=None, gt=0)
    max_children: int | None = Field(default=None, ge=0)
    max_occupancy: int | None = Field(default=None, gt=0)
    gender_policy: UnitTypeGenderPolicy | None = None
    bed_config: list[Any] | None = None
    size_sqm: Decimal | None = Field(default=None, max_digits=7, decimal_places=2)
    amenities: list[str] | None = None
    content: dict[str, Any] | None = None
    is_virtual: bool | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class UnitTypeRead(SQLModel):
    """Fields returned when reading a UnitType."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    code: str
    name: str
    category: str
    sell_mode: str
    time_grain: str
    hour_block_minutes: int | None
    turnaround_minutes: int
    base_occupancy: int
    max_adults: int
    max_children: int
    max_occupancy: int
    gender_policy: str
    bed_config: list[Any]
    size_sqm: Decimal | None
    amenities: list[str]
    content: dict[str, Any]
    is_virtual: bool
    sort_order: int
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
