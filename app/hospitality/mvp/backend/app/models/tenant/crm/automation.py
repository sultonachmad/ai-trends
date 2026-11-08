"""Automation entity — table ``automation``.

Tenant database, L. CRM, messaging & reputation.

Lifecycle journeys ("2 days before arrival send pre-check-in link").

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity


class Automation(TenantEntity, table=True):
    """Lifecycle journeys ("2 days before arrival send pre-check-in link")."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="automation_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="automation_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID | None = Field(default=None, sa_type=Uuid)
    name: str = Field(sa_type=Text)
    trigger_event: str = Field(
        sa_type=Text, description="'reservation.confirmed','reservation.arrival_offset',…"
    )
    offset_minutes: int = Field(
        default=0,
        sa_column_kwargs={"server_default": text("0")},
        description="negative = before the anchor time",
    )
    conditions: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
    )
    steps: list[Any] = Field(
        default_factory=list,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'[]'::jsonb")},
    )
    review_before_send: bool = Field(
        default=False, sa_column_kwargs={"server_default": text("false")}
    )
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class AutomationCreate(SQLModel):
    """Fields accepted when creating a Automation."""

    property_id: UUID | None = None
    name: str
    trigger_event: str
    offset_minutes: int = 0
    conditions: dict[str, Any] = Field(default_factory=dict)
    steps: list[Any] = Field(default_factory=list)
    review_before_send: bool = False
    is_active: bool = True


class AutomationUpdate(SQLModel):
    """Fields accepted when patching a Automation (all optional)."""

    property_id: UUID | None = None
    name: str | None = None
    trigger_event: str | None = None
    offset_minutes: int | None = None
    conditions: dict[str, Any] | None = None
    steps: list[Any] | None = None
    review_before_send: bool | None = None
    is_active: bool | None = None


class AutomationRead(SQLModel):
    """Fields returned when reading a Automation."""

    id: UUID
    tenant_id: UUID
    property_id: UUID | None
    name: str
    trigger_event: str
    offset_minutes: int
    conditions: dict[str, Any]
    steps: list[Any]
    review_before_send: bool
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
