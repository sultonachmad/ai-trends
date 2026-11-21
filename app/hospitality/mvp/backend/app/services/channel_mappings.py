"""Matching our rooms and rate plans to a channel's rooms and rates, and reading a connection.

The channel's rooms and rates are fetched from the channel and kept on the connection
as a snapshot, so the screen can show names without calling the channel every time.
"""

import datetime as dt
import logging
import uuid
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, insert
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import ChannelConnection, ChannelMapping, ChannelMessage, Property
from app.schemas.channels import (
    ChannelProductsRead,
    ConnectionDetail,
    ConnectionHealth,
    ConnectionRead,
    HistoryEntry,
    MappingHealth,
    MappingPair,
    MappingsRequest,
    MessageLogEntry,
)
from app.services import tenant_audit
from app.services.channel_connections import (
    COMMISSION,
    ENTITY,
    LAST_TESTED,
    LIVE,
    PAUSED,
    PRODUCTS,
    TESTING,
    WrongConnectionStateError,
    channel_of,
    fetch_from_channel,
    get_connection,
    lock_property,
    products_snapshot,
)
from app.services.rate_plans import find_base_prices, find_rate_plans
from app.services.room_types import find_room_types
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

HISTORY_LIMIT = 50
TWO_PLACES = Decimal("0.01")
MATCHABLE = (TESTING, LIVE, PAUSED)


class UnknownOwnProductError(Exception):
    """A pair names a room type or rate plan that is not in use, or a plan that does not sell it."""


class UnknownChannelProductError(Exception):
    """A pair names a channel room or rate the channel does not list."""


async def refresh_products(
    session: AsyncSession, context: TenantContext, property_id: UUID, connection_id: UUID
) -> ChannelProductsRead:
    """Fetch the channel's rooms and rates now and remember them. Commits."""
    connection = await get_connection(session, context, property_id, connection_id)
    if connection.status not in MATCHABLE:
        raise WrongConnectionStateError(connection.status)
    code = (await channel_of(session, context, connection)).code
    found = await fetch_from_channel(session, context, connection, code)
    await lock_property(session, context, property_id)
    connection = await get_connection(session, context, property_id, connection_id, lock=True)
    if connection.status == "disconnected":  # disconnected while the channel was answering
        raise WrongConnectionStateError(connection.status)
    connection.settings = {**connection.settings, PRODUCTS: products_snapshot(found)}
    session.add(connection)
    await tenant_audit.record(
        session,
        context,
        "channel.connection.products_refreshed",
        property_id=property_id,
        entity_table=ENTITY,
        entity_id=connection.id,
    )
    await session.commit()
    return ChannelProductsRead.model_validate(connection.settings[PRODUCTS])


def _channel_pairs(products: dict[str, object] | None) -> dict[tuple[str, str], int]:
    """(channel room id, channel rate id) -> guests the room fits."""
    rooms = (products or {}).get("rooms", [])
    return {
        (str(room["id"]), str(rate["id"])): int(room["max_guests"])
        for room in rooms  # type: ignore[union-attr]
        for rate in room.get("rates", [])
    }


async def _own_pairs(
    session: AsyncSession, context: TenantContext, property_id: UUID
) -> dict[tuple[UUID, UUID], int]:
    """(room type id, rate plan id) -> guests the room fits, for everything on sale."""
    rooms = {
        room.id: room
        for room in await find_room_types(session, context, property_id, active_only=True)
    }
    plans = await find_rate_plans(session, context, property_id, active_only=True)
    links = await find_base_prices(session, context, [plan.id for plan in plans])
    return {
        (link.unit_type_id, link.rate_plan_id): rooms[link.unit_type_id].max_occupancy
        for link in links
        if link.unit_type_id in rooms
    }


