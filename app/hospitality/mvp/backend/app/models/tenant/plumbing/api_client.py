"""ApiClient entity — table ``apiclient``.

Tenant database, T. Platform plumbing.

API keys; request idempotency.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity, utc_datetime_field

ApiClientStatus = Literal[
    "active",
    "revoked",
]


class ApiClient(TenantEntity, table=True):
    """API keys; request idempotency."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="apiclient_tenant_id_id_key"),
        UniqueConstraint("key_hash", name="apiclient_key_hash_key"),
        CheckConstraint("status IN ('active', 'revoked')", name="apiclient_status_check"),
        MIGRATION_ONLY,
    )

    name: str = Field(sa_type=Text)
    key_prefix: str = Field(sa_type=Text, description="shown in UI to identify the key")
    key_hash: str = Field(sa_type=Text)
    scopes: list[str] = Field(
        default_factory=list,
        sa_type=ARRAY(Text),
        sa_column_kwargs={"server_default": text("'{}'::text[]")},
    )
    property_ids: list[UUID] = Field(
        default_factory=list,
        sa_type=ARRAY(Uuid),
        sa_column_kwargs={"server_default": text("'{}'::uuid[]")},
        description="empty = all",
    )
    expires_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    last_used_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    status: str = Field(
        default="active", sa_type=Text, sa_column_kwargs={"server_default": text("'active'::text")}
    )


class ApiClientCreate(SQLModel):
    """Fields accepted when creating a ApiClient."""

    name: str
    key_prefix: str
    scopes: list[str] = Field(default_factory=list)
    property_ids: list[UUID] = Field(default_factory=list)
    expires_at: dt.datetime | None = None
    last_used_at: dt.datetime | None = None
    status: ApiClientStatus = "active"


class ApiClientUpdate(SQLModel):
    """Fields accepted when patching a ApiClient (all optional)."""

    name: str | None = None
    key_prefix: str | None = None
    scopes: list[str] | None = None
    property_ids: list[UUID] | None = None
    expires_at: dt.datetime | None = None
    last_used_at: dt.datetime | None = None
    status: ApiClientStatus | None = None


class ApiClientRead(SQLModel):
    """Fields returned when reading a ApiClient (never returns: key_hash)."""

    id: UUID
    tenant_id: UUID
    name: str
    key_prefix: str
    scopes: list[str]
    property_ids: list[UUID]
    expires_at: dt.datetime | None
    last_used_at: dt.datetime | None
    status: str
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
