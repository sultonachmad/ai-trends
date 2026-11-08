"""TenantAuditEntry entity — table ``tenantauditentry``.

Tenant database, T. Platform plumbing.

Tenant-scoped audit trail. Same shape as the audit prefab's audit_entries (hash-chained) plus
tenant_id; the chain is per tenant.

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Any
from uuid import UUID

from sqlalchemy import Index, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantRecord, utc_datetime_field


class TenantAuditEntry(TenantRecord, table=True):
    """
    Tenant-scoped audit trail. Same shape as the audit prefab's audit_entries (hash-chained)
    plus tenant_id; the chain is per tenant.
    """

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="tenantauditentry_tenant_id_id_key"),
        Index(
            "ix_tenantauditentry_entity", "tenant_id", "entity_table", "entity_id", "occurred_at"
        ),
        Index("ix_tenantauditentry_time", "tenant_id", "occurred_at"),
        MIGRATION_ONLY,
    )

    property_id: UUID | None = Field(default=None, sa_type=Uuid)
    event_id: str = Field(sa_type=Text, description="AUDIT_EVENTS registry key")
    actor_id: str | None = Field(default=None, sa_type=Text)
    occurred_at: dt.datetime = utc_datetime_field(
        nullable=False, default_now=True, server_default_now=True
    )  # type: ignore[assignment]
    entity_table: str | None = Field(default=None, sa_type=Text)
    entity_id: UUID | None = Field(default=None, sa_type=Uuid)
    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": text("'{}'::jsonb")},
    )
    request_id: str | None = Field(default=None, sa_type=Text)
    session_id: str | None = Field(default=None, sa_type=Text)
    ip_address: str | None = Field(default=None, sa_type=INET)
    subject_key: str | None = Field(default=None, sa_type=Text, description="shredded on erasure")
    anonymised: bool = Field(default=False, sa_column_kwargs={"server_default": text("false")})
    prev_hash: str | None = Field(default=None, sa_type=Text)
    entry_hash: str = Field(sa_type=Text)


class TenantAuditEntryCreate(SQLModel):
    """Fields accepted when creating a TenantAuditEntry."""

    property_id: UUID | None = None
    event_id: str
    actor_id: str | None = None
    occurred_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))
    entity_table: str | None = None
    entity_id: UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None
    session_id: str | None = None
    ip_address: str | None = None
    subject_key: str | None = None
    anonymised: bool = False


class TenantAuditEntryUpdate(SQLModel):
    """Fields accepted when patching a TenantAuditEntry (all optional)."""

    property_id: UUID | None = None
    event_id: str | None = None
    actor_id: str | None = None
    occurred_at: dt.datetime | None = None
    entity_table: str | None = None
    entity_id: UUID | None = None
    payload: dict[str, Any] | None = None
    request_id: str | None = None
    session_id: str | None = None
    ip_address: str | None = None
    subject_key: str | None = None
    anonymised: bool | None = None


class TenantAuditEntryRead(SQLModel):
    """Fields returned when reading a TenantAuditEntry."""

    id: UUID
    tenant_id: UUID
    property_id: UUID | None
    event_id: str
    actor_id: str | None
    occurred_at: dt.datetime
    entity_table: str | None
    entity_id: UUID | None
    payload: dict[str, Any]
    request_id: str | None
    session_id: str | None
    ip_address: str | None
    subject_key: str | None
    anonymised: bool
    prev_hash: str | None
    entry_hash: str
