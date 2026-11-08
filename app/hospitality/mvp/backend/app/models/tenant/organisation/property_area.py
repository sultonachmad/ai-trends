"""PropertyArea entity — table ``propertyarea``.

Tenant database, A. Organisation & property.

Building / floor / wing / zone / campsite area. Self-referencing tree.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

PropertyAreaKind = Literal[
    "building",
    "floor",
    "wing",
    "zone",
    "site",
    "public_area",
]


class PropertyArea(TenantEntity, table=True):
    """Building / floor / wing / zone / campsite area. Self-referencing tree."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="propertyarea_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="propertyarea_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "parent_area_id"],
            ["propertyarea.tenant_id", "propertyarea.id"],
            name="propertyarea_tenant_id_parent_area_id_fkey",
            ondelete="SET NULL (parent_area_id)",
        ),
        CheckConstraint(
            "kind IN ('building', 'floor', 'wing', 'zone', 'site', 'public_area')",
            name="propertyarea_kind_check",
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    parent_area_id: UUID | None = Field(default=None, sa_type=Uuid)
    kind: str = Field(sa_type=Text)
    name: str = Field(sa_type=Text)
    sort_order: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})


class PropertyAreaCreate(SQLModel):
    """Fields accepted when creating a PropertyArea."""

    property_id: UUID
    parent_area_id: UUID | None = None
    kind: PropertyAreaKind
    name: str
    sort_order: int = 0


class PropertyAreaUpdate(SQLModel):
    """Fields accepted when patching a PropertyArea (all optional)."""

    property_id: UUID | None = None
    parent_area_id: UUID | None = None
    kind: PropertyAreaKind | None = None
    name: str | None = None
    sort_order: int | None = None


class PropertyAreaRead(SQLModel):
    """Fields returned when reading a PropertyArea."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    parent_area_id: UUID | None
    kind: str
    name: str
    sort_order: int
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
