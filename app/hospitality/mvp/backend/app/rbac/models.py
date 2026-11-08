"""SQLModel table definitions for RBAC.

Table layout:
    role             — named roles (admin, editor, viewer, …)
    user_roles       — M2M: users ↔ roles (composite PK, no audit columns)
    permission       — every granular action as a canonical code (module:action)
    role_permissions — M2M: roles ↔ permissions (composite PK, no audit columns)

Navigation menus are NOT stored in the database — they are read from
backend/docs/rbac-spec.yaml at runtime (see app/rbac/me.py).

Audit columns (created_at, updated_at, created_by, updated_by) and the
auto-increment `id` PK come from BaseEntity (→ TimestampMixin → SQLModel).
The M2M join tables (UserRole, RolePermission) use plain SQLModel because
they have composite PKs and need no audit trail.

No `from __future__ import annotations` here: SQLModel Relationship() fields
(if added later) need the class to be already resolved at field-evaluation
time, which the future import breaks.
"""

from enum import Enum

from sqlmodel import Field, SQLModel

from app.crud.base_model import BaseEntity


class PermissionType(str, Enum):
    api = "api"
    menu = "menu"
    button = "button"


class Role(BaseEntity, table=True):
    __tablename__ = "role"

    name: str = Field(unique=True, index=True, max_length=100)
    description: str | None = Field(default=None, nullable=True)


class UserRole(SQLModel, table=True):
    """M2M join — no audit columns, composite PK."""

    __tablename__ = "user_roles"

    user_id: int = Field(foreign_key="user.id", primary_key=True)
    role_id: int = Field(foreign_key="role.id", primary_key=True)


class Permission(BaseEntity, table=True):
    __tablename__ = "permission"

    code: str = Field(unique=True, index=True, max_length=200)
    description: str | None = Field(default=None, nullable=True)
    type: PermissionType = Field(default=PermissionType.api)


class RolePermission(SQLModel, table=True):
    """M2M join — no audit columns, composite PK."""

    __tablename__ = "role_permissions"

    role_id: int = Field(foreign_key="role.id", primary_key=True)
    permission_id: int = Field(foreign_key="permission.id", primary_key=True)
