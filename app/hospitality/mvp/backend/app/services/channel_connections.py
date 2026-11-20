"""A property's connections to sales channels: starting, testing, settings and status.

A connection moves through a small set of states:

    draft ──test passes──▶ testing ──go live──▶ live ◀──resume── paused
      │  ▲                                        └────pause────▶
      └──┴── test fails ──▶ error (test again)
    any state ──disconnect──▶ disconnected (history kept, slot freed)

The channel is always called with our own record already saved and no lock held, so a
slow or failing channel never blocks the property.
"""

import datetime as dt
import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.channels.provider import (
    ChannelCall,
    ChannelProperty,
    ChannelUnavailableError,
    UnknownChannelPropertyError,
    get_channel,
)
from app.models.tenant import Channel, ChannelConnection, ChannelMapping, Property
from app.schemas.channels import ConnectionCreateRequest, ConnectionSettingsRequest
from app.services import channel_hooks, tenant_audit
from app.services.channel_catalog import can_connect, find_catalog_entry
from app.services.channel_quota import DISCONNECTED, reserve_connection_slot
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

DRAFT, TESTING, LIVE, PAUSED, ERROR = "draft", "testing", "live", "paused", "error"
ENTITY = "channelconnection"
# Problems a test can report, as short codes the screen turns into sentences.
UNKNOWN_PROPERTY = "unknown_property"
UNAVAILABLE = "channel_unavailable"
# Keys inside `channelconnection.settings`.
COMMISSION = "commission_percent"
PRODUCTS = "products"
LAST_TESTED = "last_tested_at"
ZERO = Decimal("0")


class ChannelNotConnectableError(Exception):
    """That channel cannot be connected here (unknown, or not available yet)."""


class ChannelAlreadyConnectedError(Exception):
    """The property already has a connection to that channel."""


class ConnectionNotFoundError(Exception):
    """No such connection on the caller's property."""


class WrongConnectionStateError(Exception):
    """The connection is not in a state that allows this."""

    def __init__(self, status: str) -> None:
        super().__init__(f"not possible while the connection is {status}")
        self.status = status


class NothingMatchedError(Exception):
    """Going live needs at least one room and rate matched."""


async def lock_property(session: AsyncSession, context: TenantContext, property_id: UUID) -> None:
    await session.exec(
        select(col(Property.id))
        .where(col(Property.tenant_id) == context.tenant_id, col(Property.id) == property_id)
        .with_for_update()
    )


async def get_connection(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    connection_id: UUID,
    *,
    lock: bool = False,
) -> ChannelConnection:
    statement = select(ChannelConnection).where(
        col(ChannelConnection.tenant_id) == context.tenant_id,
        col(ChannelConnection.property_id) == property_id,
        col(ChannelConnection.id) == connection_id,
    )
    if lock:
        # A locked re-read must see what other transactions committed meanwhile, not the
        # attributes this session already has in its identity map.
        statement = statement.with_for_update().execution_options(populate_existing=True)
    connection = (await session.exec(statement)).first()
    if connection is None:
        raise ConnectionNotFoundError
    return connection


async def channel_of(
    session: AsyncSession, context: TenantContext, connection: ChannelConnection
) -> Channel:
    return (
        await session.exec(
            select(Channel).where(
                col(Channel.tenant_id) == context.tenant_id,
                col(Channel.id) == connection.channel_id,
            )
        )
    ).one()


async def list_connections(
    session: AsyncSession, context: TenantContext, property_id: UUID
) -> list[ChannelConnection]:
    """Connections in use first (oldest first), then disconnected ones."""
    rows = await session.exec(
        select(ChannelConnection)
        .where(
            col(ChannelConnection.tenant_id) == context.tenant_id,
            col(ChannelConnection.property_id) == property_id,
        )
        .order_by(
            (col(ChannelConnection.status) == DISCONNECTED).asc(),
            col(ChannelConnection.created_at),
        )
    )
    return list(rows.all())


async def _channel_row(session: AsyncSession, context: TenantContext, code: str) -> Channel:
    """The tenant's row for a catalogue channel, created on first use."""
    existing = (
        await session.exec(
            select(Channel).where(
                col(Channel.tenant_id) == context.tenant_id, col(Channel.code) == code
            )
        )
    ).first()
    if existing is not None:
        return existing
    entry = await find_catalog_entry(session, code)
    if entry is None:
        raise ChannelNotConnectableError
    channel = Channel(
        tenant_id=context.tenant_id,
        code=entry.code,
        name=entry.name,
        kind=entry.kind,
        commission_pct=entry.default_commission_pct,
        is_direct=False,
    )
    session.add(channel)
    await session.flush()
    return channel


