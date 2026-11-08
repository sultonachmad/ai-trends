"""StaffRolePermission entity — table ``staffrolepermission``.

Tenant database, B. Staff, vendors & tenant-scoped roles.

Permission codes are the same codes as backend/docs/rbac-spec.yaml (module:action).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

from uuid import UUID

from sqlalchemy import ForeignKeyConstraint, Text, Uuid
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY


class StaffRolePermission(SQLModel, table=True):
    """Permission codes are the same codes as backend/docs/rbac-spec.yaml (module:action)."""

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "role_id"],
            ["staffrole.tenant_id", "staffrole.id"],
            name="staffrolepermission_tenant_id_role_id_fkey",
            ondelete="CASCADE",
        ),
        MIGRATION_ONLY,
    )

    tenant_id: UUID = Field(primary_key=True, sa_type=Uuid)
    role_id: UUID = Field(primary_key=True, sa_type=Uuid)
    permission_code: str = Field(primary_key=True, sa_type=Text)


class StaffRolePermissionCreate(SQLModel):
    """Fields accepted when creating a StaffRolePermission."""

    role_id: UUID
    permission_code: str


class StaffRolePermissionUpdate(SQLModel):
    """
    Patch shape for a StaffRolePermission: every column is part of the key, nothing is
    patchable.
    """

    pass


class StaffRolePermissionRead(SQLModel):
    """Fields returned when reading a StaffRolePermission."""

    tenant_id: UUID
    role_id: UUID
    permission_code: str
