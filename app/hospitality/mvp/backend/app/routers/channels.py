"""Sales channel routes.

GET   /api/channels                              catalogue and usage against the plan
GET   /api/channel-connections
POST  /api/channel-connections                   start a connection (draft)
GET   /api/channel-connections/{id}
PATCH /api/channel-connections/{id}              commission, price adjustment, who collects
POST  /api/channel-connections/{id}/test         check the property ID with the channel
POST  /api/channel-connections/{id}/go-live | /pause | /resume | /disconnect
GET   /api/channel-connections/{id}/products     the channel's rooms and rates, fetched now
PUT   /api/channel-connections/{id}/mappings     the whole matching
"""

from collections.abc import Awaitable, Callable
from typing import Literal, TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.channels.provider import ChannelUnavailableError, UnknownChannelPropertyError
from app.rbac.dependencies import require_permission
from app.schemas.channels import (
    ChannelProductsRead,
    ChannelsOverview,
    ConnectionCreateRequest,
    ConnectionDetail,
    ConnectionRead,
    ConnectionSettingsRequest,
    MappingsRequest,
)
from app.services import channel_catalog
from app.services import channel_connections as connections
from app.services import channel_mappings as mappings
from app.services.channel_quota import ChannelLimitReachedError
from app.services.workspace import find_property
from app.tenancy.context import TenantContext, get_tenant_context
from app.tenancy.session import get_tenant_session

VIEW = require_permission("channels:view", "See connected sales channels")

EDIT = require_permission("channels:edit", "Connect and manage sales channels")

channels_router = APIRouter(prefix="/api/channels", tags=["channels"])
connections_router = APIRouter(prefix="/api/channel-connections", tags=["channels"])

T = TypeVar("T")
Move = Literal["go-live", "pause", "resume", "disconnect"]
UNPROCESSABLE = status.HTTP_422_UNPROCESSABLE_ENTITY
CONFLICT = status.HTTP_409_CONFLICT

_MESSAGES: dict[type[Exception], tuple[int, str]] = {
    connections.ConnectionNotFoundError: (status.HTTP_404_NOT_FOUND, "Connection not found"),
    connections.ChannelNotConnectableError: (
        UNPROCESSABLE,
        "This channel cannot be connected yet.",
    ),
    connections.ChannelAlreadyConnectedError: (
        CONFLICT,
        "This property is already connected to that channel.",
    ),
    connections.NothingMatchedError: (
        CONFLICT,
        "Match at least one room and rate before going live.",
    ),
    mappings.UnknownOwnProductError: (
        UNPROCESSABLE,
        "A room type or rate plan in the matching is not in use, or the plan does not sell it.",
    ),
    mappings.UnknownChannelProductError: (
        UNPROCESSABLE,
        "A channel room or rate in the matching is not on the channel's list. Refresh it.",
    ),
    UnknownChannelPropertyError: (
        CONFLICT,
        "The channel no longer shows a property with that ID.",
    ),
    ChannelUnavailableError: (
        status.HTTP_502_BAD_GATEWAY,
        "The channel did not answer. Try again in a moment.",
    ),
}


def _limit_message(exc: ChannelLimitReachedError) -> str:
    if exc.quota.limit == 0:
        return "Channel connections are not part of your plan."
    noun = "channel" if exc.quota.limit == 1 else "channels"
    return f"Your plan allows {exc.quota.limit} connected {noun}. Disconnect one to add another."


async def _guarded(call: Callable[[], Awaitable[T]]) -> T:
    """Run a channel service call, turning its domain errors into HTTP answers."""
    try:
        return await call()
    except ChannelLimitReachedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=_limit_message(exc)
        ) from None
    except connections.WrongConnectionStateError as exc:
        raise HTTPException(
            status_code=CONFLICT, detail=f"Not possible while the connection is {exc.status}."
        ) from None
    except tuple(_MESSAGES) as exc:
        code, detail = _MESSAGES[type(exc)]
        raise HTTPException(status_code=code, detail=detail) from None


@channels_router.get("", response_model=ChannelsOverview)
async def channels_overview(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
) -> ChannelsOverview:
    prop = await find_property(session, context)
    return await channel_catalog.overview(session, context, prop.id)


@connections_router.get("", response_model=list[ConnectionRead])
async def list_connections(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
) -> list[ConnectionRead]:
    prop = await find_property(session, context)
    found = await connections.list_connections(session, context, prop.id)
    return await mappings.read_many(session, context, found)


@connections_router.post("", response_model=ConnectionDetail, status_code=status.HTTP_201_CREATED)
async def create_connection(
    body: ConnectionCreateRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> ConnectionDetail:
    prop = await find_property(session, context)
    connection = await _guarded(lambda: connections.create_connection(session, context, prop, body))
    return await mappings.read_detail(session, context, prop, connection)


@connections_router.get("/{connection_id}", response_model=ConnectionDetail)
async def read_connection(
    connection_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
) -> ConnectionDetail:
    prop = await find_property(session, context)
    connection = await _guarded(
        lambda: connections.get_connection(session, context, prop.id, connection_id)
    )
    return await mappings.read_detail(session, context, prop, connection)


@connections_router.patch("/{connection_id}", response_model=ConnectionDetail)
async def update_connection(
    connection_id: UUID,
    body: ConnectionSettingsRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> ConnectionDetail:
    prop = await find_property(session, context)
    connection = await _guarded(
        lambda: connections.update_settings(session, context, prop.id, connection_id, body)
    )
    return await mappings.read_detail(session, context, prop, connection)


@connections_router.post("/{connection_id}/test", response_model=ConnectionDetail)
async def test_connection(
    connection_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> ConnectionDetail:
    prop = await find_property(session, context)
    connection = await _guarded(
        lambda: connections.test_connection(session, context, prop.id, connection_id)
    )
    return await mappings.read_detail(session, context, prop, connection)


@connections_router.get("/{connection_id}/products", response_model=ChannelProductsRead)
async def channel_products(
    connection_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
) -> ChannelProductsRead:
    prop = await find_property(session, context)
    return await _guarded(
        lambda: mappings.refresh_products(session, context, prop.id, connection_id)
    )


@connections_router.put("/{connection_id}/mappings", response_model=ConnectionDetail)
async def save_mappings(
    connection_id: UUID,
    body: MappingsRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> ConnectionDetail:
    prop = await find_property(session, context)
    connection = await _guarded(
        lambda: mappings.save_mappings(session, context, prop.id, connection_id, body)
    )
    return await mappings.read_detail(session, context, prop, connection)


@connections_router.post("/{connection_id}/{action}", response_model=ConnectionDetail)
async def move_connection(
    connection_id: UUID,
    action: Move,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> ConnectionDetail:
    prop = await find_property(session, context)
    connection = await _guarded(
        lambda: connections.move(session, context, prop.id, connection_id, action.replace("-", "_"))
    )
    return await mappings.read_detail(session, context, prop, connection)
