"""Competitor entity — table ``competitor``.

Tenant database, R. Revenue management.

Competitor set and shopped rates.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity


class Competitor(TenantEntity, table=True):
    """Competitor set and shopped rates."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="competitor_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="competitor_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    name: str = Field(sa_type=Text)
    external_ref: str | None = Field(default=None, sa_type=Text)
    unit_type_equivalence: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description='{"<our unit_type_id>":"Deluxe Room"}',
    )
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class CompetitorCreate(SQLModel):
    """Fields accepted when creating a Competitor."""

    property_id: UUID
    name: str
    external_ref: str | None = None
    unit_type_equivalence: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class CompetitorUpdate(SQLModel):
    """Fields accepted when patching a Competitor (all optional)."""

    property_id: UUID | None = None
    name: str | None = None
    external_ref: str | None = None
    unit_type_equivalence: dict[str, Any] | None = None
    is_active: bool | None = None


class CompetitorRead(SQLModel):
    """Fields returned when reading a Competitor."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    name: str
    external_ref: str | None
    unit_type_equivalence: dict[str, Any]
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
