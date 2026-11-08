"""RBAC management routers.

Registers resource groups under a single `rbac_router` that is included
in `main.py` via the prefab integrate snippet:

    GET/POST    /api/roles
    GET/PATCH/DELETE /api/roles/{id}
    GET/PUT     /api/roles/{id}/permissions   — replace permission set
    GET         /api/permissions              — read-only; populated by seed
    GET         /api/users                    — list users + their roles
    GET/PUT     /api/users/{id}/roles         — replace role set

Navigation menus are NOT managed here — they are read from backend/docs/rbac-spec.yaml
(see app/rbac/me.py). Edit the yaml file to add/remove/reorder menu items.

Each endpoint declares its permission code via `require_permission()` which
simultaneously enforces access AND registers the code for seed auto-discovery.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.rbac.dependencies import get_user_roles, require_permission
from app.rbac.models import Permission, Role, RolePermission, UserRole

rbac_router = APIRouter(tags=["rbac"])


# ── Pydantic schemas ─────────────────────────────────────────────────────────


class RoleCreate(BaseModel):
    name: str
    description: str | None = None


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class RoleOut(BaseModel):
    id: int
    name: str
    description: str | None

    class Config:
        from_attributes = True


class PermissionOut(BaseModel):
    id: int
    code: str
    description: str | None
    type: str

    class Config:
        from_attributes = True


class UserOut(BaseModel):
    id: int
    email: str
    roles: list[str] = []

    class Config:
        from_attributes = True


# ── Roles ────────────────────────────────────────────────────────────────────


@rbac_router.get("/api/roles", response_model=list[RoleOut])
async def list_roles(
    user: dict = require_permission("roles:view", "View and manage roles"),
    db: AsyncSession = Depends(get_session),
) -> list[Role]:
    result = await db.exec(select(Role))
    return list(result.all())


@rbac_router.post("/api/roles", response_model=RoleOut, status_code=201)
async def create_role(
    body: RoleCreate,
    user: dict = require_permission("roles:add", "Create a new role"),
    db: AsyncSession = Depends(get_session),
) -> Role:
    existing = (await db.exec(select(Role).where(Role.name == body.name))).first()
    if existing:
        raise HTTPException(status_code=409, detail="Role name already exists")
    role = Role(
        name=body.name,
        description=body.description,
        created_by=user.get("email"),
        updated_by=user.get("email"),
    )
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return role


@rbac_router.get("/api/roles/{role_id}", response_model=RoleOut)
async def get_role(
    role_id: int,
    user: dict = require_permission("roles:view", "Get a role"),
    db: AsyncSession = Depends(get_session),
) -> Role:
    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


@rbac_router.patch("/api/roles/{role_id}", response_model=RoleOut)
async def update_role(
    role_id: int,
    body: RoleUpdate,
    user: dict = require_permission("roles:edit", "Edit and delete roles"),
    db: AsyncSession = Depends(get_session),
) -> Role:
    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(role, k, v)
    role.updated_by = user.get("email")
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return role


@rbac_router.delete("/api/roles/{role_id}", status_code=204)
async def delete_role(
    role_id: int,
    user: dict = require_permission("roles:delete", "Delete a role"),
    db: AsyncSession = Depends(get_session),
) -> None:
    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    await db.delete(role)
    await db.commit()


# ── Role ↔ Permission assignment ─────────────────────────────────────────────


@rbac_router.get("/api/roles/{role_id}/permissions", response_model=list[PermissionOut])
async def get_role_permissions(
    role_id: int,
    user: dict = require_permission("roles:view", "View role permissions"),
    db: AsyncSession = Depends(get_session),
) -> list[Permission]:
    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    result = await db.exec(
        select(Permission)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == role_id)
    )
    return list(result.all())


@rbac_router.put("/api/roles/{role_id}/permissions", response_model=list[PermissionOut])
async def set_role_permissions(
    role_id: int,
    permission_ids: list[int],
    user: dict = require_permission("roles:edit", "Set role permissions"),
    db: AsyncSession = Depends(get_session),
) -> list[Permission]:
    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    existing_rps = list(
        (await db.exec(select(RolePermission).where(RolePermission.role_id == role_id))).all()
    )
    for rp in existing_rps:
        await db.delete(rp)
    await db.commit()
    for perm_id in permission_ids:
        perm = await db.get(Permission, perm_id)
        if perm:
            db.add(RolePermission(role_id=role_id, permission_id=perm_id))
    await db.commit()
    result = await db.exec(
        select(Permission)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == role_id)
    )
    return list(result.all())


# ── Permissions (read-only — managed by seed) ─────────────────────────────────


@rbac_router.get("/api/permissions", response_model=list[PermissionOut])
async def list_permissions(
    user: dict = require_permission("permissions:view", "List all permissions"),
    db: AsyncSession = Depends(get_session),
) -> list[Permission]:
    result = await db.exec(select(Permission))
    return list(result.all())


@rbac_router.get("/api/permissions/{permission_id}", response_model=PermissionOut)
async def get_permission(
    permission_id: int,
    user: dict = require_permission("permissions:view", "Get a permission"),
    db: AsyncSession = Depends(get_session),
) -> Permission:
    perm = await db.get(Permission, permission_id)
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    return perm


# ── Users ────────────────────────────────────────────────────────────────────


@rbac_router.get("/api/users", response_model=list[UserOut])
async def list_users(
    user: dict = require_permission("users:view", "List all users"),
    db: AsyncSession = Depends(get_session),
) -> list[UserOut]:
    from app.auth.models import User as AuthUser

    result = await db.exec(select(AuthUser))
    users = list(result.all())
    out = []
    for u in users:
        roles = await get_user_roles(u.id, db)
        out.append(UserOut(id=u.id, email=u.email, roles=roles))
    return out


@rbac_router.get("/api/users/{user_id}/roles", response_model=list[str])
async def get_user_role_list(
    user_id: int,
    user: dict = require_permission("users:view", "View user roles"),
    db: AsyncSession = Depends(get_session),
) -> list[str]:
    return await get_user_roles(user_id, db)


@rbac_router.put("/api/users/{user_id}/roles", response_model=list[str])
async def set_user_roles(
    user_id: int,
    role_ids: list[int],
    user: dict = require_permission("users:edit", "Assign user roles"),
    db: AsyncSession = Depends(get_session),
) -> list[str]:
    from app.auth.models import User as AuthUser

    target = await db.get(AuthUser, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    existing_urs = list(
        (await db.exec(select(UserRole).where(UserRole.user_id == user_id))).all()
    )
    for ur in existing_urs:
        await db.delete(ur)
    await db.commit()
    for role_id in role_ids:
        role = await db.get(Role, role_id)
        if role:
            db.add(UserRole(user_id=user_id, role_id=role_id))
    await db.commit()
    return await get_user_roles(user_id, db)
