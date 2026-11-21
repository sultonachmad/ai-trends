"""A signed-in test user with rbac roles, for integration tests (US #1653 FR-12, FR-12a).

rbac ships this file because tests/integration/conftest.py belongs to base-backend-fastapi.
A test in another prefab imports it after pytest.importorskip("app.rbac.dependencies"):

    from tests.integration.rbac_users import signed_in_as

    async with signed_in_as(app, codes=(FEATURES_USE,)) as user:
        ...

It adds a user and, when asked, a role holding `codes` and/or the seeded admin role, points
app.dependency_overrides[get_current_user] at that user, and on exit removes the override and
every row it added. A code that is not seeded raises LookupError instead of granting less.
"""

import uuid
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import col, delete, select

from app.auth.models import User
from app.database import async_session_factory
from app.rbac.models import Permission, Role, RolePermission, UserRole
from app.session.dependencies import get_current_user

ROW_PREFIX = "t-rbac-"


@asynccontextmanager
async def signed_in_as(
    app: FastAPI, *, codes: Iterable[str] = (), admin: bool = False
) -> AsyncIterator[User]:
    mine = f"{ROW_PREFIX}{uuid.uuid4().hex[:8]}-"
    wanted = tuple(codes)
    async with async_session_factory() as db:
        user = User(email=f"{mine}user@example.com", hashed_password="placeholder-not-a-hash")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        user_id, email = user.id, user.email  # read now: a later commit or rollback expires them
        try:
            if wanted:
                role = Role(name=f"{mine}role")
                db.add(role)
                await db.commit()
                await db.refresh(role)
                found = (
                    await db.exec(select(Permission).where(col(Permission.code).in_(wanted)))
                ).all()
                missing = set(wanted) - {p.code for p in found}
                if missing:
                    raise LookupError(f"permission codes not seeded: {sorted(missing)}")
                db.add_all([RolePermission(role_id=role.id, permission_id=p.id) for p in found])
                db.add(UserRole(user_id=user_id, role_id=role.id))
            if admin:
                admin_role = (await db.exec(select(Role).where(Role.name == "admin"))).one()
                db.add(UserRole(user_id=user_id, role_id=admin_role.id))
            await db.commit()
        except BaseException:
            await db.rollback()
            await _remove(user_id, mine)
            raise
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": str(user_id),
        "email": email,
    }
    try:
        yield user
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        await _remove(user_id, mine)


async def _remove(user_id: object, mine: str) -> None:
    async with async_session_factory() as db:
        roles = select(Role.id).where(col(Role.name).startswith(mine))
        await db.exec(delete(UserRole).where(UserRole.user_id == user_id))
        await db.exec(delete(RolePermission).where(col(RolePermission.role_id).in_(roles)))
        await db.exec(delete(Role).where(col(Role.name).startswith(mine)))
        await db.exec(delete(User).where(User.id == user_id))
        await db.commit()
