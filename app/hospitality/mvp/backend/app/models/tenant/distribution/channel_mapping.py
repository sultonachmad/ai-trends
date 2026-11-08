"""ChannelMapping entity — table ``channelmapping``.

Tenant database, K. Distribution (channel manager).

Local product -> channel room/rate ids.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    SmallInteger,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity


class ChannelMapping(TenantEntity, table=True):
    """Local product -> channel room/rate ids."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="channelmapping_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "channel_connection_id",
            "external_room_id",
            "external_rate_id",
            "occupancy",
            name="channelmapping_tenant_id_channel_connection_id_external_roo_key",
            postgresql_nulls_not_distinct=True,
        ),
        ForeignKeyConstraint(
            ["tenant_id", "channel_connection_id"],
            ["channelconnection.tenant_id", "channelconnection.id"],
            name="channelmapping_tenant_id_channel_connection_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_type_id"],
            ["unittype.tenant_id", "unittype.id"],
            name="channelmapping_tenant_id_unit_type_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "rate_plan_id"],
            ["rateplan.tenant_id", "rateplan.id"],
            name="channelmapping_tenant_id_rate_plan_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint("(allocation_cap >= 0)", name="channelmapping_allocation_cap_check"),
        MIGRATION_ONLY,
    )

    channel_connection_id: UUID = Field(sa_type=Uuid)
    unit_type_id: UUID = Field(sa_type=Uuid)
    rate_plan_id: UUID | None = Field(default=None, sa_type=Uuid)
    external_room_id: str = Field(sa_type=Text)
    external_rate_id: str | None = Field(default=None, sa_type=Text)
    occupancy: int | None = Field(default=None, sa_type=SmallInteger)
    markup_pct: Decimal | None = Field(default=None, max_digits=6, decimal_places=2)
    allocation_cap: int | None = Field(default=None)
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class ChannelMappingCreate(SQLModel):
    """Fields accepted when creating a ChannelMapping."""

    channel_connection_id: UUID
    unit_type_id: UUID
    rate_plan_id: UUID | None = None
    external_room_id: str
    external_rate_id: str | None = None
    occupancy: int | None = None
    markup_pct: Decimal | None = Field(default=None, max_digits=6, decimal_places=2)
    allocation_cap: int | None = Field(default=None, ge=0)
    is_active: bool = True


class ChannelMappingUpdate(SQLModel):
    """Fields accepted when patching a ChannelMapping (all optional)."""

    channel_connection_id: UUID | None = None
    unit_type_id: UUID | None = None
    rate_plan_id: UUID | None = None
    external_room_id: str | None = None
    external_rate_id: str | None = None
    occupancy: int | None = None
    markup_pct: Decimal | None = Field(default=None, max_digits=6, decimal_places=2)
    allocation_cap: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class ChannelMappingRead(SQLModel):
    """Fields returned when reading a ChannelMapping."""

    id: UUID
    tenant_id: UUID
    channel_connection_id: UUID
    unit_type_id: UUID
    rate_plan_id: UUID | None
    external_room_id: str
    external_rate_id: str | None
    occupancy: int | None
    markup_pct: Decimal | None
    allocation_cap: int | None
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
