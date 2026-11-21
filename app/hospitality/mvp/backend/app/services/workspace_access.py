"""Who may use the workspace's features: the roles behind the permission checks.

Every feature route checks a `module:view` / `module:edit` permission (rbac-spec.yaml
is the source of truth). Permissions are granted through roles, which an administrator
configures in /admin. Two things are wired here so a fresh property works at all:

* the **manager** role — created at startup and kept in step with every application
  permission that exists (the platform's own admin permissions excluded), so an
  administrator can assign "full access" in one click;
* the property owner — the user who creates a workspace gets manager automatically,
  and a startup backfill gives it to owners who signed up before roles existed.

Nobody else gets anything by default: a staff member sees only what an administrator
configures.
"""

import logging

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.control_plane import TenantMembership
from app.rbac.dependencies import _PERMISSION_REGISTRY, get_user_roles
from app.rbac.models import Permission, Role, RolePermission, UserRole

log = logging.getLogger(__name__)

MANAGER_ROLE = "manager"
# The platform's own administration; a property manager never needs these.
SYSTEM_PREFIXES = ("users:", "roles:", "permissions:", "menus:", "audit:", "features:")


def _application_codes() -> list[str]:
    return sorted(code for code in _PERMISSION_REGISTRY if not code.startswith(SYSTEM_PREFIXES))


async def ensure_manager_role(db: AsyncSession) -> Role:
    """The manager role with every application permission (new codes added, none removed).

    Removing is deliberate: an administrator may have tailored the role, and a startup
    must not undo that. Idempotent.
    """
    role = (await db.exec(select(Role).where(col(Role.name) == MANAGER_ROLE))).first()
    if role is None:
        role = Role(
            name=MANAGER_ROLE,
            description="Full access to this property's features (granted to property owners)",
            created_by="seed",
            updated_by="seed",
        )
        db.add(role)
        await db.flush()
    wanted = (
        (
            await db.exec(select(Permission).where(col(Permission.code).in_(_application_codes())))
        ).all()
        if _application_codes()
        else []
    )
    held = set(
        (
            await db.exec(
                select(col(RolePermission.permission_id)).where(
                    col(RolePermission.role_id) == role.id
                )
            )
        ).all()
    )
    for permission in wanted:
        if permission.id not in held:
            db.add(RolePermission(role_id=role.id, permission_id=permission.id))
    await db.commit()
    return role


async def grant_manager(db: AsyncSession, user_id: int) -> None:
    """Give the user the manager role, if they do not already hold it. Idempotent."""
    role = (await db.exec(select(Role).where(col(Role.name) == MANAGER_ROLE))).first()
    if role is None:
        role = await ensure_manager_role(db)
    existing = (
        await db.exec(
            select(UserRole).where(
                col(UserRole.user_id) == user_id, col(UserRole.role_id) == role.id
            )
        )
    ).first()
    if existing is None:
        db.add(UserRole(user_id=user_id, role_id=role.id))
        await db.commit()
        log.info("Manager role granted to user=%s", user_id)


async def backfill_owner_access(db: AsyncSession) -> int:
    """Manager for every property owner who holds no role at all (users from before roles).

    An owner who was deliberately given a narrower role is left exactly as configured.
    Skipped on databases without the control-plane tables (e.g. the SQLite test app).
    """
    from sqlalchemy import inspect

    connection = await db.connection()
    has_memberships = await connection.run_sync(
        lambda sync: inspect(sync).has_table("tenantmembership")
    )
    if not has_memberships:
        return 0
    owners = (
        await db.exec(
            select(col(TenantMembership.user_id))
            .where(col(TenantMembership.is_tenant_owner).is_(True))
            .distinct()
        )
    ).all()
    granted = 0
    for user_id in owners:
        if not await get_user_roles(user_id, db):
            await grant_manager(db, user_id)
            granted += 1
    if granted:
        log.info("Manager role backfilled to %s workspace owner(s)", granted)
    return granted
