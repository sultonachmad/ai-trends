"""Calendar links: one room type paired with one outside site, in both directions.

A link is two `icalfeed` rows sharing `link_id`: the export (our private `.ics` link) and
optionally the import (the site's link). Links create no channel connection, so they do
not count toward the plan's channel limit. URLs and tokens never reach logs or history.
"""

import datetime as dt
import logging
import uuid
from dataclasses import dataclass
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import delete, func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.channels.ical_fetch import check_url
from app.channels.ical_format import Window, build_calendar
from app.models.tenant import IcalBlock, IcalFeed, Property, UnitType
from app.payments.tokens import fingerprint, new_token
from app.schemas.calendar_links import (
    CalendarImportStatus,
    CalendarLinkCreated,
    CalendarLinkCreateRequest,
    CalendarLinkRead,
    CalendarLinkUpdateRequest,
)
from app.services import channel_queue, inventory, tenant_audit
from app.services.calendar import closed_nights
from app.services.calendar_dates import property_today
from app.services.channel_connections import lock_property
from app.tenancy.business_settings import resolve_property_settings
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

ENTITY = "icalfeed"
EXPORT, IMPORT = "export", "import"
HORIZON_DAYS = 366
MAX_LINKS_PER_PROPERTY = 50
MAX_CONFLICT_DATES = 30
EXPORT_PATH = "/api/ical/{token}.ics"


class CalendarLinkNotFoundError(Exception):
    pass


class UnknownRoomTypeError(Exception):
    pass


class TooManyLinksError(Exception):
    pass


@dataclass(frozen=True)
class LinkFeeds:
    export: IcalFeed
    imported: IcalFeed | None


def selling_window(prop: Property) -> Window:
    today = property_today(prop.timezone)
    return Window(today, today + dt.timedelta(days=HORIZON_DAYS))


def _export_path(token: str) -> str:
    return EXPORT_PATH.format(token=token)


async def find_link(
    session: AsyncSession, context: TenantContext, property_id: UUID, link_id: UUID
) -> LinkFeeds:
    rows = (
        await session.exec(
            select(IcalFeed)
            .where(
                col(IcalFeed.tenant_id) == context.tenant_id,
                col(IcalFeed.property_id) == property_id,
                col(IcalFeed.link_id) == link_id,
            )
            .execution_options(populate_existing=True)
        )
    ).all()
    by_direction = {row.direction: row for row in rows}
    if EXPORT not in by_direction:
        raise CalendarLinkNotFoundError
    return LinkFeeds(by_direction[EXPORT], by_direction.get(IMPORT))


async def _active_room(
    session: AsyncSession, context: TenantContext, property_id: UUID, room_type_id: UUID
) -> UnitType:
    room = (
        await session.exec(
            select(UnitType).where(
                col(UnitType.tenant_id) == context.tenant_id,
                col(UnitType.property_id) == property_id,
                col(UnitType.id) == room_type_id,
                col(UnitType.is_active).is_(True),
            )
        )
    ).first()
    if room is None:
        raise UnknownRoomTypeError
    return room


def _new_feed(
    context: TenantContext,
    prop_id: UUID,
    room_type_id: UUID,
    link_id: UUID,
    label: str,
    **fields: object,
) -> IcalFeed:
    return IcalFeed(
        tenant_id=context.tenant_id,
        property_id=prop_id,
        unit_type_id=room_type_id,
        link_id=link_id,
        label=label,
        created_by=str(context.user_id),
        **fields,
    )


async def _audit(session: AsyncSession, context: TenantContext, event: str, feed: IcalFeed) -> None:
    await tenant_audit.record(
        session,
        context,
        f"calendar_link.{event}",
        property_id=feed.property_id,
        entity_table=ENTITY,
        entity_id=feed.id,
        payload={"label": feed.label, "room_type_id": str(feed.unit_type_id)},
    )


async def create_link(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    request: CalendarLinkCreateRequest,
) -> CalendarLinkCreated:
    """Create a link. Commits. The answer is the only time the private link is shown."""
    import_url = check_url(request.import_url) if request.import_url else None
    await lock_property(session, context, prop.id)
    await _active_room(session, context, prop.id, request.room_type_id)
    count = (
        await session.exec(
            select(func.count())
            .select_from(IcalFeed)
            .where(
                col(IcalFeed.tenant_id) == context.tenant_id,
                col(IcalFeed.property_id) == prop.id,
                col(IcalFeed.direction) == EXPORT,
            )
        )
    ).one()
    if count >= MAX_LINKS_PER_PROPERTY:
        await session.rollback()
        raise TooManyLinksError
    link_id, token = uuid.uuid4(), new_token()
    make = lambda **fields: _new_feed(  # noqa: E731
        context, prop.id, request.room_type_id, link_id, request.label, **fields
    )
    export = make(direction=EXPORT, export_token_hash=fingerprint(token))
    session.add(export)
    if import_url:
        session.add(make(direction=IMPORT, url=import_url))
    await session.flush()
    await _audit(session, context, "created", export)
    await session.commit()
    read = await read_link(session, context, prop, link_id)
    return CalendarLinkCreated(**read.model_dump(), export_path=_export_path(token))


async def release_blocks(
    session: AsyncSession, context: TenantContext, prop: Property, feed: IcalFeed
) -> None:
    """Give back every date this import holds. The caller holds the property lock."""
    nights = list(
        (
            await session.exec(
                select(col(IcalBlock.stay_date)).where(
                    col(IcalBlock.tenant_id) == context.tenant_id,
                    col(IcalBlock.feed_id) == feed.id,
                )
            )
        ).all()
    )
    if not nights:
        return
    await inventory.unblock_units(session, context, feed.unit_type_id, nights)
    await session.exec(
        delete(IcalBlock).where(
            col(IcalBlock.tenant_id) == context.tenant_id, col(IcalBlock.feed_id) == feed.id
        )
    )
    await channel_queue.enqueue(session, context, prop.id, [feed.unit_type_id], nights)


async def _set_import_url(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    feeds: LinkFeeds,
    url: str | None,
) -> None:
    current = feeds.imported
    if url is None:
        if current is not None:
            await release_blocks(session, context, prop, current)
            await session.delete(current)
        return
    if current is None:
        export = feeds.export
        session.add(
            _new_feed(
                context,
                prop.id,
                export.unit_type_id,
                export.link_id,
                export.label,
                direction=IMPORT,
                url=url,
            )
        )
    elif current.url != url:
        current.url = url
        current.last_synced_at = current.last_attempt_at = None
        current.last_error = current.failing_since = None
        session.add(current)


async def update_link(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    link_id: UUID,
    request: CalendarLinkUpdateRequest,
) -> CalendarLinkRead:
    """Rename, set or stop the import. A changed URL keeps blocks until its first good read."""
    sent = request.model_dump(exclude_unset=True)
    url = sent.get("import_url")
    if url:
        check_url(url)
    await lock_property(session, context, prop.id)
    feeds = await find_link(session, context, prop.id, link_id)
    if "import_url" in sent:
        await _set_import_url(session, context, prop, feeds, url)
    if sent.get("label"):
        for feed in (feeds.export, feeds.imported):
            if feed is not None and feed in session:
                feed.label = sent["label"]
                session.add(feed)
    await _audit(session, context, "changed", feeds.export)
    await session.commit()
    read = await read_link(session, context, prop, link_id)
    return read


async def replace_token(
    session: AsyncSession, context: TenantContext, prop: Property, link_id: UUID
) -> CalendarLinkCreated:
    """Issue a new private link; the old one stops working at once. Commits."""
    await lock_property(session, context, prop.id)
    feeds = await find_link(session, context, prop.id, link_id)
    token = new_token()
    feeds.export.export_token_hash = fingerprint(token)
    session.add(feeds.export)
    await _audit(session, context, "token_replaced", feeds.export)
    await session.commit()
    read = await read_link(session, context, prop, link_id)
    return CalendarLinkCreated(**read.model_dump(), export_path=_export_path(token))


async def remove_link(
    session: AsyncSession, context: TenantContext, prop: Property, link_id: UUID
) -> None:
    """Remove a link and give back everything it blocked. Commits."""
    await lock_property(session, context, prop.id)
    feeds = await find_link(session, context, prop.id, link_id)
    await _audit(session, context, "removed", feeds.export)
    if feeds.imported is not None:
        await release_blocks(session, context, prop, feeds.imported)
        await session.delete(feeds.imported)
    await session.delete(feeds.export)
    await session.commit()


# ---- reading ------------------------------------------------------------------------


async def _blocks_by_feed(
    session: AsyncSession, context: TenantContext, feed_ids: list[UUID], today: dt.date
) -> dict[UUID, list[dt.date]]:
    if not feed_ids:
        return {}
    rows = await session.exec(
        select(col(IcalBlock.feed_id), col(IcalBlock.stay_date))
        .where(
            col(IcalBlock.tenant_id) == context.tenant_id,
            col(IcalBlock.feed_id).in_(feed_ids),
            col(IcalBlock.stay_date) >= today,
        )
        .order_by(col(IcalBlock.stay_date))
    )
    found: dict[UUID, list[dt.date]] = {}
    for feed_id, night in rows.all():
        found.setdefault(feed_id, []).append(night)
    return found


def _import_status(
    feed: IcalFeed, busy: int, stale_hours: int, now: dt.datetime
) -> CalendarImportStatus:
    failing = feed.failing_since
    return CalendarImportStatus(
        url_hint=urlsplit(feed.url or "").hostname or "",
        last_synced_at=feed.last_synced_at,
        last_error=feed.last_error,
        failing_since=failing,
        at_risk=failing is not None and now - failing >= dt.timedelta(hours=stale_hours),
        busy_dates=busy,
    )


