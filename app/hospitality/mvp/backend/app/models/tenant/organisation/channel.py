"""Channel entity — table ``channel``.

Tenant database, A. Organisation & property.

Distribution / booking-source channels (seeded from control-plane channelcatalog).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, Text, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

ChannelKind = Literal[
    "ota",
    "metasearch",
    "google",
    "gds",
    "wholesaler",
    "vacation_rental",
    "ical",
    "direct_web",
    "direct_phone",
    "walk_in",
    "messaging",
    "corporate",
    "other",
]


class Channel(TenantEntity, table=True):
    """Distribution / booking-source channels (seeded from control-plane channelcatalog)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="channel_tenant_id_id_key"),
        UniqueConstraint("tenant_id", "code", name="channel_tenant_id_code_key"),
        CheckConstraint(
            (
                "kind IN ('ota', 'metasearch', 'google', 'gds', 'wholesaler', "
                "'vacation_rental', 'ical', 'direct_web', 'direct_phone', 'walk_in', "
                "'messaging', 'corporate', 'other')"
            ),
            name="channel_kind_check",
        ),
        MIGRATION_ONLY,
    )

    code: str = Field(sa_type=Text, description="'traveloka','direct_web','walk_in','whatsapp'")
    name: str = Field(sa_type=Text)
    kind: str = Field(sa_type=Text)
    commission_pct: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    is_direct: bool = Field(default=False, sa_column_kwargs={"server_default": text("false")})
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})


class ChannelCreate(SQLModel):
    """Fields accepted when creating a Channel."""

    code: str
    name: str
    kind: ChannelKind
    commission_pct: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    is_direct: bool = False
    is_active: bool = True


class ChannelUpdate(SQLModel):
    """Fields accepted when patching a Channel (all optional)."""

    code: str | None = None
    name: str | None = None
    kind: ChannelKind | None = None
    commission_pct: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    is_direct: bool | None = None
    is_active: bool | None = None


class ChannelRead(SQLModel):
    """Fields returned when reading a Channel."""

    id: UUID
    tenant_id: UUID
    code: str
    name: str
    kind: str
    commission_pct: Decimal | None
    is_direct: bool
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
