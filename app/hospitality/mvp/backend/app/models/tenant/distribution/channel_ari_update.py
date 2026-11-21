"""ChannelAriUpdate entity — table ``channelariupdate``.

Tenant database, K. Distribution (channel manager).

One row per (connection, room type, date) whose availability, prices or restrictions
must (again) be sent to the channel. The unique key collapses repeated changes; the
background sender deletes rows as the channel acknowledges them.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from uuid import UUID

from sqlalchemy import ForeignKeyConstraint, Index, UniqueConstraint, Uuid
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field


class ChannelAriUpdate(TenantRecord, table=True):
    """A date whose truth must reach a channel."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="channelariupdate_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "channel_connection_id",
            "unit_type_id",
            "stay_date",
            name="channelariupdate_due_key",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="channelariupdate_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "channel_connection_id"],
            ["channelconnection.tenant_id", "channelconnection.id"],
            name="channelariupdate_tenant_id_channel_connection_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_type_id"],
            ["unittype.tenant_id", "unittype.id"],
            name="channelariupdate_tenant_id_unit_type_id_fkey",
            ondelete="CASCADE",
        ),
        Index(
            "ix_channelariupdate_due",
            "tenant_id",
            "channel_connection_id",
            "stay_date",
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    channel_connection_id: UUID = Field(sa_type=Uuid)
    unit_type_id: UUID = Field(sa_type=Uuid)
    stay_date: dt.date = Field()
    created_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]


class ChannelAriUpdateCreate(SQLModel):
    """Fields accepted when creating a ChannelAriUpdate."""

    property_id: UUID
    channel_connection_id: UUID
    unit_type_id: UUID
    stay_date: dt.date


class ChannelAriUpdateUpdate(SQLModel):
    """Patch shape for a ChannelAriUpdate: every field is optional."""

    pass


class ChannelAriUpdateRead(SQLModel):
    """Fields returned when reading a ChannelAriUpdate."""

    tenant_id: UUID
    property_id: UUID
    channel_connection_id: UUID
    unit_type_id: UUID
    stay_date: dt.date
    created_at: dt.datetime
