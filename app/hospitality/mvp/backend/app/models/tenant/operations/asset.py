"""Asset entity — table ``asset``.

Tenant database, M. Operations (housekeeping & maintenance).

Maintenance.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

AssetStatus = Literal[
    "in_service",
    "down",
    "retired",
]


class Asset(TenantEntity, table=True):
    """Maintenance."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="asset_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id", "property_id", "code", name="asset_tenant_id_property_id_code_key"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="asset_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["unit.tenant_id", "unit.id"],
            name="asset_tenant_id_unit_id_fkey",
            ondelete="SET NULL (unit_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "area_id"],
            ["propertyarea.tenant_id", "propertyarea.id"],
            name="asset_tenant_id_area_id_fkey",
            ondelete="SET NULL (area_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "vendor_id"],
            ["vendor.tenant_id", "vendor.id"],
            name="asset_tenant_id_vendor_id_fkey",
            ondelete="SET NULL (vendor_id)",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "manual_document_id"],
            ["document.tenant_id", "document.id"],
            name="asset_tenant_id_manual_document_id_fkey",
            ondelete="SET NULL (manual_document_id)",
        ),
        CheckConstraint("status IN ('in_service', 'down', 'retired')", name="asset_status_check"),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    unit_id: UUID | None = Field(default=None, sa_type=Uuid)
    area_id: UUID | None = Field(default=None, sa_type=Uuid)
    code: str = Field(sa_type=Text)
    name: str = Field(sa_type=Text)
    category: str = Field(
        sa_type=Text, description="'hvac','boiler','lift','pool','appliance','vehicle','generator'"
    )
    manufacturer: str | None = Field(default=None, sa_type=Text)
    model: str | None = Field(default=None, sa_type=Text)
    serial_no: str | None = Field(default=None, sa_type=Text)
    installed_on: dt.date | None = Field(default=None)
    warranty_until: dt.date | None = Field(default=None)
    vendor_id: UUID | None = Field(default=None, sa_type=Uuid)
    manual_document_id: UUID | None = Field(default=None, sa_type=Uuid)
    status: str = Field(
        default="in_service",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'in_service'::text")},
    )


class AssetCreate(SQLModel):
    """Fields accepted when creating a Asset."""

    property_id: UUID
    unit_id: UUID | None = None
    area_id: UUID | None = None
    code: str
    name: str
    category: str
    manufacturer: str | None = None
    model: str | None = None
    serial_no: str | None = None
    installed_on: dt.date | None = None
    warranty_until: dt.date | None = None
    vendor_id: UUID | None = None
    manual_document_id: UUID | None = None
    status: AssetStatus = "in_service"


class AssetUpdate(SQLModel):
    """Fields accepted when patching a Asset (all optional)."""

    property_id: UUID | None = None
    unit_id: UUID | None = None
    area_id: UUID | None = None
    code: str | None = None
    name: str | None = None
    category: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    serial_no: str | None = None
    installed_on: dt.date | None = None
    warranty_until: dt.date | None = None
    vendor_id: UUID | None = None
    manual_document_id: UUID | None = None
    status: AssetStatus | None = None


class AssetRead(SQLModel):
    """Fields returned when reading a Asset."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    unit_id: UUID | None
    area_id: UUID | None
    code: str
    name: str
    category: str
    manufacturer: str | None
    model: str | None
    serial_no: str | None
    installed_on: dt.date | None
    warranty_until: dt.date | None
    vendor_id: UUID | None
    manual_document_id: UUID | None
    status: str
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
