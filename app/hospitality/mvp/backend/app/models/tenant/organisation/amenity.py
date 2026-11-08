"""Amenity entity — table ``amenity``.

Tenant database, A. Organisation & property.

Amenity / feature dictionary (codes are referenced from text[] columns).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any
from uuid import UUID

from sqlalchemy import Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity


class Amenity(TenantEntity, table=True):
    """Amenity / feature dictionary (codes are referenced from text[] columns)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="amenity_tenant_id_id_key"),
        UniqueConstraint("tenant_id", "code", name="amenity_tenant_id_code_key"),
        MIGRATION_ONLY,
    )

    code: str = Field(sa_type=Text, description="'wifi','pool','kitchen','prayer_room','qibla'")
    category: str = Field(
        default="general",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'general'::text")},
    )
    name_i18n: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
    )


class AmenityCreate(SQLModel):
    """Fields accepted when creating a Amenity."""

    code: str
    category: str = "general"
    name_i18n: dict[str, Any] = Field(default_factory=dict)


class AmenityUpdate(SQLModel):
    """Fields accepted when patching a Amenity (all optional)."""

    code: str | None = None
    category: str | None = None
    name_i18n: dict[str, Any] | None = None


class AmenityRead(SQLModel):
    """Fields returned when reading a Amenity."""

    id: UUID
    tenant_id: UUID
    code: str
    category: str
    name_i18n: dict[str, Any]
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
