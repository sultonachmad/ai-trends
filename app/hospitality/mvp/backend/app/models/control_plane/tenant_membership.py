"""TenantMembership entity — table ``tenantmembership``.

Control-plane database, Control plane.

User ↔ tenant link (a user may belong to several tenants).

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

TenantMembershipStatus = Literal[
    "invited",
    "active",
    "suspended",
    "removed",
]


class TenantMembership(UUIDEntity, table=True):
    """User ↔ tenant link (a user may belong to several tenants)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="tenantmembership_tenant_id_user_id_key"),
        ForeignKeyConstraint(
            ["tenant_id"], ["tenant.id"], name="tenantmembership_tenant_id_fkey", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["user_id"], ["user.id"], name="tenantmembership_user_id_fkey", ondelete="CASCADE"
        ),
        CheckConstraint(
            "status IN ('invited', 'active', 'suspended', 'removed')",
            name="tenantmembership_status_check",
        ),
        Index("ix_tenantmembership_user", "user_id"),
        MIGRATION_ONLY,
    )

    tenant_id: UUID = Field(sa_type=Uuid)
    user_id: int = Field()
    status: str = Field(
        default="active", sa_type=Text, sa_column_kwargs={"server_default": text("'active'::text")}
    )
    is_tenant_owner: bool = Field(default=False, sa_column_kwargs={"server_default": text("false")})
    staff_member_id: UUID | None = Field(
        default=None, sa_type=Uuid, description="tenant-DB staffmember.id (no cross-DB FK)"
    )
    last_property_id: UUID | None = Field(
        default=None, sa_type=Uuid, description="UI convenience: last property opened"
    )
    joined_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]


class TenantMembershipCreate(SQLModel):
    """Fields accepted when creating a TenantMembership."""

    tenant_id: UUID
    user_id: int
    status: TenantMembershipStatus = "active"
    is_tenant_owner: bool = False
    staff_member_id: UUID | None = None
    last_property_id: UUID | None = None
    joined_at: dt.datetime | None = None


class TenantMembershipUpdate(SQLModel):
    """Fields accepted when patching a TenantMembership (all optional)."""

    tenant_id: UUID | None = None
    user_id: int | None = None
    status: TenantMembershipStatus | None = None
    is_tenant_owner: bool | None = None
    staff_member_id: UUID | None = None
    last_property_id: UUID | None = None
    joined_at: dt.datetime | None = None


class TenantMembershipRead(SQLModel):
    """Fields returned when reading a TenantMembership."""

    id: UUID
    tenant_id: UUID
    user_id: int
    status: str
    is_tenant_owner: bool
    staff_member_id: UUID | None
    last_property_id: UUID | None
    joined_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
