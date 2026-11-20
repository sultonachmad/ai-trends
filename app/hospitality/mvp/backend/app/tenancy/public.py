"""Tenant scope for the public pay page — no sign-in, only a link token.

The token is checked for shape, fingerprinted, and resolved to its tenant through
`resolve_payment_link` (migration 0005), the one thing an unscoped `app_rw` session
may ask. From then on the session is tenant-scoped exactly like a staff request, so
row-level security applies to everything the pay page reads or writes.

An unknown, malformed or foreign token always gets the same 404.
"""

from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.payments.tokens import fingerprint, is_well_formed
from app.tenancy.session import APP_ROLE, bind_tenant

LINK_NOT_FOUND = "Payment link not found"
_AS_APP_ROLE = text(f"SET LOCAL ROLE {APP_ROLE}")
_RESOLVE = text("SELECT resolve_payment_link(:token_hash)")


@dataclass(frozen=True)
class PublicLinkScope:
    """A tenant-scoped session reached through a pay-link token."""

    session: AsyncSession
    tenant_id: UUID
    token_hash: str


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=LINK_NOT_FOUND)


async def get_public_link_scope(
    token: str, session: AsyncSession = Depends(get_session)
) -> PublicLinkScope:
    """FastAPI dependency for `/api/pay/{token}` routes."""
    if not is_well_formed(token):
        raise _not_found()
    token_hash = fingerprint(token)
    await session.execute(_AS_APP_ROLE)  # least privilege before touching anything
    tenant_id = (await session.execute(_RESOLVE, {"token_hash": token_hash})).scalar_one_or_none()
    if tenant_id is None:
        raise _not_found()
    await bind_tenant(session, tenant_id)
    return PublicLinkScope(session=session, tenant_id=tenant_id, token_hash=token_hash)
