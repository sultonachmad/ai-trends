"""StaffRoleAssignment entity — table ``staffroleassignment``.

Tenant database, B. Staff, vendors & tenant-scoped roles.

Role grant, optionally limited to one property (NULL property = all properties).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from uuid import UUID

from sqlalchemy import ForeignKeyConstraint, UniqueConstraint, Uuid
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity


class StaffRoleAssignment(TenantEntity, table=True):
    """Role grant, optionally limited to one property (NULL property = all properties)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="staffroleassignment_tenant_id_id_key"),
        UniqueConstraint(
            "tenant_id",
            "staff_member_id",
            "role_id",
            "property_id",
            name="staffroleassignment_tenant_id_staff_member_id_role_id_prope_key",
            postgresql_nulls_not_distinct=True,
        ),
        ForeignKeyConstraint(
            ["tenant_id", "staff_member_id"],
            ["staffmember.tenant_id", "staffmember.id"],
            name="staffroleassignment_tenant_id_staff_member_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "role_id"],
            ["staffrole.tenant_id", "staffrole.id"],
            name="staffroleassignment_tenant_id_role_id_fkey",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "property_id"],
            ["property.tenant_id", "property.id"],
            name="staffroleassignment_tenant_id_property_id_fkey",
            ondelete="CASCADE",
        ),
        MIGRATION_ONLY,
    )

    staff_member_id: UUID = Field(sa_type=Uuid)
    role_id: UUID = Field(sa_type=Uuid)
    property_id: UUID | None = Field(default=None, sa_type=Uuid)


class StaffRoleAssignmentCreate(SQLModel):
    """Fields accepted when creating a StaffRoleAssignment."""

    staff_member_id: UUID
    role_id: UUID
    property_id: UUID | None = None


class StaffRoleAssignmentUpdate(SQLModel):
    """Fields accepted when patching a StaffRoleAssignment (all optional)."""

    staff_member_id: UUID | None = None
    role_id: UUID | None = None
    property_id: UUID | None = None


class StaffRoleAssignmentRead(SQLModel):
    """Fields returned when reading a StaffRoleAssignment."""

    id: UUID
    tenant_id: UUID
    staff_member_id: UUID
    role_id: UUID
    property_id: UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
