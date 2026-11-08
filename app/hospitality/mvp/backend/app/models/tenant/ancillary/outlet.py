"""Outlet entity — table ``outlet``.

Tenant database, Q. Ancillary / POS lite.

POS Lite, services, gift vouchers.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

OutletKind = Literal[
    "breakfast",
    "restaurant",
    "bar",
    "shop",
    "reception",
    "spa",
    "activities",
    "pool_bar",
]


class Outlet(TenantEntity, table=True):
    """POS Lite, services, gift vouchers."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="outlet_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id", "property_id", "code", name="outlet_tenant_id_property_id_code_key"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="outlet_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            (
                "kind IN ('breakfast', 'restaurant', 'bar', 'shop', 'reception', 'spa', "
                "'activities', 'pool_bar')"
            ),
            name="outlet_kind_check",
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    code: str = Field(sa_type=Text)
    name: str = Field(sa_type=Text)
    kind: str = Field(sa_type=Text)
    opening_hours: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
    )
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class OutletCreate(SQLModel):
    """Fields accepted when creating a Outlet."""

    property_id: UUID
    code: str
    name: str
    kind: OutletKind
    opening_hours: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class OutletUpdate(SQLModel):
    """Fields accepted when patching a Outlet (all optional)."""

    property_id: UUID | None = None
    code: str | None = None
    name: str | None = None
    kind: OutletKind | None = None
    opening_hours: dict[str, Any] | None = None
    is_active: bool | None = None


class OutletRead(SQLModel):
    """Fields returned when reading a Outlet."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    code: str
    name: str
    kind: str
    opening_hours: dict[str, Any]
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
