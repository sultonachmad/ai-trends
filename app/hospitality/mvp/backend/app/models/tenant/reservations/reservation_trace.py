"""ReservationTrace entity — table ``reservationtrace``.

Tenant database, G. Groups & reservations.

Notes, check-in alerts and follow-up traces.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

ReservationTraceKind = Literal[
    "note",
    "alert",
    "trace",
]


class ReservationTrace(TenantEntity, table=True):
    """Notes, check-in alerts and follow-up traces."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="reservationtrace_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_id"],
            ["reservation.tenant_id", "reservation.id"],
            name="reservationtrace_tenant_id_reservation_id_fkey",
            ondelete="CASCADE",
        ),
        CheckConstraint("kind IN ('note', 'alert', 'trace')", name="reservationtrace_kind_check"),
        MIGRATION_ONLY,
    )

    reservation_id: UUID = Field(sa_type=Uuid)
    kind: str = Field(sa_type=Text)
    department: str | None = Field(default=None, sa_type=Text)
    body: str = Field(sa_type=Text)
    due_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    show_at_checkin: bool = Field(default=False, sa_column_kwargs={"server_default": text("false")})
    resolved_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    resolved_by: str | None = Field(default=None, sa_type=Text)


class ReservationTraceCreate(SQLModel):
    """Fields accepted when creating a ReservationTrace."""

    reservation_id: UUID
    kind: ReservationTraceKind
    department: str | None = None
    body: str
    due_at: dt.datetime | None = None
    show_at_checkin: bool = False
    resolved_at: dt.datetime | None = None
    resolved_by: str | None = None


class ReservationTraceUpdate(SQLModel):
    """Fields accepted when patching a ReservationTrace (all optional)."""

    reservation_id: UUID | None = None
    kind: ReservationTraceKind | None = None
    department: str | None = None
    body: str | None = None
    due_at: dt.datetime | None = None
    show_at_checkin: bool | None = None
    resolved_at: dt.datetime | None = None
    resolved_by: str | None = None


class ReservationTraceRead(SQLModel):
    """Fields returned when reading a ReservationTrace."""

    id: UUID
    tenant_id: UUID
    reservation_id: UUID
    kind: str
    department: str | None
    body: str
    due_at: dt.datetime | None
    show_at_checkin: bool
    resolved_at: dt.datetime | None
    resolved_by: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
