"""FastAPI dependencies and permission-check helpers for RBAC.

Usage — protect a route with a permission code:

    from app.rbac.dependencies import require_permission

    @router.get("/roles")
    async def list_roles(
        user: dict = require_permission("roles:view", "List all roles"),
        db: AsyncSession = Depends(get_session),
    ) -> list[RoleOut]:
        ...

`require_permission(code, desc)` does two things at call time (module-import
time, i.e. when the router module is first imported):
  1. Registers `code → description` in `_PERMISSION_REGISTRY` so the startup
     seed can upsert a Permission row without manual duplication.
  2. Returns a `Depends(...)` object that FastAPI injects as a route
     dependency — it validates that the current user holds `code` before the
     route handler runs.

Admin bypass: a user whose roles include any role named "admin" passes every
permission check without a per-permission DB lookup.
"""

from typing import Any

from fastapi import Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.session.dependencies import get_current_user

# Populated at import time as routers call require_permission().
# The startup seed reads this to upsert Permission rows.
_PERMISSION_REGISTRY: dict[str, str] = {}


async def _is_admin(user_id: int, db: AsyncSession) -> bool:
    """True when the user holds any role named 'admin'.

    `user_id` must be an integer PK — convert from session dict with
    `int(user["user_id"])` (session/router.py stores it as str(user.id)).
    """
    from app.rbac.models import Role, UserRole

    result = await db.exec(
        select(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id, Role.name == "admin")
    )
    return result.first() is not None


async def _user_has_permission(user_id: int, code: str, db: AsyncSession) -> bool:
    from app.rbac.models import Permission, Role, RolePermission, UserRole

    if await _is_admin(user_id, db):
        return True

    result = await db.exec(
        select(Permission)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id, Permission.code == code)
    )
    return result.first() is not None


async def get_user_permissions(user_id: int, db: AsyncSession) -> list[str]:
    """Return all permission codes held by `user_id` (empty list if none)."""
    from app.rbac.models import Permission, Role, RolePermission, UserRole

    result = await db.exec(
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )
    return list(result.all())


async def get_user_roles(user_id: int, db: AsyncSession) -> list[str]:
    """Return role names held by `user_id`."""
    from app.rbac.models import Role, UserRole

    result = await db.exec(
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )
    return list(result.all())


def require_permission(code: str, description: str = "") -> Any:
    """Return a FastAPI `Depends` that enforces `code` AND registers it for seeding.

    Call this as a default-value expression in a route function parameter:

        user: dict = require_permission("roles:view", "List all roles")

    FastAPI recognises the returned `Depends(...)` object and injects the
    resolved user dict (or raises 403 if the permission is absent).
    """
    _PERMISSION_REGISTRY.setdefault(code, description)

    async def _check(
        user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_session),
    ) -> dict:
        user_id = int(user["user_id"])
        if not await _user_has_permission(user_id, code, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {code}",
            )
        return user

    return Depends(_check)
