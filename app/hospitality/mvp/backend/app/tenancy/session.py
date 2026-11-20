"""Database session limited to one tenant.

The API may connect as a role that bypasses row-level security (the dev database
uses the ``postgres`` superuser). A tenant-scoped session therefore does two things
at the start of **every** transaction:

    SET LOCAL ROLE app_rw            -- not an owner, no BYPASSRLS → policies apply
    set_config('app.tenant_id', …)   -- the tenant the policies compare against

Both are transaction-local, so they vanish on commit/rollback and a pooled
connection never carries one tenant's scope into another request. `bind_tenant`
re-applies them on each new transaction through an ``after_begin`` hook.

Use `get_tenant_session` for anything that reads or writes tenant tables. The plain
`get_session` is for control-plane work (sign-in, provisioning) only.
"""

from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import Depends
from sqlalchemy import event, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.tenancy.context import TenantContext, get_tenant_context

APP_ROLE = "app_rw"  # created by migration 0004
_SET_ROLE = text(f"SET LOCAL ROLE {APP_ROLE}")
_SET_TENANT = text("SELECT set_config('app.tenant_id', :tenant_id, true)")


def _apply_scope(connection: Connection, tenant_id: UUID) -> None:
    connection.execute(_SET_ROLE)
    connection.execute(_SET_TENANT, {"tenant_id": str(tenant_id)})


async def bind_tenant(session: AsyncSession, tenant_id: UUID) -> None:
    """Scope `session` to `tenant_id` for the rest of its life."""

    def _after_begin(_session: Session, _transaction: object, connection: Connection) -> None:
        _apply_scope(connection, tenant_id)

    event.listen(session.sync_session, "after_begin", _after_begin)
    if session.in_transaction():
        # A transaction is already open (e.g. the membership lookup): scope it too.
        connection = await session.connection()
        await connection.run_sync(_apply_scope, tenant_id)


async def get_tenant_session(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_session),
) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: the request's session, scoped to the caller's tenant."""
    await bind_tenant(session, context.tenant_id)
    yield session
