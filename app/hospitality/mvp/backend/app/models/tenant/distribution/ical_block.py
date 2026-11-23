"""IcalBlock entity — table ``icalblock``.

Tenant database, K. Distribution (channel manager).

One row per (imported calendar, date) that site marks as busy. Each row accounts for
one unit in ``inventoryday.blocked``, so a later import can release exactly the dates
the site no longer lists.
"""

import datetime as dt
from uuid import UUID

from sqlalchemy import ForeignKeyConstraint, Index, UniqueConstraint, Uuid
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field


class IcalBlock(TenantRecord, table=True):
    """A date an imported calendar marks as busy."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="icalblock_tenant_id_id_key"),
        UniqueConstraint("tenant_id", "feed_id", "stay_date", name="icalblock_feed_date_key"),
        ForeignKeyConstraint(
            ["tenant_id", "feed_id"],
            ["icalfeed.tenant_id", "icalfeed.id"],
            name="icalblock_tenant_id_feed_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_type_id"],
            ["unittype.tenant_id", "unittype.id"],
            name="icalblock_tenant_id_unit_type_id_fkey",
            ondelete="CASCADE",
        ),
        Index("ix_icalblock_room_date", "tenant_id", "unit_type_id", "stay_date"),
        MIGRATION_ONLY,
    )

    feed_id: UUID = Field(sa_type=Uuid)
    unit_type_id: UUID = Field(sa_type=Uuid)
    stay_date: dt.date = Field()
    created_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]


class IcalBlockCreate(SQLModel):
    """Fields accepted when creating an IcalBlock."""

    feed_id: UUID
    unit_type_id: UUID
    stay_date: dt.date


class IcalBlockUpdate(SQLModel):
    """Blocks are replaced, never edited."""


class IcalBlockRead(SQLModel):
    """Fields returned when reading an IcalBlock."""

    id: UUID
    tenant_id: UUID
    feed_id: UUID
    unit_type_id: UUID
    stay_date: dt.date
    created_at: dt.datetime