async def _conflicts(
    session: AsyncSession,
    context: TenantContext,
    feeds: list[IcalFeed],
    blocks: dict[UUID, list[dt.date]],
    window: Window,
) -> dict[UUID, list[dt.date]]:
    """Per import feed, its busy dates on which more is taken than there are units."""
    room_ids = list({feed.unit_type_id for feed in feeds if blocks.get(feed.id)})
    if not room_ids:
        return {}
    units = await inventory.units_in_use(session, context, room_ids)
    last = window.end - dt.timedelta(days=1)
    taken = await inventory.taken_by_night(session, context, room_ids, window.start, last)
    return {
        feed.id: [
            night
            for night in blocks.get(feed.id, [])
            if taken.get((feed.unit_type_id, night), 0) > units.get(feed.unit_type_id, 0)
        ][:MAX_CONFLICT_DATES]
        for feed in feeds
    }


async def read_links(
    session: AsyncSession, context: TenantContext, prop: Property, link_id: UUID | None = None
) -> list[CalendarLinkRead]:
    """The property's links, oldest first (or just one)."""
    statement = (
        select(IcalFeed, col(UnitType.name))
        .join(
            UnitType,
            (col(UnitType.tenant_id) == col(IcalFeed.tenant_id))
            & (col(UnitType.id) == col(IcalFeed.unit_type_id)),
        )
        .where(col(IcalFeed.tenant_id) == context.tenant_id, col(IcalFeed.property_id) == prop.id)
        .order_by(col(IcalFeed.created_at), col(IcalFeed.id))
        .execution_options(populate_existing=True)
    )
    if link_id is not None:
        statement = statement.where(col(IcalFeed.link_id) == link_id)
    rows = (await session.exec(statement)).all()
    imports = {feed.link_id: feed for feed, _name in rows if feed.direction == IMPORT}
    window = selling_window(prop)
    import_feeds = list(imports.values())
    blocks = await _blocks_by_feed(session, context, [f.id for f in import_feeds], window.start)
    conflicts = await _conflicts(session, context, import_feeds, blocks, window)
    stale = resolve_property_settings(prop.settings).calendar_stale_hours
    now = dt.datetime.now(dt.UTC)
    result = []
    for feed, room_name in rows:
        if feed.direction != EXPORT:
            continue
        imported = imports.get(feed.link_id)
        result.append(
            CalendarLinkRead(
                id=feed.link_id,
                label=feed.label,
                room_type_id=feed.unit_type_id,
                room_type_name=room_name,
                imports=_import_status(imported, len(blocks.get(imported.id, [])), stale, now)
                if imported is not None
                else None,
                conflict_dates=conflicts.get(imported.id, []) if imported is not None else [],
            )
        )
    return result


async def read_link(
    session: AsyncSession, context: TenantContext, prop: Property, link_id: UUID
) -> CalendarLinkRead:
    found = await read_links(session, context, prop, link_id)
    if not found:
        raise CalendarLinkNotFoundError
    return found[0]


# ---- the public calendar ------------------------------------------------------------


async def export_calendar(session: AsyncSession, context: TenantContext, token_hash: str) -> bytes:
    """The `.ics` for a private link. Raises `CalendarLinkNotFoundError`."""
    feed = (
        await session.exec(
            select(IcalFeed).where(
                col(IcalFeed.tenant_id) == context.tenant_id,
                col(IcalFeed.export_token_hash) == token_hash,
                col(IcalFeed.is_active).is_(True),
            )
        )
    ).first()
    if feed is None:
        raise CalendarLinkNotFoundError
    prop = (
        await session.exec(
            select(Property).where(
                col(Property.tenant_id) == context.tenant_id, col(Property.id) == feed.property_id
            )
        )
    ).one()
    busy = await _busy_for_site(session, context, prop, feed)
    return build_calendar(busy, uid_seed=str(feed.id), now=dt.datetime.now(dt.UTC))


async def _busy_for_site(
    session: AsyncSession, context: TenantContext, prop: Property, feed: IcalFeed
) -> list[dt.date]:
    """Dates with nothing left for this site, not counting what the site itself blocked."""
    window = selling_window(prop)
    last = window.end - dt.timedelta(days=1)
    room_id = feed.unit_type_id
    units = (await inventory.units_in_use(session, context, [room_id])).get(room_id, 0)
    taken = await inventory.taken_by_night(session, context, [room_id], window.start, last)
    closed = await closed_nights(session, context, prop.id, room_id, window.start, last)
    own = set(await _own_blocks(session, context, feed.link_id, window.start))
    hold_back = resolve_property_settings(prop.settings).channel_hold_back_units
    days = [window.start + dt.timedelta(days=n) for n in range(HORIZON_DAYS)]
    return [
        day
        for day in days
        if day in closed
        or units - taken.get((room_id, day), 0) + (1 if day in own else 0) - hold_back <= 0
    ]


async def _own_blocks(
    session: AsyncSession, context: TenantContext, link_id: UUID, start: dt.date
) -> list[dt.date]:
    rows = await session.exec(
        select(col(IcalBlock.stay_date))
        .join(
            IcalFeed,
            (col(IcalFeed.tenant_id) == col(IcalBlock.tenant_id))
            & (col(IcalFeed.id) == col(IcalBlock.feed_id)),
        )
        .where(
            col(IcalBlock.tenant_id) == context.tenant_id,
            col(IcalFeed.link_id) == link_id,
            col(IcalBlock.stay_date) >= start,
        )
    )
    return list(rows.all())
