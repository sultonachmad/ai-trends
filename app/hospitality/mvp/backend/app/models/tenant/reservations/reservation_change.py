"""ReservationChange entity — table ``reservationchange``.

Tenant database, G. Groups & reservations.

Field-level change history (FR-RES-023). Append-only.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field

ReservationChangeSource = Literal[
    "staff",
    "guest",
    "channel",
    "api",
    "system",
    "ai",
]


class ReservationChange(TenantRecord, table=True):
    """Field-level change history (FR-RES-023). Append-only."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="reservationchange_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_id"],
            ["reservation.tenant_id", "reservation.id"],
            name="reservationchange_tenant_id_reservation_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "source IN ('staff', 'guest', 'channel', 'api', 'system', 'ai')",
            name="reservationchange_source_check",
        ),
        Index("ix_reservationchange_res", "tenant_id", "reservation_id", "changed_at"),
        MIGRATION_ONLY,
    )

    reservation_id: UUID = Field(sa_type=Uuid)
    changed_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]
    actor: str | None = Field(default=None, sa_type=Text)
    source: str = Field(sa_type=Text)
    action: str = Field(
        sa_type=Text, description="'created','modified','cancelled','checked_in','room_moved',…"
    )
    changes: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
        description='{"field":{"old":..,"new":..}}',
    )


class ReservationChangeCreate(SQLModel):
    """Fields accepted when creating a ReservationChange."""

    reservation_id: UUID
    changed_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))
    actor: str | None = None
    source: ReservationChangeSource
    action: str
    changes: dict[str, Any] = Field(default_factory=dict)


class ReservationChangeUpdate(SQLModel):
    """Fields accepted when patching a ReservationChange (all optional)."""

    reservation_id: UUID | None = None
    changed_at: dt.datetime | None = None
    actor: str | None = None
    source: ReservationChangeSource | None = None
    action: str | None = None
    changes: dict[str, Any] | None = None


class ReservationChangeRead(SQLModel):
    """Fields returned when reading a ReservationChange."""

    id: UUID
    tenant_id: UUID
    reservation_id: UUID
    changed_at: dt.datetime
    actor: str | None
    source: str
    action: str
    changes: dict[str, Any]
