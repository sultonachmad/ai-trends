"""ChannelCatalog entity — table ``channelcatalog``.

Control-plane database, Control plane.

Distribution channels the platform can connect to. Copied into each tenant DB (tenant.channel)
at provisioning so tenant data never references across DBs.

Mirrors .ttest/contexts/schema-control-plane.sql; the Alembic migration creates the table.
"""

import datetime as dt
from decimal import Decimal
from typing import Literal

from sqlalchemy import CheckConstraint, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, utc_datetime_field

ChannelCatalogKind = Literal[
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
ChannelCatalogConnectivity = Literal[
    "direct_api",
    "partner",
    "ical",
    "manual",
]
ChannelCatalogCertificationStatus = Literal[
    "planned",
    "in_progress",
    "certified",
    "deprecated",
]


class ChannelCatalog(SQLModel, table=True):
    """
    Distribution channels the platform can connect to. Copied into each tenant DB
    (tenant.channel) at provisioning so tenant data never references across DBs.
    """

    __table_args__ = (
        CheckConstraint(
            (
                "kind IN ('ota', 'metasearch', 'google', 'gds', 'wholesaler', "
                "'vacation_rental', 'ical', 'direct_web', 'direct_phone', 'walk_in', "
                "'messaging', 'corporate', 'other')"
            ),
            name="channelcatalog_kind_check",
        ),
        CheckConstraint(
            "connectivity IN ('direct_api', 'partner', 'ical', 'manual')",
            name="channelcatalog_connectivity_check",
        ),
        CheckConstraint(
            ("certification_status IN ('planned', 'in_progress', 'certified', 'deprecated')"),
            name="channelcatalog_certification_status_check",
        ),
        MIGRATION_ONLY,
    )

    code: str = Field(
        primary_key=True, sa_type=Text, description="'traveloka', 'google_hotels', 'airbnb', 'ical'"
    )
    name: str = Field(sa_type=Text)
    kind: str = Field(sa_type=Text)
    connectivity: str = Field(sa_type=Text)
    certification_status: str = Field(
        default="planned",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'planned'::text")},
    )
    country_codes: list[str] = Field(
        default_factory=list,
        sa_type=ARRAY(Text),
        sa_column_kwargs={"server_default": text("'{}'::text[]")},
        description="ISO-3166 alpha-2; empty = global",
    )
    features: list[str] = Field(
        default_factory=list,
        sa_type=ARRAY(Text),
        sa_column_kwargs={"server_default": text("'{}'::text[]")},
        description="'ari_push','booking_pull','content','vcc','messaging','reviews'",
    )
    default_commission_pct: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})
    created_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]
    updated_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, onupdate_now=True, server_default_now=True
    )  # type: ignore[assignment]


class ChannelCatalogCreate(SQLModel):
    """Fields accepted when creating a ChannelCatalog."""

    code: str
    name: str
    kind: ChannelCatalogKind
    connectivity: ChannelCatalogConnectivity
    certification_status: ChannelCatalogCertificationStatus = "planned"
    country_codes: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    default_commission_pct: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    is_active: bool = True


class ChannelCatalogUpdate(SQLModel):
    """Fields accepted when patching a ChannelCatalog (all optional)."""

    name: str | None = None
    kind: ChannelCatalogKind | None = None
    connectivity: ChannelCatalogConnectivity | None = None
    certification_status: ChannelCatalogCertificationStatus | None = None
    country_codes: list[str] | None = None
    features: list[str] | None = None
    default_commission_pct: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    is_active: bool | None = None


class ChannelCatalogRead(SQLModel):
    """Fields returned when reading a ChannelCatalog."""

    code: str
    name: str
    kind: str
    connectivity: str
    certification_status: str
    country_codes: list[str]
    features: list[str]
    default_commission_pct: Decimal | None
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