async def _connections_to(
    session: AsyncSession, context: TenantContext, property_id: UUID, channel_id: UUID
) -> list[ChannelConnection]:
    rows = await session.exec(
        select(ChannelConnection).where(
            col(ChannelConnection.tenant_id) == context.tenant_id,
            col(ChannelConnection.property_id) == property_id,
            col(ChannelConnection.channel_id) == channel_id,
        )
    )
    return list(rows.all())


async def create_connection(
    session: AsyncSession, context: TenantContext, prop: Property, request: ConnectionCreateRequest
) -> ChannelConnection:
    """Start a connection as a draft and take a slot of the plan's limit. Commits."""
    if not can_connect(request.channel_code):
        raise ChannelNotConnectableError
    property_id, currency = prop.id, prop.currency
    await lock_property(session, context, property_id)
    channel = await _channel_row(session, context, request.channel_code)
    earlier = await _connections_to(session, context, property_id, channel.id)
    if any(connection.status != DISCONNECTED for connection in earlier):
        raise ChannelAlreadyConnectedError
    await reserve_connection_slot(session, context, property_id)
    # Coming back to the same listing continues the old record and its history.
    connection = next(
        (c for c in earlier if c.external_property_id == request.external_property_id), None
    )
    if connection is None:
        connection = ChannelConnection(
            tenant_id=context.tenant_id,
            property_id=property_id,
            channel_id=channel.id,
            external_property_id=request.external_property_id,
            connection_via="direct_api",
            currency=currency,
            created_by=str(context.user_id),
        )
    else:
        await session.exec(
            delete(ChannelMapping).where(
                col(ChannelMapping.tenant_id) == context.tenant_id,
                col(ChannelMapping.channel_connection_id) == connection.id,
            )
        )
    connection.status = DRAFT
    connection.error_message = None
    connection.settings = {COMMISSION: str(channel.commission_pct or ZERO)}
    session.add(connection)
    await session.flush()
    await tenant_audit.record(
        session,
        context,
        "channel.connection.started",
        property_id=property_id,
        entity_table=ENTITY,
        entity_id=connection.id,
        payload={"channel": channel.code, "channel_property_id": request.external_property_id},
    )
    await session.commit()
    await session.refresh(connection)
    log.info("Channel connection started connection=%s channel=%s", connection.id, channel.code)
    return connection


def products_snapshot(found: ChannelProperty) -> dict[str, object]:
    """The channel's rooms and rates as we keep them between fetches."""
    return {
        "property_name": found.name,
        "rooms": [
            {
                "id": room.id,
                "name": room.name,
                "max_guests": room.max_guests,
                "rates": [{"id": rate.id, "name": rate.name} for rate in room.rates],
            }
            for room in found.rooms
        ],
    }


async def fetch_from_channel(
    session: AsyncSession, context: TenantContext, connection: ChannelConnection, code: str
) -> ChannelProperty:
    """Ask the channel for the property. No transaction is open while it answers."""
    await session.commit()  # release anything read so far before waiting on the channel
    call = ChannelCall(tenant_id=context.tenant_id, session=session)
    found = await get_channel(code).fetch_property(call, connection.external_property_id or "")
    await session.commit()  # the simulator read through our session: close that too
    return found


async def test_connection(
    session: AsyncSession, context: TenantContext, property_id: UUID, connection_id: UUID
) -> ChannelConnection:
    """Check the property ID with the channel and remember its rooms and rates. Commits.

    A connection in use (live or paused) keeps its status whatever the answer; only the
    problem is noted, so a channel hiccup never takes a property off sale.
    """
    connection = await get_connection(session, context, property_id, connection_id)
    if connection.status == DISCONNECTED:
        raise WrongConnectionStateError(connection.status)
    code = (await channel_of(session, context, connection)).code
    problem, found = None, None
    try:
        found = await fetch_from_channel(session, context, connection, code)
    except UnknownChannelPropertyError:
        problem = UNKNOWN_PROPERTY
    except ChannelUnavailableError:
        problem = UNAVAILABLE
    # The property lock serialises this against every other writer (and the audit entry
    # below); the locked re-read then sees what they may have committed meanwhile.
    await lock_property(session, context, property_id)
    connection = await get_connection(session, context, property_id, connection_id, lock=True)
    if connection.status == DISCONNECTED:  # disconnected while the channel was answering
        raise WrongConnectionStateError(connection.status)
    setup = connection.status in (DRAFT, TESTING, ERROR)
    tested_at = dt.datetime.now(dt.UTC).isoformat()
    if found is not None:
        connection.settings = {
            **connection.settings,
            PRODUCTS: products_snapshot(found),
            LAST_TESTED: tested_at,
        }
        connection.status = TESTING if setup else connection.status
    else:
        connection.settings = {**connection.settings, LAST_TESTED: tested_at}
        # "The channel did not answer" says nothing about the ID: a draft stays a draft.
        if setup and problem == UNKNOWN_PROPERTY:
            connection.status = ERROR
    connection.error_message = problem
    session.add(connection)
    await tenant_audit.record(
        session,
        context,
        "channel.connection.tested",
        property_id=property_id,
        entity_table=ENTITY,
        entity_id=connection.id,
        payload={"result": problem or "ok"},
    )
    await session.commit()
    await session.refresh(connection)
    return connection


