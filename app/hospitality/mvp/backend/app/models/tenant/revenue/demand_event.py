"""DemandEvent entity — table ``demandevent``.

Tenant database, R. Revenue management.

Holidays, cuti bersama, Lebaran, local events.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

DemandEventKind = Literal[
    "public_holiday",
    "cuti_bersama",
    "school_holiday",
    "religious",
    "local_event",
    "convention",
    "weather",
    "other",
]
DemandEventImpact = Literal[
    "negative",
    "low",
    "medium",
    "high",
    "very_high",
]


class DemandEvent(TenantEntity, table=True):
    """Holidays, cuti bersama, Lebaran, local events."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="demandevent_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="demandevent_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            (
                "kind IN ('public_holiday', 'cuti_bersama', 'school_holiday', "
                "'religious', 'local_event', 'convention', 'weather', 'other')"
            ),
            name="demandevent_kind_check",
        ),
        CheckConstraint(
            "impact IN ('negative', 'low', 'medium', 'high', 'very_high')",
            name="demandevent_impact_check",
        ),
        CheckConstraint("(ends_on >= starts_on)", name="demandevent_check"),
        MIGRATION_ONLY,
    )

    property_id: UUID | None = Field(
        default=None, sa_type=Uuid, description="NULL = applies to all properties in region"
    )
    name: str = Field(sa_type=Text)
    kind: str = Field(sa_type=Text)
    region_code: str | None = Field(default=None, sa_type=Text)
    starts_on: dt.date = Field()
    ends_on: dt.date = Field()
    impact: str = Field(
        default="medium", sa_type=Text, sa_column_kwargs={"server_default": text("'medium'::text")}
    )
    source: str = Field(
        default="manual",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'manual'::text")},
        description="'calendar_pack','manual','ai_suggested'",
    )
    is_confirmed: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class DemandEventCreate(SQLModel):
    """Fields accepted when creating a DemandEvent."""

    property_id: UUID | None = None
    name: str
    kind: DemandEventKind
    region_code: str | None = None
    starts_on: dt.date
    ends_on: dt.date
    impact: DemandEventImpact = "medium"
    source: str = "manual"
    is_confirmed: bool = True


class DemandEventUpdate(SQLModel):
    """Fields accepted when patching a DemandEvent (all optional)."""

    property_id: UUID | None = None
    name: str | None = None
    kind: DemandEventKind | None = None
    region_code: str | None = None
    starts_on: dt.date | None = None
    ends_on: dt.date | None = None
    impact: DemandEventImpact | None = None
    source: str | None = None
    is_confirmed: bool | None = None


class DemandEventRead(SQLModel):
    """Fields returned when reading a DemandEvent."""

    id: UUID
    tenant_id: UUID
    property_id: UUID | None
    name: str
    kind: str
    region_code: str | None
    starts_on: dt.date
    ends_on: dt.date
    impact: str
    source: str
    is_confirmed: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
