"""IcalFeed entity — table ``icalfeed``.

Tenant database, K. Distribution (channel manager).

iCal import/export per unit.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

IcalFeedDirection = Literal[
    "import",
    "export",
]


class IcalFeed(TenantEntity, table=True):
    """iCal import/export per unit."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="icalfeed_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "channel_connection_id"],
            ["channelconnection.tenant_id", "channelconnection.id"],
            name="icalfeed_tenant_id_channel_connection_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["unit.tenant_id", "unit.id"],
            name="icalfeed_tenant_id_unit_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint("direction IN ('import', 'export')", name="icalfeed_direction_check"),
        CheckConstraint(
            "((direction = 'import'::text) = (url IS NOT NULL))", name="icalfeed_check"
        ),
        MIGRATION_ONLY,
    )

    channel_connection_id: UUID | None = Field(default=None, sa_type=Uuid)
    unit_id: UUID = Field(sa_type=Uuid)
    direction: str = Field(sa_type=Text)
    url: str | None = Field(default=None, sa_type=Text, description="import source")
    export_token_hash: str | None = Field(
        default=None, sa_type=Text, description="export URL token (path segment)"
    )
    last_synced_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    last_error: str | None = Field(default=None, sa_type=Text)
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class IcalFeedCreate(SQLModel):
    """Fields accepted when creating a IcalFeed."""

    channel_connection_id: UUID | None = None
    unit_id: UUID
    direction: IcalFeedDirection
    url: str | None = None
    last_synced_at: dt.datetime | None = None
    last_error: str | None = None
    is_active: bool = True


class IcalFeedUpdate(SQLModel):
    """Fields accepted when patching a IcalFeed (all optional)."""

    channel_connection_id: UUID | None = None
    unit_id: UUID | None = None
    direction: IcalFeedDirection | None = None
    url: str | None = None
    last_synced_at: dt.datetime | None = None
    last_error: str | None = None
    is_active: bool | None = None


class IcalFeedRead(SQLModel):
    """Fields returned when reading a IcalFeed (never returns: export_token_hash)."""

    id: UUID
    tenant_id: UUID
    channel_connection_id: UUID | None
    unit_id: UUID
    direction: str
    url: str | None
    last_synced_at: dt.datetime | None
    last_error: str | None
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
