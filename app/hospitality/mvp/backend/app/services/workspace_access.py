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


# Ready-made roles an owner can give a new staff member (rbac-spec.yaml describes them).
# Kept in step like manager: missing codes are added at startup, none removed.
FRONT_DESK_ROLE, HOUSEKEEPER_ROLE = "front_desk", "housekeeper"
STAFF_ROLE_CODES: dict[str, tuple[str, ...]] = {
    FRONT_DESK_ROLE: (
        "bookings:view",
        "bookings:edit",
        "frontdesk:view",
        "frontdesk:edit",
        "bills:view",
        "bills:edit",
        "guestid:view",
        "guestid:edit",
        "apoa:view",
        "apoa:edit",
        "endofday:view",
        "inbox:view",
        "inbox:edit",
        "calendar:view",
        "rooms:view",
        "proofs:view",
        "housekeeping:view",
        "housekeeping:edit",
    ),
    HOUSEKEEPER_ROLE: ("housekeeping:view", "housekeeping:edit"),
}
STAFF_ROLES = (MANAGER_ROLE, FRONT_DESK_ROLE, HOUSEKEEPER_ROLE)


async def ensure_staff_roles(db: AsyncSession) -> None:
    """The front desk and housekeeper roles with their codes (added, never removed)."""
    for name, codes in STAFF_ROLE_CODES.items():
        role = (await db.exec(select(Role).where(col(Role.name) == name))).first()
        if role is None:
            role = Role(
                name=name,
                description=f"Ready-made staff role: {name.replace('_', ' ')}",
                created_by="seed",
                updated_by="seed",
            )
            db.add(role)
            await db.flush()
        held = set(
            (
                await db.exec(
                    select(col(RolePermission.permission_id)).where(
                        col(RolePermission.role_id) == role.id
                    )
                )
            ).all()
        )
        wanted = (await db.exec(select(Permission).where(col(Permission.code).in_(codes)))).all()
        for permission in wanted:
            if permission.id not in held:
                db.add(RolePermission(role_id=role.id, permission_id=permission.id))
    await db.commit()


async def staff_role_of(db: AsyncSession, user_id: int) -> str:
    """The ready-made role the user holds (the widest), or `custom`."""
    names = set(
        (
            await db.exec(
                select(col(Role.name))
                .join(UserRole, col(UserRole.role_id) == col(Role.id))
                .where(col(UserRole.user_id) == user_id)
            )
        ).all()
    )
    return next((name for name in STAFF_ROLES if name in names), "custom")


async def staff_roles_of(db: AsyncSession, user_ids: list[int]) -> dict[int, str]:
    """`staff_role_of` for many users in one query."""
    if not user_ids:
        return {}
    rows = (
        await db.exec(
            select(col(UserRole.user_id), col(Role.name))
            .join(Role, col(Role.id) == col(UserRole.role_id))
            .where(col(UserRole.user_id).in_(user_ids))
        )
    ).all()
    held: dict[int, set[str]] = {user_id: set() for user_id in user_ids}
    for user_id, name in rows:
        held[user_id].add(name)
    return {
        user_id: next((name for name in STAFF_ROLES if name in names), "custom")
        for user_id, names in held.items()
    }


async def may_grant(db: AsyncSession, user_id: int, is_owner: bool, role: str) -> bool:
    """Only the owner or a manager may make someone a manager; staff:edit alone may not."""
    return role != MANAGER_ROLE or is_owner or await staff_role_of(db, user_id) == MANAGER_ROLE


async def set_staff_role(db: AsyncSession, user_id: int, name: str) -> None:
    """Give the user exactly one ready-made role (other roles they hold stay). No commit."""
    roles = (await db.exec(select(Role).where(col(Role.name).in_(STAFF_ROLES)))).all()
    by_name = {role.name: role for role in roles}
    if name not in by_name:
        raise LookupError(f"staff role {name} is missing; startup creates it")
    held = (
        await db.exec(
            select(UserRole).where(
                col(UserRole.user_id) == user_id,
                col(UserRole.role_id).in_([role.id for role in roles]),
            )
        )
    ).all()
    for grant in held:
        if grant.role_id != by_name[name].id:
            await db.delete(grant)
    if all(grant.role_id != by_name[name].id for grant in held):
        db.add(UserRole(user_id=user_id, role_id=by_name[name].id))


async def remove_all_roles(db: AsyncSession, user_id: int) -> None:
    """The user loses every role (they leave the only workspace they belong to). No commit."""
    for grant in (await db.exec(select(UserRole).where(col(UserRole.user_id) == user_id))).all():
        await db.delete(grant)
