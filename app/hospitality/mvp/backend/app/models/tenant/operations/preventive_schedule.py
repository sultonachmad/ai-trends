"""PreventiveSchedule entity — table ``preventiveschedule``.

Tenant database, M. Operations (housekeeping & maintenance).

Maintenance.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity


class PreventiveSchedule(TenantEntity, table=True):
    """Maintenance."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="preventiveschedule_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="preventiveschedule_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "asset_id"],
            ["asset.tenant_id", "asset.id"],
            name="preventiveschedule_tenant_id_asset_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["unit.tenant_id", "unit.id"],
            name="preventiveschedule_tenant_id_unit_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint("(interval_days > 0)", name="preventiveschedule_interval_days_check"),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    asset_id: UUID | None = Field(default=None, sa_type=Uuid)
    unit_id: UUID | None = Field(default=None, sa_type=Uuid)
    name: str = Field(sa_type=Text)
    interval_days: int = Field()
    lead_days: int = Field(default=7, sa_column_kwargs={"server_default": text("7")})
    next_due_on: dt.date = Field()
    checklist: list[Any] = Field(
        default_factory=list,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'[]'::jsonb")},
    )
    is_statutory: bool = Field(
        default=False,
        sa_column_kwargs={"server_default": text("false")},
        description="fire, lift, gas certifications",
    )
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class PreventiveScheduleCreate(SQLModel):
    """Fields accepted when creating a PreventiveSchedule."""

    property_id: UUID
    asset_id: UUID | None = None
    unit_id: UUID | None = None
    name: str
    interval_days: int = Field(gt=0)
    lead_days: int = 7
    next_due_on: dt.date
    checklist: list[Any] = Field(default_factory=list)
    is_statutory: bool = False
    is_active: bool = True


class PreventiveScheduleUpdate(SQLModel):
    """Fields accepted when patching a PreventiveSchedule (all optional)."""

    property_id: UUID | None = None
    asset_id: UUID | None = None
    unit_id: UUID | None = None
    name: str | None = None
    interval_days: int | None = Field(default=None, gt=0)
    lead_days: int | None = None
    next_due_on: dt.date | None = None
    checklist: list[Any] | None = None
    is_statutory: bool | None = None
    is_active: bool | None = None


class PreventiveScheduleRead(SQLModel):
    """Fields returned when reading a PreventiveSchedule."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    asset_id: UUID | None
    unit_id: UUID | None
    name: str
    interval_days: int
    lead_days: int
    next_due_on: dt.date
    checklist: list[Any]
    is_statutory: bool
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
