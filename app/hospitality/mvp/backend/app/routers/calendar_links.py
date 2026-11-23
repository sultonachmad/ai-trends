"""Calendar links (iCal).

GET    /api/calendar-links
POST   /api/calendar-links                 returns the private link, once
PATCH  /api/calendar-links/{id}            rename; set or stop the import
POST   /api/calendar-links/{id}/token      a new private link; the old one stops working
POST   /api/calendar-links/{id}/sync       read the site's calendar now
DELETE /api/calendar-links/{id}            remove it and give back what it blocked
GET    /api/ical/{token}.ics               public; the token is the credential
"""

import logging
import re
from collections.abc import Awaitable, Callable
from typing import TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.channels.ical_fetch import IcalFetchError
from app.database import get_session
from app.payments.tokens import fingerprint, is_well_formed
from app.routers.channels import EDIT, VIEW
from app.schemas.calendar_links import (
    CalendarLinkCreated,
    CalendarLinkCreateRequest,
    CalendarLinkRead,
    CalendarLinkUpdateRequest,
)
from app.services import calendar_link_sync as sync
from app.services import calendar_links as links
from app.services.channel_push import _context as worker_context
from app.services.workspace import find_property
from app.tenancy.context import TenantContext, get_tenant_context
from app.tenancy.session import APP_ROLE, bind_tenant, get_tenant_session

__all__ = ["calendar_links_router", "ical_router"]


class _RedactCalendarTokens(logging.Filter):
    """The private token is in the path of `/api/ical/...`: keep it out of access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            record.args = (*args[:2], _TOKEN_IN_PATH.sub(r"\1***.ics", args[2]), *args[3:])
        return True


_TOKEN_IN_PATH = re.compile(r"(/api/ical/)[^/?\s]+\.ics")
logging.getLogger("uvicorn.access").addFilter(_RedactCalendarTokens())

calendar_links_router = APIRouter(prefix="/api/calendar-links", tags=["calendar links"])
ical_router = APIRouter(prefix="/api/ical", tags=["calendar links"])

T = TypeVar("T")
NOT_FOUND = "Calendar link not found"
log = logging.getLogger(__name__)
_AS_APP_ROLE = text(f"SET LOCAL ROLE {APP_ROLE}")
_RESOLVE = text("SELECT resolve_ical_feed(:token_hash)")
_URL_ERRORS = {
    "invalid_url": "Paste the full https:// calendar link from the site.",
    "unsafe_address": "That address cannot be used as a calendar link.",
}


async def _guarded(call: Callable[[], Awaitable[T]]) -> T:
    try:
        return await call()
    except links.CalendarLinkNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND) from None
    except links.UnknownRoomTypeError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "That room type is not in use."
        ) from None
    except links.TooManyLinksError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This property has reached its number of calendar links."
        ) from None
    except IcalFetchError as exc:
        detail = _URL_ERRORS.get(exc.code, _URL_ERRORS["invalid_url"])
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail) from None


@calendar_links_router.get("", response_model=list[CalendarLinkRead])
async def list_links(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view: dict = VIEW,
) -> list[CalendarLinkRead]:
    prop = await find_property(session, context)
    return await links.read_links(session, context, prop)


async def _read_site(
    session: AsyncSession, context: TenantContext, link_id: UUID, property_id: UUID
) -> None:
    feeds = await links.find_link(session, context, property_id, link_id)
    if feeds.imported is not None:
        await sync.sync_feed(session, context, feeds.imported.id)


async def _read_after_sync(
    session: AsyncSession, context: TenantContext, link_id: UUID
) -> CalendarLinkRead:
    """The link as it now stands (it may have been removed while the site was read)."""
    prop = await find_property(session, context)
    return await _guarded(lambda: links.read_link(session, context, prop, link_id))


@calendar_links_router.post(
    "", response_model=CalendarLinkCreated, status_code=status.HTTP_201_CREATED
)
async def create_link(
    body: CalendarLinkCreateRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit: dict = EDIT,
) -> CalendarLinkCreated:
    prop = await find_property(session, context)
    created = await _guarded(lambda: links.create_link(session, context, prop, body))
    try:  # the private link is shown only now: a failed first read must not lose it
        await _read_site(session, context, created.id, prop.id)
        read = await _read_after_sync(session, context, created.id)
    except Exception as exc:  # noqa: BLE001
        log.error("First calendar read failed link=%s type=%s", created.id, type(exc).__name__)
        await session.rollback()
        return created
    return CalendarLinkCreated(**read.model_dump(), export_path=created.export_path)


@calendar_links_router.patch("/{link_id}", response_model=CalendarLinkRead)
async def update_link(
    link_id: UUID,
    body: CalendarLinkUpdateRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit: dict = EDIT,
) -> CalendarLinkRead:
    prop = await find_property(session, context)
    await _guarded(lambda: links.update_link(session, context, prop, link_id, body))
    if body.import_url:
        await _guarded(lambda: _read_site(session, context, link_id, prop.id))
    return await _read_after_sync(session, context, link_id)


@calendar_links_router.post("/{link_id}/token", response_model=CalendarLinkCreated)
async def replace_token(
    link_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit: dict = EDIT,
) -> CalendarLinkCreated:
    prop = await find_property(session, context)
    return await _guarded(lambda: links.replace_token(session, context, prop, link_id))


@calendar_links_router.post("/{link_id}/sync", response_model=CalendarLinkRead)
async def sync_now(
    link_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit: dict = EDIT,
) -> CalendarLinkRead:
    prop = await find_property(session, context)
    await _guarded(lambda: _read_site(session, context, link_id, prop.id))
    return await _read_after_sync(session, context, link_id)


@calendar_links_router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_link(
    link_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit: dict = EDIT,
) -> None:
    prop = await find_property(session, context)
    await _guarded(lambda: links.remove_link(session, context, prop, link_id))


@ical_router.get("/{token}.ics")
async def public_calendar(token: str, session: AsyncSession = Depends(get_session)) -> Response:
    """The busy dates of one room type. An unknown or malformed token is always a 404."""
    if not is_well_formed(token):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    token_hash = fingerprint(token)
    await session.execute(_AS_APP_ROLE)
    tenant_id = (await session.execute(_RESOLVE, {"token_hash": token_hash})).scalar_one_or_none()
    if tenant_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    await bind_tenant(session, tenant_id)
    context = worker_context(tenant_id, session)
    body = await _guarded(lambda: links.export_calendar(session, context, token_hash))
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )
