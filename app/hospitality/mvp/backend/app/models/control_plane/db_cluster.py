"""DbCluster entity — table ``dbcluster``.

Control-plane database, Control plane.

A PostgreSQL server/cluster that hosts tenant databases.

Mirrors .ttest/contexts/schema-control-plane.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, Text, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, UUIDEntity

DbClusterKind = Literal[
    "pooled",
    "dedicated",
    "mixed",
]
DbClusterStatus = Literal[
    "active",
    "draining",
    "read_only",
    "retired",
]


class DbCluster(UUIDEntity, table=True):
    """A PostgreSQL server/cluster that hosts tenant databases."""

    __table_args__ = (
        UniqueConstraint("code", name="dbcluster_code_key"),
        CheckConstraint("kind IN ('pooled', 'dedicated', 'mixed')", name="dbcluster_kind_check"),
        CheckConstraint(
            "status IN ('active', 'draining', 'read_only', 'retired')",
            name="dbcluster_status_check",
        ),
        MIGRATION_ONLY,
    )

    code: str = Field(sa_type=Text, description="'jkt-pooled-01', 'jkt-dedicated-07'")
    region: str = Field(sa_type=Text, description="cloud region, e.g. 'ap-southeast-3' (Jakarta)")
    kind: str = Field(sa_type=Text)
    connection_secret_ref: str = Field(
        sa_type=Text, description="secret-manager key; NEVER a password"
    )
    replica_secret_ref: str | None = Field(
        default=None, sa_type=Text, description="optional read replica for reporting/BI"
    )
    max_tenants: int | None = Field(default=None, description="capacity hint for pooled clusters")
    status: str = Field(
        default="active", sa_type=Text, sa_column_kwargs={"server_default": text("'active'::text")}
    )


class DbClusterCreate(SQLModel):
    """Fields accepted when creating a DbCluster."""

    code: str
    region: str
    kind: DbClusterKind
    connection_secret_ref: str
    replica_secret_ref: str | None = None
    max_tenants: int | None = None
    status: DbClusterStatus = "active"


class DbClusterUpdate(SQLModel):
    """Fields accepted when patching a DbCluster (all optional)."""

    code: str | None = None
    region: str | None = None
    kind: DbClusterKind | None = None
    connection_secret_ref: str | None = None
    replica_secret_ref: str | None = None
    max_tenants: int | None = None
    status: DbClusterStatus | None = None


class DbClusterRead(SQLModel):
    """Fields returned when reading a DbCluster."""

    id: UUID
    code: str
    region: str
    kind: str
    connection_secret_ref: str
    replica_secret_ref: str | None
    max_tenants: int | None
    status: str
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
