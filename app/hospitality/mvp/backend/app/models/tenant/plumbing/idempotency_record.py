"""IdempotencyRecord entity — table ``idempotencyrecord``.

Tenant database, T. Platform plumbing.

API keys; request idempotency.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any
from uuid import UUID

from sqlalchemy import Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field


class IdempotencyRecord(TenantRecord, table=True):
    """API keys; request idempotency."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="idempotencyrecord_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id", "scope", "key", name="idempotencyrecord_tenant_id_scope_key_key"
        ),
        MIGRATION_ONLY,
    )

    scope: str = Field(sa_type=Text, description="'booking_engine.checkout','payment.capture'")
    key: str = Field(sa_type=Text)
    request_hash: str = Field(sa_type=Text)
    response: Any = Field(default=None, sa_type=JSONB, nullable=True)
    status_code: int | None = Field(default=None)
    expires_at: dt.datetime = utc_datetime_field(nullable=False)  # type: ignore[assignment]
    created_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]


class IdempotencyRecordCreate(SQLModel):
    """Fields accepted when creating a IdempotencyRecord."""

    scope: str
    key: str
    response: Any = None
    status_code: int | None = None
    expires_at: dt.datetime


class IdempotencyRecordUpdate(SQLModel):
    """Fields accepted when patching a IdempotencyRecord (all optional)."""

    scope: str | None = None
    key: str | None = None
    response: Any = None
    status_code: int | None = None
    expires_at: dt.datetime | None = None


class IdempotencyRecordRead(SQLModel):
    """Fields returned when reading a IdempotencyRecord (never returns: request_hash)."""

    id: UUID
    tenant_id: UUID
    scope: str
    key: str
    response: Any
    status_code: int | None
    expires_at: dt.datetime
    created_at: dt.datetime
