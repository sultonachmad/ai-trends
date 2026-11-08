"""OutboxEvent entity — table ``outboxevent``.

Tenant database, T. Platform plumbing.

Transactional outbox: written in the same transaction as the business change, relayed to the
event bus (CRM, channel manager, RMS, control-plane directory).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any
from uuid import UUID

from sqlalchemy import Index, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field


class OutboxEvent(TenantRecord, table=True):
    """
    Transactional outbox: written in the same transaction as the business change, relayed to the
    event bus (CRM, channel manager, RMS, control-plane directory).
    """

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="outboxevent_tenant_id_id_key"),
        Index(
            "ix_outboxevent_unpublished",
            "occurred_at",
            postgresql_where=text("published_at IS NULL"),
        ),
        MIGRATION_ONLY,
    )

    aggregate_type: str = Field(sa_type=Text, description="'reservation','folio','unit','task'")
    aggregate_id: UUID = Field(sa_type=Uuid)
    event_type: str = Field(sa_type=Text, description="'reservation.created','unit.status_changed'")
    payload: Any = Field(sa_type=JSONB, nullable=False)
    occurred_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]
    published_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    attempts: int = Field(default=0, sa_column_kwargs={"server_default": text("0")})
    last_error: str | None = Field(default=None, sa_type=Text)


class OutboxEventCreate(SQLModel):
    """Fields accepted when creating a OutboxEvent."""

    aggregate_type: str
    aggregate_id: UUID
    event_type: str
    payload: Any
    occurred_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))
    published_at: dt.datetime | None = None
    attempts: int = 0
    last_error: str | None = None


class OutboxEventUpdate(SQLModel):
    """Fields accepted when patching a OutboxEvent (all optional)."""

    aggregate_type: str | None = None
    aggregate_id: UUID | None = None
    event_type: str | None = None
    payload: Any = None
    occurred_at: dt.datetime | None = None
    published_at: dt.datetime | None = None
    attempts: int | None = None
    last_error: str | None = None


class OutboxEventRead(SQLModel):
    """Fields returned when reading a OutboxEvent."""

    id: UUID
    tenant_id: UUID
    aggregate_type: str
    aggregate_id: UUID
    event_type: str
    payload: Any
    occurred_at: dt.datetime
    published_at: dt.datetime | None
    attempts: int
    last_error: str | None