async def save_mappings(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    connection_id: UUID,
    request: MappingsRequest,
) -> ChannelConnection:
    """Replace the whole matching of a connection. All or nothing. Commits."""
    await lock_property(session, context, property_id)
    connection = await get_connection(session, context, property_id, connection_id, lock=True)
    if connection.status not in MATCHABLE:
        raise WrongConnectionStateError(connection.status)
    ours = await _own_pairs(session, context, property_id)
    theirs = _channel_pairs(connection.settings.get(PRODUCTS))
    for pair in request.mappings:
        if (pair.room_type_id, pair.rate_plan_id) not in ours:
            raise UnknownOwnProductError
        if (pair.external_room_id, pair.external_rate_id) not in theirs:
            raise UnknownChannelProductError
    await session.exec(
        delete(ChannelMapping).where(
            col(ChannelMapping.tenant_id) == context.tenant_id,
            col(ChannelMapping.channel_connection_id) == connection.id,
        )
    )
    if request.mappings:
        await session.exec(
            insert(ChannelMapping),
            params=[
                {
                    "id": uuid.uuid4(),
                    "tenant_id": context.tenant_id,
                    "channel_connection_id": connection.id,
                    "unit_type_id": pair.room_type_id,
                    "rate_plan_id": pair.rate_plan_id,
                    "external_room_id": pair.external_room_id,
                    "external_rate_id": pair.external_rate_id,
                    "created_by": str(context.user_id),
                }
                for pair in request.mappings
            ],
        )
    if request.mappings:
        from app.services.calendar_dates import property_today
        from app.services.channel_queue import enqueue as enqueue_channels
        from app.services.channel_queue import horizon as channel_horizon

        prop = (
            await session.exec(
                select(Property).where(
                    col(Property.tenant_id) == context.tenant_id,
                    col(Property.id) == property_id,
                )
            )
        ).one()
        await enqueue_channels(
            session,
            context,
            property_id,
            list({pair.room_type_id for pair in request.mappings}),
            channel_horizon(property_today(prop.timezone), 366),
        )
    await tenant_audit.record(
        session,
        context,
        "channel.connection.matching_changed",
        property_id=property_id,
        entity_table=ENTITY,
        entity_id=connection.id,
        payload={"matched_pairs": len(request.mappings)},
    )
    await session.commit()
    log.info("Channel matching saved connection=%s pairs=%s", connection.id, len(request.mappings))
    return connection


# ---- reading ----------------------------------------------------------------------------


async def _mappings(
    session: AsyncSession, context: TenantContext, connection_ids: list[UUID]
) -> dict[UUID, list[MappingPair]]:
    grouped: dict[UUID, list[MappingPair]] = {connection_id: [] for connection_id in connection_ids}
    if not connection_ids:
        return grouped
    rows = await session.exec(
        select(ChannelMapping)
        .where(
            col(ChannelMapping.tenant_id) == context.tenant_id,
            col(ChannelMapping.channel_connection_id).in_(connection_ids),
            col(ChannelMapping.rate_plan_id).is_not(None),
            col(ChannelMapping.external_rate_id).is_not(None),
        )
        .order_by(col(ChannelMapping.created_at), col(ChannelMapping.id))
    )
    for row in rows.all():
        grouped[row.channel_connection_id].append(
            MappingPair(
                room_type_id=row.unit_type_id,
                rate_plan_id=row.rate_plan_id,
                external_room_id=row.external_room_id,
                external_rate_id=row.external_rate_id,
            )
        )
    return grouped


def _tested_at(connection: ChannelConnection) -> dt.datetime | None:
    stamp = connection.settings.get(LAST_TESTED)
    return dt.datetime.fromisoformat(stamp) if isinstance(stamp, str) else None


async def read_many(
    session: AsyncSession, context: TenantContext, connections: list[ChannelConnection]
) -> list[ConnectionRead]:
    pairs = await _mappings(session, context, [connection.id for connection in connections])
    result = []
    for connection in connections:
        channel = await channel_of(session, context, connection)
        products = connection.settings.get(PRODUCTS) or {}
        result.append(
            ConnectionRead(
                id=connection.id,
                channel_code=channel.code,
                channel_name=channel.name,
                external_property_id=connection.external_property_id or "",
                channel_property_name=products.get("property_name"),
                status=connection.status,
                problem=connection.error_message,
                commission_percent=Decimal(str(connection.settings.get(COMMISSION, "0"))).quantize(
                    TWO_PLACES
                ),
                price_adjustment_percent=connection.rate_markup_pct,
                payment_collect=connection.payment_collect_model,
                mapped_pairs=len(pairs[connection.id]),
                last_tested_at=_tested_at(connection),
                created_at=connection.created_at,
            )
        )
    return result


