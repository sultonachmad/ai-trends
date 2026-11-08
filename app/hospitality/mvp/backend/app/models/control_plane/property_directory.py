"""PropertyDirectory entity — table ``propertydirectory``.

Control-plane database, Control plane.

Light directory of properties for routing and portfolio/CRS-style lookups without opening every
tenant DB. Written by tenant DB outbox events.

Mirrors .ttest/contexts/schema-control-plane.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CHAR, ForeignKeyConstraint, Index, Text, Uuid
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, utc_datetime_field


class PropertyDirectory(SQLModel, table=True):
    """
    Light directory of properties for routing and portfolio/CRS-style lookups without opening
    every tenant DB. Written by tenant DB outbox events.
    """

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
            name="propertydirectory_tenant_id_fkey",
            ondelete="CASCADE",
        ),
        Index("ix_propertydirectory_tenant", "tenant_id"),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(
        primary_key=True, sa_type=Uuid, description="same id as tenant-DB property.id"
    )
    tenant_id: UUID = Field(sa_type=Uuid)
    code: str = Field(sa_type=Text)
    name: str = Field(sa_type=Text)
    property_type: str = Field(sa_type=Text)
    country_code: str = Field(sa_type=CHAR(2))
    region_code: str | None = Field(default=None, sa_type=Text)
    city: str | None = Field(default=None, sa_type=Text)
    latitude: Decimal | None = Field(default=None, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(default=None, max_digits=9, decimal_places=6)
    status: str = Field(sa_type=Text)
    synced_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]


class PropertyDirectoryCreate(SQLModel):
    """Fields accepted when creating a PropertyDirectory."""

    property_id: UUID
    tenant_id: UUID
    code: str
    name: str
    property_type: str
    country_code: str = Field(min_length=2, max_length=2)
    region_code: str | None = None
    city: str | None = None
    latitude: Decimal | None = Field(default=None, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(default=None, max_digits=9, decimal_places=6)
    status: str
    synced_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))


class PropertyDirectoryUpdate(SQLModel):
    """Fields accepted when patching a PropertyDirectory (all optional)."""

    tenant_id: UUID | None = None
    code: str | None = None
    name: str | None = None
    property_type: str | None = None
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    region_code: str | None = None
    city: str | None = None
    latitude: Decimal | None = Field(default=None, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(default=None, max_digits=9, decimal_places=6)
    status: str | None = None
    synced_at: dt.datetime | None = None


class PropertyDirectoryRead(SQLModel):
    """Fields returned when reading a PropertyDirectory."""

    property_id: UUID
    tenant_id: UUID
    code: str
    name: str
    property_type: str
    country_code: str
    region_code: str | None
    city: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    status: str
    synced_at: dt.datetime
