"""GuestSegment entity — table ``guestsegment``.

Tenant database, L. CRM, messaging & reputation.

Segments and campaigns.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

GuestSegmentKind = Literal[
    "dynamic",
    "static",
]


class GuestSegment(TenantEntity, table=True):
    """Segments and campaigns."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="guestsegment_tenant_id_id_key"),
        CheckConstraint("kind IN ('dynamic', 'static')", name="guestsegment_kind_check"),
        MIGRATION_ONLY,
    )

    name: str = Field(sa_type=Text)
    kind: str = Field(
        default="dynamic",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'dynamic'::text")},
    )
    rules: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
    )
    guest_ids: list[UUID] = Field(
        default_factory=list,
        sa_type=ARRAY(Uuid),
        sa_column_kwargs={"server_default": text("'{}'::uuid[]")},
        description="static lists only",
    )


class GuestSegmentCreate(SQLModel):
    """Fields accepted when creating a GuestSegment."""

    name: str
    kind: GuestSegmentKind = "dynamic"
    rules: dict[str, Any] = Field(default_factory=dict)
    guest_ids: list[UUID] = Field(default_factory=list)


class GuestSegmentUpdate(SQLModel):
    """Fields accepted when patching a GuestSegment (all optional)."""

    name: str | None = None
    kind: GuestSegmentKind | None = None
    rules: dict[str, Any] | None = None
    guest_ids: list[UUID] | None = None


class GuestSegmentRead(SQLModel):
    """Fields returned when reading a GuestSegment."""

    id: UUID
    tenant_id: UUID
    name: str
    kind: str
    rules: dict[str, Any]
    guest_ids: list[UUID]
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