async def update_settings(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    connection_id: UUID,
    request: ConnectionSettingsRequest,
) -> ChannelConnection:
    """Change commission, price adjustment or who collects payment. Commits."""
    await lock_property(session, context, property_id)
    connection = await get_connection(session, context, property_id, connection_id, lock=True)
    if connection.status == DISCONNECTED:
        raise WrongConnectionStateError(connection.status)
    changes = request.model_dump(exclude_unset=True, exclude_none=True)
    if "commission_percent" in changes:
        connection.settings = {
            **connection.settings,
            COMMISSION: str(changes["commission_percent"]),
        }
    if "price_adjustment_percent" in changes:
        connection.rate_markup_pct = changes["price_adjustment_percent"]
    if "payment_collect" in changes:
        connection.payment_collect_model = changes["payment_collect"]
    connection.updated_by = str(context.user_id)
    session.add(connection)
    if changes:
        await tenant_audit.record(
            session,
            context,
            "channel.connection.settings_changed",
            property_id=property_id,
            entity_table=ENTITY,
            entity_id=connection.id,
            payload={key: str(value) for key, value in changes.items()},
        )
    await session.commit()
    await session.refresh(connection)
    return connection


async def _mapped_count(session: AsyncSession, context: TenantContext, connection_id: UUID) -> int:
    """The go-live gate. Same rows as the `mapped_pairs` the screen shows."""
    rows = await session.exec(
        select(col(ChannelMapping.id)).where(
            col(ChannelMapping.tenant_id) == context.tenant_id,
            col(ChannelMapping.channel_connection_id) == connection_id,
            col(ChannelMapping.rate_plan_id).is_not(None),
            col(ChannelMapping.external_rate_id).is_not(None),
        )
    )
    return len(rows.all())


# move -> (states it is allowed from, state it leads to, event recorded)
_MOVES: dict[str, tuple[tuple[str, ...], str, str]] = {
    "go_live": ((TESTING,), LIVE, "channel.connection.went_live"),
    "pause": ((LIVE,), PAUSED, "channel.connection.paused"),
    "resume": ((PAUSED,), LIVE, "channel.connection.resumed"),
    "disconnect": (
        (DRAFT, TESTING, LIVE, PAUSED, ERROR),
        DISCONNECTED,
        "channel.connection.disconnected",
    ),
}
_HOOKS = {
    "go_live": channel_hooks.on_go_live,
    "pause": channel_hooks.on_pause,
    "resume": channel_hooks.on_resume,
}


async def move(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    connection_id: UUID,
    action: str,
) -> ChannelConnection:
    """Go live, pause, resume or disconnect. Commits."""
    allowed_from, target, event = _MOVES[action]
    await lock_property(session, context, property_id)
    connection = await get_connection(session, context, property_id, connection_id, lock=True)
    if connection.status not in allowed_from:
        raise WrongConnectionStateError(connection.status)
    if action == "go_live" and await _mapped_count(session, context, connection.id) == 0:
        raise NothingMatchedError
    connection.status = target
    connection.updated_by = str(context.user_id)
    session.add(connection)
    await tenant_audit.record(
        session,
        context,
        event,
        property_id=property_id,
        entity_table=ENTITY,
        entity_id=connection.id,
    )
    hook = _HOOKS.get(action)
    if hook is not None:
        await hook(session, context, connection)
    await session.commit()
    await session.refresh(connection)
    log.info("Channel connection %s connection=%s", action, connection.id)
    return connection
