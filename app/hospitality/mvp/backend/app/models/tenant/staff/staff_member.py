"""StaffMember entity — table ``staffmember``.

Tenant database, B. Staff, vendors & tenant-scoped roles.

Tenant-specific staff profile. Login identity = control-plane "user".

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
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

from app.crud.base_model import MIGRATION_ONLY, TenantEntity

StaffMemberDepartment = Literal[
    "front_office",
    "housekeeping",
    "maintenance",
    "fnb",
    "sales",
    "revenue",
    "finance",
    "management",
    "other",
]
StaffMemberUiMode = Literal[
    "classic",
    "guided",
]
StaffMemberStatus = Literal[
    "active",
    "suspended",
    "left",
]


class StaffMember(TenantEntity, table=True):
    """Tenant-specific staff profile. Login identity = control-plane "user"."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="staffmember_tenant_id_id_key"),
        ForeignKeyConstraint(
            ["tenant_id", "vendor_id"],
            ["vendor.tenant_id", "vendor.id"],
            name="staffmember_tenant_id_vendor_id_fkey",
            ondelete="SET NULL (vendor_id)",
        ),
        CheckConstraint(
            (
                "department IN ('front_office', 'housekeeping', 'maintenance', 'fnb', "
                "'sales', 'revenue', 'finance', 'management', 'other')"
            ),
            name="staffmember_department_check",
        ),
        CheckConstraint("ui_mode IN ('classic', 'guided')", name="staffmember_ui_mode_check"),
        CheckConstraint(
            "status IN ('active', 'suspended', 'left')", name="staffmember_status_check"
        ),
        Index(
            "ux_staffmember_user",
            "tenant_id",
            "user_id",
            unique=True,
            postgresql_where=text("user_id IS NOT NULL"),
        ),
        MIGRATION_ONLY,
    )

    user_id: int | None = Field(
        default=None, description='control-plane "user".id; NULL for PIN-only staff'
    )
    vendor_id: UUID | None = Field(
        default=None, sa_type=Uuid, description="set for external vendor workers"
    )
    display_name: str = Field(sa_type=Text)
    email: str | None = Field(default=None, sa_type=Text)
    phone: str | None = Field(default=None, sa_type=Text)
    employee_code: str | None = Field(default=None, sa_type=Text)
    department: str | None = Field(default=None, sa_type=Text)
    language: str = Field(
        default="id-ID", sa_type=Text, sa_column_kwargs={"server_default": text("'id-ID'::text")}
    )
    ui_mode: str = Field(
        default="classic",
        sa_type=Text,
        sa_column_kwargs={"server_default": text("'classic'::text")},
    )
    pin_hash: str | None = Field(
        default=None, sa_type=Text, description="quick login on shared housekeeping devices"
    )
    status: str = Field(
        default="active", sa_type=Text, sa_column_kwargs={"server_default": text("'active'::text")}
    )
    valid_until: dt.date | None = Field(default=None, description="seasonal / temporary staff")


class StaffMemberCreate(SQLModel):
    """Fields accepted when creating a StaffMember."""

    user_id: int | None = None
    vendor_id: UUID | None = None
    display_name: str
    email: str | None = None
    phone: str | None = None
    employee_code: str | None = None
    department: StaffMemberDepartment | None = None
    language: str = "id-ID"
    ui_mode: StaffMemberUiMode = "classic"
    status: StaffMemberStatus = "active"
    valid_until: dt.date | None = None


class StaffMemberUpdate(SQLModel):
    """Fields accepted when patching a StaffMember (all optional)."""

    user_id: int | None = None
    vendor_id: UUID | None = None
    display_name: str | None = None
    email: str | None = None
    phone: str | None = None
    employee_code: str | None = None
    department: StaffMemberDepartment | None = None
    language: str | None = None
    ui_mode: StaffMemberUiMode | None = None
    status: StaffMemberStatus | None = None
    valid_until: dt.date | None = None


class StaffMemberRead(SQLModel):
    """Fields returned when reading a StaffMember (never returns: pin_hash)."""

    id: UUID
    tenant_id: UUID
    user_id: int | None
    vendor_id: UUID | None
    display_name: str
    email: str | None
    phone: str | None
    employee_code: str | None
    department: str | None
    language: str
    ui_mode: str
    status: str
    valid_until: dt.date | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
