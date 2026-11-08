"""ChannelPerformanceDaily entity — table ``channelperformancedaily``.

Tenant database, K. Distribution (channel manager).

Daily channel performance (Google impressions/clicks/cost, OTA production).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, ForeignKeyConstraint, UniqueConstraint, Uuid
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord


class ChannelPerformanceDaily(TenantRecord, table=True):
    """Daily channel performance (Google impressions/clicks/cost, OTA production)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="channelperformancedaily_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "channel_connection_id",
            "metric_date",
            name="channelperformancedaily_tenant_id_channel_connection_id_met_key",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "channel_connection_id"],
            ["channelconnection.tenant_id", "channelconnection.id"],
            name="channelperformancedaily_tenant_id_channel_connection_id_fkey",
            ondelete="CASCADE",
        ),
        MIGRATION_ONLY,
    )

    channel_connection_id: UUID = Field(sa_type=Uuid)
    metric_date: dt.date = Field()
    impressions: int | None = Field(default=None, sa_type=BigInteger)
    clicks: int | None = Field(default=None, sa_type=BigInteger)
    bookings: int | None = Field(default=None)
    room_nights: int | None = Field(default=None)
    revenue: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    cost: Decimal | None = Field(
        default=None, max_digits=18, decimal_places=2, description="ad spend or commission"
    )
    price_accuracy_score: Decimal | None = Field(
        default=None, max_digits=5, decimal_places=2, description="Google"
    )


class ChannelPerformanceDailyCreate(SQLModel):
    """Fields accepted when creating a ChannelPerformanceDaily."""

    channel_connection_id: UUID
    metric_date: dt.date
    impressions: int | None = None
    clicks: int | None = None
    bookings: int | None = None
    room_nights: int | None = None
    revenue: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    cost: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    price_accuracy_score: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)


class ChannelPerformanceDailyUpdate(SQLModel):
    """Fields accepted when patching a ChannelPerformanceDaily (all optional)."""

    channel_connection_id: UUID | None = None
    metric_date: dt.date | None = None
    impressions: int | None = None
    clicks: int | None = None
    bookings: int | None = None
    room_nights: int | None = None
    revenue: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    cost: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    price_accuracy_score: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)


class ChannelPerformanceDailyRead(SQLModel):
    """Fields returned when reading a ChannelPerformanceDaily."""

    id: UUID
    tenant_id: UUID
    channel_connection_id: UUID
    metric_date: dt.date
    impressions: int | None
    clicks: int | None
    bookings: int | None
    room_nights: int | None
    revenue: Decimal | None
    cost: Decimal | None
    price_accuracy_score: Decimal | None
