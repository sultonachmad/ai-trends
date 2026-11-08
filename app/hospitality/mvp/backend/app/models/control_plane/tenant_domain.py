"""TenantDomain entity — table ``tenantdomain``.

Control-plane database, Control plane.

Custom hostnames (booking engine, guest portal) -> tenant routing.

Mirrors .ttest/contexts/schema-control-plane.sql; the Alembic migration creates the table.
"""

import datetime as dt
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, Text, Uuid, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, UUIDEntity, utc_datetime_field

TenantDomainPurpose = Literal[
    "booking_engine",
    "guest_portal",
    "staff_app",
    "api",
]
TenantDomainStatus = Literal[
    "pending",
    "active",
    "failed",
    "disabled",
]


class TenantDomain(UUIDEntity, table=True):
    """Custom hostnames (booking engine, guest portal) -> tenant routing."""

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id"], ["tenant.id"], name="tenantdomain_tenant_id_fkey", ondelete="CASCADE"
        ),
        CheckConstraint(
            "purpose IN ('booking_engine', 'guest_portal', 'staff_app', 'api')",
            name="tenantdomain_purpose_check",
        ),
        CheckConstraint(
            "status IN ('pending', 'active', 'failed', 'disabled')",
            name="tenantdomain_status_check",
        ),
        Index("ux_tenantdomain_hostname", text("lower(hostname)"), unique=True),
        MIGRATION_ONLY,
    )

    tenant_id: UUID = Field(sa_type=Uuid)
    hostname: str = Field(sa_type=Text)
    purpose: str = Field(sa_type=Text)
    property_id: UUID | None = Field(
        default=None, sa_type=Uuid, description="tenant-DB property id (no cross-DB FK)"
    )
    verified_at: dt.datetime | None = utc_datetime_field(nullable=True)  # type: ignore[assignment]
    status: str = Field(
        default="pending",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'pending'::text")},
    )


class TenantDomainCreate(SQLModel):
    """Fields accepted when creating a TenantDomain."""

    tenant_id: UUID
    hostname: str
    purpose: TenantDomainPurpose
    property_id: UUID | None = None
    verified_at: dt.datetime | None = None
    status: TenantDomainStatus = "pending"


class TenantDomainUpdate(SQLModel):
    """Fields accepted when patching a TenantDomain (all optional)."""

    tenant_id: UUID | None = None
    hostname: str | None = None
    purpose: TenantDomainPurpose | None = None
    property_id: UUID | None = None
    verified_at: dt.datetime | None = None
    status: TenantDomainStatus | None = None


class TenantDomainRead(SQLModel):
    """Fields returned when reading a TenantDomain."""

    id: UUID
    tenant_id: UUID
    hostname: str
    purpose: str
    property_id: UUID | None
    verified_at: dt.datetime | None
    status: str
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
