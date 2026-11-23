"""ChannelSimulatorListing entity — table ``channelsimulatorlisting``.

Tenant database, K. Distribution (channel manager).

A listing on the simulated online travel agency: its property ID and its rooms and
rates, as the agency names them. Development and test only — it stands in for the
agency's own extranet, which we cannot see.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field


class ChannelSimulatorListing(TenantRecord, table=True):
    """A property as the simulated agency lists it."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="channelsimulatorlisting_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id", "hotel_id", name="channelsimulatorlisting_tenant_id_hotel_id_key"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="channelsimulatorlisting_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        MIGRATION_ONLY,
    )

    property_id: UUID = Field(sa_type=Uuid)
    hotel_id: str = Field(sa_type=Text, description="the agency's id for the property")
    name: str = Field(sa_type=Text)
    rooms: list[Any] = Field(
        default_factory=list,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'[]'::jsonb")},
        description='[{"id":"R1","name":"…","max_guests":2,"rates":[{"id":"P1","name":"…"}]}]',
    )
    # What the agency has been told and acknowledged: {room id: {date: day}}.
    ari: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description="acknowledged ARI as stored by push_ari (development and test only)",
    )
    # Fail the next N pushes, so retries and drift can be exercised (dev/test only).
    fail_next: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})
    # A test calendar for calendar links: {"busy": ["2026-12-01"], "broken": false}.
    calendar: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description="what the simulated site's .ics shows (development and test only)",
    )
    # The agency's booking history: one entry per new/modify/cancel event.
    bookings: list[Any] = Field(
        default_factory=list,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'[]'::jsonb")},
        description="booking events as the agency reports them (dev/test only)",
    )
    created_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]


class ChannelSimulatorListingCreate(SQLModel):
    """Fields accepted when creating a ChannelSimulatorListing."""

    property_id: UUID
    hotel_id: str
    name: str
    rooms: list[Any] = Field(default_factory=list)


class ChannelSimulatorListingUpdate(SQLModel):
    """Patch shape for a ChannelSimulatorListing: every field is optional."""

    hotel_id: str | None = None
    name: str | None = None
    rooms: list[Any] | None = None


class ChannelSimulatorListingRead(SQLModel):
    """Fields returned when reading a ChannelSimulatorListing."""

    id: UUID
    tenant_id: UUID
    property_id: UUID
    hotel_id: str
    name: str
    rooms: list[Any]
    created_at: dt.datetime
