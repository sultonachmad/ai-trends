"""StaffRole entity — table ``staffrole``.

Tenant database, B. Staff, vendors & tenant-scoped roles.

Tenant-defined role (front desk, housekeeper, revenue manager …).

Mirrors .ttest/contexts/schema-tenant.sql; the Alembic migration creates the table.
"""

import datetime as dt
from uuid import UUID

from sqlalchemy import Text, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.crud.base_model import MIGRATION_ONLY, TenantEntity


class StaffRole(TenantEntity, table=True):
    """Tenant-defined role (front desk, housekeeper, revenue manager …)."""

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="staffrole_tenant_id_id_key"),
        UniqueConstraint("tenant_id", "code", name="staffrole_tenant_id_code_key"),
        MIGRATION_ONLY,
    )

    code: str = Field(sa_type=Text)
    name: str = Field(sa_type=Text)
    description: str | None = Field(default=None, sa_type=Text)
    is_system: bool = Field(
        default=False,
        sa_column_kwargs={"server_default": text("false")},
        description="seeded template, not deletable",
    )


class StaffRoleCreate(SQLModel):
    """Fields accepted when creating a StaffRole."""

    code: str
    name: str
    description: str | None = None
    is_system: bool = False


class StaffRoleUpdate(SQLModel):
    """Fields accepted when patching a StaffRole (all optional)."""

    code: str | None = None
    name: str | None = None
    description: str | None = None
    is_system: bool | None = None


class StaffRoleRead(SQLModel):
    """Fields returned when reading a StaffRole."""

    id: UUID
    tenant_id: UUID
    code: str
    name: str
    description: str | None
    is_system: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str | None
    updated_by: str | None
