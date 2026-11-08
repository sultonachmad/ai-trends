"""TenantMigration entity — table ``tenantmigration``.

Control-plane database, Control plane.

Migration / move history per tenant database.

Mirrors .ttest/contexts/schema-control-plane.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, UUIDEntity, utc_datetime_field

TenantMigrationKind = Literal[
    "schema_upgrade",
    "schema_downgrade",
    "move_cluster",
    "pooled_to_dedicated",
    "dedicated_to_pooled",
    "restore",
]
TenantMigrationStatus = Literal[
    "pending",
    "running",
    "succeeded",
    "failed",
    "rolled_back",
]


class TenantMigration(UUIDEntity, table=True):
    """Migration / move history per tenant database."""

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_database_id"],
            ["tenantdatabase.id"],
            name="tenantmigration_tenant_database_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["from_cluster_id"], ["dbcluster.id"], name="tenantmigration_from_cluster_id_fkey"
        ),
        ForeignKeyConstraint(
            ["to_cluster_id"], ["dbcluster.id"], name="tenantmigration_to_cluster_id_fkey"
        ),
        CheckConstraint(
            (
                "kind IN ('schema_upgrade', 'schema_downgrade', 'move_cluster', "
                "'pooled_to_dedicated', 'dedicated_to_pooled', 'restore')"
            ),
            name="tenantmigration_kind_check",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'rolled_back')",
            name="tenantmigration_status_check",
        ),
        MIGRATION_ONLY,
    )

    tenant_database_id: UUID = Field(sa_type=Uuid)
    kind: str = Field(sa_type=Text)
    from_version: str | None = Field(default=None, sa_type=Text)
    to_version: str | None = Field(default=None, sa_type=Text)
    from_cluster_id: UUID | None = Field(default=None, sa_type=Uuid)
    to_cluster_id: UUID | None = Field(default=None, sa_type=Uuid)
    status: str = Field(
        default="pending",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'pending'::text")},
    )
    started_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    finished_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    log: str | None = Field(default=None, sa_type=Text)


class TenantMigrationCreate(SQLModel):
    """Fields accepted when creating a TenantMigration."""

    tenant_database_id: UUID
    kind: TenantMigrationKind
    from_version: str | None = None
    to_version: str | None = None
    from_cluster_id: UUID | None = None
    to_cluster_id: UUID | None = None
    status: TenantMigrationStatus = "pending"
    started_at: dt.datetime | None = None
    finished_at: dt.datetime | None = None
    log: str | None = None


class TenantMigrationUpdate(SQLModel):
    """Fields accepted when patching a TenantMigration (all optional)."""

    tenant_database_id: UUID | None = None
    kind: TenantMigrationKind | None = None
    from_version: str | None = None
    to_version: str | None = None
    from_cluster_id: UUID | None = None
    to_cluster_id: UUID | None = None
    status: TenantMigrationStatus | None = None
    started_at: dt.datetime | None = None
    finished_at: dt.datetime | None = None
    log: str | None = None


class TenantMigrationRead(SQLModel):
    """Fields returned when reading a TenantMigration."""

    id: UUID
    tenant_database_id: UUID
    kind: str
    from_version: str | None
    to_version: str | None
    from_cluster_id: UUID | None
    to_cluster_id: UUID | None
    status: str
    started_at: dt.datetime | None
    finished_at: dt.datetime | None
    log: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