async def _health(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    connection: ChannelConnection,
    pairs: list[MappingPair],
) -> MappingHealth:
    ours = await _own_pairs(session, context, property_id)
    theirs = _channel_pairs(connection.settings.get(PRODUCTS))
    matched_ours = {(pair.room_type_id, pair.rate_plan_id) for pair in pairs}
    matched_theirs = {(pair.external_room_id, pair.external_rate_id) for pair in pairs}
    smaller, switched_off, missing = [], [], []
    for pair in pairs:
        own_key = (pair.room_type_id, pair.rate_plan_id)
        their_key = (pair.external_room_id, pair.external_rate_id)
        if own_key not in ours:
            switched_off.append(pair)
        if their_key not in theirs:
            missing.append(pair)
        if own_key in ours and their_key in theirs and theirs[their_key] < ours[own_key]:
            smaller.append(pair)
    return MappingHealth(
        unmatched_pairs=len(set(ours) - matched_ours),
        unmatched_channel_rates=len(set(theirs) - matched_theirs),
        smaller_capacity=smaller,
        switched_off=switched_off,
        missing_on_channel=missing,
    )


async def push_health(
    session: AsyncSession, context: TenantContext, prop: Property, connection: ChannelConnection
) -> ConnectionHealth:
    """Sender health of one connection: what is waiting, what is failing, how stale."""
    from app.services.channel_queue import oldest_pending_at, pending_counts
    from app.tenancy.business_settings import resolve_property_settings

    settings = resolve_property_settings(prop.settings)
    pending = (await pending_counts(session, context, prop.id)).get(connection.id, 0)
    oldest = await oldest_pending_at(session, context, connection.id)
    now = dt.datetime.now(dt.UTC)
    stale_after = dt.timedelta(hours=settings.channel_stale_after_hours)
    pending_after = dt.timedelta(minutes=settings.channel_pending_stale_minutes)
    last_success = connection.last_ari_success_at
    at_risk = (
        (pending > 0 and oldest is not None and (now - oldest) > pending_after)
        or (connection.status in ("live", "paused") and connection.failing_since is not None)
        or (
            connection.status == "live"
            and (last_success is None or (now - last_success) > stale_after)
        )
    )
    return ConnectionHealth(
        pending_updates=pending,
        oldest_pending_at=oldest,
        failing_since=connection.failing_since,
        next_push_at=connection.next_push_at,
        at_risk=at_risk,
        last_success_at=last_success,
    )


async def recent_messages(
    session: AsyncSession, context: TenantContext, connection_id: UUID, limit: int = 30
) -> list[MessageLogEntry]:
    rows = await session.exec(
        select(ChannelMessage)
        .where(
            col(ChannelMessage.tenant_id) == context.tenant_id,
            col(ChannelMessage.channel_connection_id) == connection_id,
        )
        .order_by(col(ChannelMessage.created_at).desc(), col(ChannelMessage.id).desc())
        .limit(limit)
    )
    return [
        MessageLogEntry(
            message_type=row.message_type,
            status=row.status,
            attempts=row.attempts,
            date_from=row.date_from,
            date_to=row.date_to,
            error=row.error,
            next_attempt_at=row.next_attempt_at,
            sent_at=row.sent_at,
            created_at=row.created_at,
        )
        for row in rows.all()
    ]


async def read_detail(
    session: AsyncSession, context: TenantContext, prop: Property, connection: ChannelConnection
) -> ConnectionDetail:
    [summary] = await read_many(session, context, [connection])
    pairs = (await _mappings(session, context, [connection.id]))[connection.id]
    products = connection.settings.get(PRODUCTS)
    history = await tenant_audit.history_of(session, context, ENTITY, connection.id, HISTORY_LIMIT)
    return ConnectionDetail(
        **summary.model_dump(),
        mappings=pairs,
        products=ChannelProductsRead.model_validate(products) if products else None,
        health=await _health(session, context, prop.id, connection, pairs),
        push_health=await push_health(session, context, prop, connection),
        messages=await recent_messages(session, context, connection.id),
        history=[
            HistoryEntry(
                event=entry.event_id,
                actor=entry.actor_id,
                at=entry.occurred_at,
                details=entry.payload,
            )
            for entry in history
        ],
    )
