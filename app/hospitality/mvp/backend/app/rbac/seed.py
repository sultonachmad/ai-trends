"""Startup seed for RBAC data.

Idempotent — safe to call on every application startup. It upserts (never
duplicates) permission rows, the admin role, and the admin user.
All DB operations are done with explicit SELECT-before-INSERT to stay
idempotent across restarts.

Navigation menus are NOT seeded — they are read from backend/docs/rbac-spec.yaml
at runtime (see app/rbac/me.py).

Called from ``backend/app/main.py``'s ``lifespan()`` after ``create_db_and_tables()``.
Admin user is seeded only when ``RBAC_SEED_ADMIN`` is truthy (``true``/``1``),
``RBAC_ADMIN_PASSWORD`` passes ``checked_seed_value`` (non-empty, printable,
no ``$ ` " \\``, at most 72 UTF-8 bytes), and the password is non-empty;
otherwise permissions + admin role seed and no admin user is created.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

log = logging.getLogger(__name__)

_ADMIN_ROLE = "admin"
_DEFAULT_ADMIN_EMAIL = "admin@example.com"
_TRUTHY = frozenset({"true", "1"})
_UNSAFE_CHARS = frozenset('$`"\\')
_MAX_PASSWORD_BYTES = 72  # bcrypt limit; auth/security.py hash_password raises above it


def _flag_is_truthy(seed_flag: str | None) -> bool:
    """True when ``seed_flag`` is strictly truthy (``"true"``/``"1"``, case-insensitive)."""
    return bool(seed_flag) and seed_flag.strip().lower() in _TRUTHY


def should_seed_admin(seed_flag: str | None, password: str | None) -> bool:
    """Seed only when the opt-in flag is strictly truthy AND a password is set."""
    return _flag_is_truthy(seed_flag) and bool(password)


async def seed_rbac(db: AsyncSession) -> None:
    """Upsert all RBAC seed data. Safe to call repeatedly."""
    from sqlmodel import select

    from app.auth.models import User
    from app.auth.security import hash_password
    from app.rbac.dependencies import _PERMISSION_REGISTRY
    from app.rbac.models import Permission, PermissionType, Role, RolePermission, UserRole

    # ── 1. Upsert permissions from the registry ──────────────────────────────
    for code, description in _PERMISSION_REGISTRY.items():
        existing = (await db.exec(select(Permission).where(Permission.code == code))).first()
        if not existing:
            db.add(
                Permission(
                    code=code,
                    description=description,
                    type=PermissionType.api,
                    created_by="seed",
                    updated_by="seed",
                )
            )
        elif existing.description != description:
            existing.description = description
            existing.updated_by = "seed"
            db.add(existing)
    await db.commit()
    log.info("RBAC seed: permissions upserted (%d codes)", len(_PERMISSION_REGISTRY))

    # ── 2. Upsert admin role ─────────────────────────────────────────────────
    admin_role = (await db.exec(select(Role).where(Role.name == _ADMIN_ROLE))).first()
    if not admin_role:
        admin_role = Role(
            name=_ADMIN_ROLE,
            description="Full system access — all permissions granted automatically",
            created_by="seed",
            updated_by="seed",
        )
        db.add(admin_role)
        await db.commit()
        await db.refresh(admin_role)
    log.info("RBAC seed: admin role ready (id=%s)", admin_role.id)

    # ── 3. Assign all permissions to admin role ──────────────────────────────
    all_permissions = list((await db.exec(select(Permission))).all())
    for perm in all_permissions:
        existing_rp = (
            await db.exec(
                select(RolePermission).where(
                    RolePermission.role_id == admin_role.id,
                    RolePermission.permission_id == perm.id,
                )
            )
        ).first()
        if not existing_rp:
            db.add(RolePermission(role_id=admin_role.id, permission_id=perm.id))
    await db.commit()

    # ── 4-5. Admin user + role assignment — opt-in, gated together ────────────
    seed_flag = checked_seed_value("RBAC_SEED_ADMIN", os.getenv("RBAC_SEED_ADMIN"))
    admin_email = normalize_admin_email(
        checked_seed_value("RBAC_ADMIN_EMAIL", os.getenv("RBAC_ADMIN_EMAIL"))
        or _DEFAULT_ADMIN_EMAIL
    )
    admin_password = checked_seed_value(
        "RBAC_ADMIN_PASSWORD", os.getenv("RBAC_ADMIN_PASSWORD"), _MAX_PASSWORD_BYTES
    )

    raw_password = os.getenv("RBAC_ADMIN_PASSWORD", "")
    if not should_seed_admin(seed_flag, admin_password):
        if _flag_is_truthy(seed_flag) and not admin_password and not raw_password:
            log.warning(
                "RBAC seed: RBAC_SEED_ADMIN is set but RBAC_ADMIN_PASSWORD is empty; "
                "no admin user seeded"
            )
        elif _flag_is_truthy(seed_flag) and not admin_password:
            pass  # checked_seed_value already logged the rejection
        else:
            log.info(
                "RBAC seed: admin seeding disabled; set RBAC_SEED_ADMIN=true and "
                "RBAC_ADMIN_PASSWORD to seed an admin user"
            )
        log.info("RBAC seed: complete (no admin user)")
        return

    admin_user = (await db.exec(select(User).where(User.email == admin_email))).first()
    if not admin_user:
        admin_user = User(email=admin_email, hashed_password=hash_password(admin_password))
        db.add(admin_user)
        await db.commit()
        await db.refresh(admin_user)
    log.info("RBAC seed: admin user ready (id=%s)", admin_user.id)

    # ── existing step-5 UserRole assignment, unchanged in shape ──────────────
    existing_ur = (
        await db.exec(
            select(UserRole).where(
                UserRole.user_id == admin_user.id,
                UserRole.role_id == admin_role.id,
            )
        )
    ).first()
    if not existing_ur:
        db.add(UserRole(user_id=admin_user.id, role_id=admin_role.id))
        await db.commit()

    log.info("RBAC seed: complete")


def checked_seed_value(key: str, value: str | None, max_bytes: int | None = None) -> str:
    """Return ``value``, or ``""`` when it is absent, empty, or breaks Ttest's rules.

    $ ` " \\, password at most 72 UTF-8 bytes), so a value Ttest rejects is also
    treated as absent when the app reads ``backend/.env`` itself. The too-long
    check also keeps ``hash_password`` from raising and crashing startup.
    """
    if not value:
        return ""
    too_long = max_bytes is not None and len(value.encode("utf-8")) > max_bytes
    if too_long or not value.isprintable() or any(ch in _UNSAFE_CHARS for ch in value):
        log.warning("RBAC seed: %s rejected (unsafe or too long); treated as absent", key)
        return ""
    return value


def normalize_admin_email(email: str) -> str:
    """Lowercase, as login does before its lookup (credentials_router.py).

    A mixed-case ``RBAC_ADMIN_EMAIL`` stored as given could never log in.
    """
    return email.lower()
