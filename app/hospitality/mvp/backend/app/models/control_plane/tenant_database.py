"""TenantDatabase entity — table ``tenantdatabase``.

Control-plane database, Control plane.

Routing record: one per tenant. The API resolves tenant -> connection here, caches it, and opens
the session against the right database/schema.

Mirrors .ttest/contexts/schema-control-plane.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
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
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, UUIDEntity, utc_datetime_field

TenantDatabaseIsolationMode = Literal[
    "pooled_rls",
    "dedicated_schema",
    "dedicated_db",
]
TenantDatabaseStatus = Literal[
    "provisioning",
    "ready",
    "migrating",
    "read_only",
    "moving",
    "archived",
    "failed",
]


class TenantDatabase(UUIDEntity, table=True):
    """
    Routing record: one per tenant. The API resolves tenant -> connection here, caches it, and
    opens the session against the right database/schema.
    """

    __table_args__ = (
        UniqueConstraint("tenant_id", name="tenantdatabase_tenant_id_key"),
        ForeignKeyConstraint(
            ["tenant_id"], ["tenant.id"], name="tenantdatabase_tenant_id_fkey", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["cluster_id"], ["dbcluster.id"], name="tenantdatabase_cluster_id_fkey"
        ),
        CheckConstraint(
            "isolation_mode IN ('pooled_rls', 'dedicated_schema', 'dedicated_db')",
            name="tenantdatabase_isolation_mode_check",
        ),
        CheckConstraint(
            (
                "status IN ('provisioning', 'ready', 'migrating', 'read_only', 'moving', "
                "'archived', 'failed')"
            ),
            name="tenantdatabase_status_check",
        ),
        Index("ix_tenantdatabase_cluster", "cluster_id"),
        MIGRATION_ONLY,
    )

    tenant_id: UUID = Field(sa_type=Uuid)
    cluster_id: UUID = Field(sa_type=Uuid)
    isolation_mode: str = Field(sa_type=Text)
    database_name: str = Field(sa_type=Text)
    schema_name: str = Field(
        default="public", sa_type=Text, sa_column_kwargs={"server_default": text("'public'::text")}
    )
    app_role_name: str | None = Field(
        default=None,
        sa_type=Text,
        description="DB role the API uses for this tenant (dedicated modes)",
    )
    credentials_secret_ref: str | None = Field(
        default=None, sa_type=Text, description="secret-manager key for dedicated credentials"
    )
    schema_version: str | None = Field(
        default=None, sa_type=Text, description="alembic revision applied"
    )
    status: str = Field(
        default="provisioning",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'provisioning'::text")},
    )
    last_migrated_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]


class TenantDatabaseCreate(SQLModel):
    """Fields accepted when creating a TenantDatabase."""

    tenant_id: UUID
    cluster_id: UUID
    isolation_mode: TenantDatabaseIsolationMode
    database_name: str
    schema_name: str = "public"
    app_role_name: str | None = None
    credentials_secret_ref: str | None = None
    schema_version: str | None = None
    status: TenantDatabaseStatus = "provisioning"
    last_migrated_at: dt.datetime | None = None


class TenantDatabaseUpdate(SQLModel):
    """Fields accepted when patching a TenantDatabase (all optional)."""

    tenant_id: UUID | None = None
    cluster_id: UUID | None = None
    isolation_mode: TenantDatabaseIsolationMode | None = None
    database_name: str | None = None
    schema_name: str | None = None
    app_role_name: str | None = None
    credentials_secret_ref: str | None = None
    schema_version: str | None = None
    status: TenantDatabaseStatus | None = None
    last_migrated_at: dt.datetime | None = None


class TenantDatabaseRead(SQLModel):
    """Fields returned when reading a TenantDatabase."""

    id: UUID
    tenant_id: UUID
    cluster_id: UUID
    isolation_mode: str
    database_name: str
    schema_name: str
    app_role_name: str | None
    credentials_secret_ref: str | None
    schema_version: str | None
    status: str
    last_migrated_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
