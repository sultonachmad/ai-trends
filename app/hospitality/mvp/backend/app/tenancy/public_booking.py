"""Tenant scope for the public booking pages: no sign-in.

A published page name or a guest token is resolved to its tenant through a narrow
`SECURITY DEFINER` function (migration 0013). From then on the session is tenant-scoped
like a staff request. Anything unknown, unpublished or malformed gets the same 404.
"""

import re
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import text
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models.tenant import BookingPage, GuestBookingLink, Property, Reservation
from app.payments.tokens import fingerprint, is_well_formed
from app.services.channel_push import _context as worker_context
from app.tenancy.context import TenantContext
from app.tenancy.session import APP_ROLE, bind_tenant

NOT_FOUND = "not_found"
SLUG_SHAPE = re.compile(r"[a-z0-9][a-z0-9-]{1,38}[a-z0-9]")
_AS_APP_ROLE = text(f"SET LOCAL ROLE {APP_ROLE}")
_RESOLVE_PAGE = text("SELECT resolve_booking_page(:value)")
_RESOLVE_GUEST = text("SELECT resolve_guest_booking(:value)")


@dataclass(frozen=True)
class PublicBookingScope:
    session: AsyncSession
    context: TenantContext
    prop: Property


@dataclass(frozen=True)
class GuestBookingScope:
    session: AsyncSession
    context: TenantContext
    prop_id: UUID
    link: GuestBookingLink


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)


async def _bind(session: AsyncSession, resolver: text, value: str) -> TenantContext:
    await session.execute(_AS_APP_ROLE)  # least privilege before touching anything
    tenant_id = (await session.execute(resolver, {"value": value})).scalar_one_or_none()
    if tenant_id is None:
        raise _not_found()
    await bind_tenant(session, tenant_id)
    return worker_context(tenant_id, session)


async def get_booking_page_scope(
    slug: str, session: AsyncSession = Depends(get_session)
) -> PublicBookingScope:
    if SLUG_SHAPE.fullmatch(slug) is None:
        raise _not_found()
    context = await _bind(session, _RESOLVE_PAGE, slug)
    row = (
        await session.exec(
            select(Property)
            .join(
                BookingPage,
                (col(BookingPage.tenant_id) == col(Property.tenant_id))
                & (col(BookingPage.property_id) == col(Property.id)),
            )
            .where(
                col(BookingPage.tenant_id) == context.tenant_id,
                col(BookingPage.slug) == slug,
                col(BookingPage.is_published).is_(True),
            )
        )
    ).first()
    if row is None:
        raise _not_found()
    return PublicBookingScope(session=session, context=context, prop=row)


async def get_guest_booking_scope(
    token: str, session: AsyncSession = Depends(get_session)
) -> GuestBookingScope:
    if not is_well_formed(token):
        raise _not_found()
    token_hash = fingerprint(token)
    context = await _bind(session, _RESOLVE_GUEST, token_hash)
    link = (
        await session.exec(
            select(GuestBookingLink).where(
                col(GuestBookingLink.tenant_id) == context.tenant_id,
                col(GuestBookingLink.token_hash) == token_hash,
            )
        )
    ).first()
    if link is None:
        raise _not_found()
    prop_id = (
        await session.exec(
            select(col(Reservation.property_id)).where(
                col(Reservation.tenant_id) == context.tenant_id,
                col(Reservation.id) == link.reservation_id,
            )
        )
    ).one()
    return GuestBookingScope(session=session, context=context, prop_id=prop_id, link=link)
