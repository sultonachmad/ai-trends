"""Reading imported calendars: fetch with no lock held, then apply the difference.

A failed or unreadable calendar changes nothing: its dates stay blocked and the error is
shown. Dates are released only when a valid calendar no longer lists them. Every change
to availability is queued for connected channels in the same transaction.
"""

import asyncio
import datetime as dt
import logging
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import delete, or_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.channels.ical_fetch import IcalFetchError, fetch_calendar
from app.channels.ical_format import IcalFormatError, build_calendar, busy_dates
from app.channels.simulator import find_listing
from app.config import settings as app_settings
from app.models.control_plane import Tenant
from app.models.tenant import IcalBlock, IcalFeed, Property
from app.services import channel_queue, inventory
from app.services.calendar_links import IMPORT, selling_window
from app.services.channel_connections import lock_property
from app.services.channel_push import _context as worker_context
from app.tenancy.business_settings import resolve_property_settings
from app.tenancy.context import TenantContext
from app.tenancy.session import bind_tenant

log = logging.getLogger(__name__)

SIMULATED_HOST = "simulated-calendar.invalid"
MAX_FEEDS_PER_TICK = 100
UNREADABLE = "unreadable"


def simulated_url(hotel_id: str) -> str:
    return f"https://{SIMULATED_HOST}/{hotel_id}.ics"


async def _simulated_calendar(session: AsyncSession, tenant_id: UUID, url: str) -> bytes:
    """The dev-only test calendar, read in-process: no network is involved."""
    hotel_id = urlsplit(url).path.strip("/").removesuffix(".ics")
    listing = await find_listing(session, tenant_id, hotel_id)
    await session.commit()
    if listing is None or (listing.calendar or {}).get("broken"):
        raise IcalFetchError("unreachable")
    busy = [dt.date.fromisoformat(day) for day in (listing.calendar or {}).get("busy", [])]
    # the test site uses its own event ids, so they are not mistaken for our export
    raw = build_calendar(busy, uid_seed=hotel_id, now=dt.datetime.now(dt.UTC))
    return raw.replace(b"@availability-export", b"@simulated-site")


async def _read_calendar(session: AsyncSession, tenant_id: UUID, url: str) -> bytes:
    if app_settings.CHANNEL_SIMULATOR_ENABLED and urlsplit(url).hostname == SIMULATED_HOST:
        return await _simulated_calendar(session, tenant_id, url)
    return await fetch_calendar(url)


async def _locked_feed(
    session: AsyncSession, context: TenantContext, property_id: UUID, feed_id: UUID
) -> IcalFeed | None:
    await lock_property(session, context, property_id)
    return (
        await session.exec(
            select(IcalFeed)
            .where(col(IcalFeed.tenant_id) == context.tenant_id, col(IcalFeed.id) == feed_id)
            .execution_options(populate_existing=True)
        )
    ).first()


async def _record_failure(
    session: AsyncSession,
    context: TenantContext,
    property_id: UUID,
    feed_id: UUID,
    url: str,
    code: str,
) -> None:
    feed = await _locked_feed(session, context, property_id, feed_id)
    if feed is not None and feed.url == url:  # the URL may have been changed meanwhile
        feed.last_error = code
        feed.failing_since = feed.failing_since or dt.datetime.now(dt.UTC)
        session.add(feed)
    await session.commit()
    log.warning("Calendar import failed feed=%s code=%s", feed_id, code)


async def _apply(
    session: AsyncSession,
    context: TenantContext,
    prop: Property,
    feed: IcalFeed,
    wanted: set[dt.date],
) -> None:
    """Make the feed's stored dates equal `wanted`. The caller holds the property lock."""
    window = selling_window(prop)
    held = set(
        (
            await session.exec(
                select(col(IcalBlock.stay_date)).where(
                    col(IcalBlock.tenant_id) == context.tenant_id,
                    col(IcalBlock.feed_id) == feed.id,
                    col(IcalBlock.stay_date) >= window.start,
                )
            )
        ).all()
    )
    added, removed = sorted(wanted - held), sorted(held - wanted)
    room_id = feed.unit_type_id
    if removed:
        await inventory.unblock_units(session, context, room_id, removed)
        await session.exec(
            delete(IcalBlock).where(
                col(IcalBlock.tenant_id) == context.tenant_id,
                col(IcalBlock.feed_id) == feed.id,
                col(IcalBlock.stay_date).in_(removed),
            )
        )
    if added:
        units = (await inventory.units_in_use(session, context, [room_id])).get(room_id, 0)
        await inventory.block_units(session, context, prop.id, room_id, added, units)
        rows = [
            {
                "tenant_id": context.tenant_id,
                "feed_id": feed.id,
                "unit_type_id": room_id,
                "stay_date": night,
            }
            for night in added
        ]
        await session.exec(pg_insert(IcalBlock).values(rows))
    if added or removed:
        await channel_queue.enqueue(session, context, prop.id, [room_id], [*added, *removed])


async def sync_feed(session: AsyncSession, context: TenantContext, feed_id: UUID) -> bool:
    """Read one imported calendar. True when it was read and applied. Commits."""
    feed = (
        await session.exec(
            select(IcalFeed)
            .where(
                col(IcalFeed.tenant_id) == context.tenant_id,
                col(IcalFeed.id) == feed_id,
                col(IcalFeed.direction) == IMPORT,
                col(IcalFeed.is_active).is_(True),
            )
            .execution_options(populate_existing=True)
        )
    ).first()
    if feed is None:
        await session.commit()  # commit, not rollback: the caller's objects stay usable
        return False
    url, property_id = feed.url or "", feed.property_id
    prop = (
        await session.exec(
            select(Property).where(
                col(Property.tenant_id) == context.tenant_id, col(Property.id) == property_id
            )
        )
    ).one()
    feed.last_attempt_at = dt.datetime.now(dt.UTC)
    session.add(feed)
    await session.commit()  # no transaction is open during the fetch
    try:
        raw = await _read_calendar(session, context.tenant_id, url)
        wanted = await asyncio.to_thread(busy_dates, raw, selling_window(prop), prop.timezone)
    except IcalFetchError as exc:
        # one stored answer for "refused" and "no such name": staff cannot map internal DNS
        code = "unreachable" if exc.code == "unsafe_address" else exc.code
        await _record_failure(session, context, property_id, feed_id, url, code)
        return False
    except IcalFormatError:
        await _record_failure(session, context, property_id, feed_id, url, UNREADABLE)
        return False
    except Exception as exc:  # noqa: BLE001 — shown on the link; no traceback, the URL is secret
        log.error("Calendar import error feed=%s type=%s", feed_id, type(exc).__name__)
        await session.rollback()
        await _record_failure(session, context, property_id, feed_id, url, UNREADABLE)
        return False
    current = await _locked_feed(session, context, property_id, feed_id)
    if current is None or current.url != url:  # removed or re-pointed during the fetch
        await session.commit()
        return False
    await _apply(session, context, prop, current, wanted)
    current.last_synced_at = dt.datetime.now(dt.UTC)
    current.last_error = current.failing_since = None
    session.add(current)
    await session.commit()
    return True


async def _due_feeds(session: AsyncSession, tenant_id: UUID, now: dt.datetime) -> list[UUID]:
    rows = await session.exec(
        select(col(IcalFeed.id), col(IcalFeed.last_attempt_at), col(Property.settings))
        .join(
            Property,
            (col(Property.tenant_id) == col(IcalFeed.tenant_id))
            & (col(Property.id) == col(IcalFeed.property_id)),
        )
        .where(
            col(IcalFeed.tenant_id) == tenant_id,
            col(IcalFeed.direction) == IMPORT,
            col(IcalFeed.is_active).is_(True),
            or_(col(IcalFeed.last_attempt_at).is_(None), col(IcalFeed.last_attempt_at) < now),
        )
        .order_by(col(IcalFeed.last_attempt_at).asc().nulls_first())
    )
    due = []
    for feed_id, attempted, raw_settings in rows.all():
        every = dt.timedelta(minutes=resolve_property_settings(raw_settings).calendar_sync_minutes)
        if attempted is None or now - attempted >= every:
            due.append(feed_id)
    await session.commit()
    return due[:MAX_FEEDS_PER_TICK]


async def sync_tenant(session: AsyncSession, tenant_id: UUID) -> int:
    """Read every calendar due for one tenant. Returns how many were applied."""
    context = worker_context(tenant_id, session)
    applied = 0
    for feed_id in await _due_feeds(session, tenant_id, dt.datetime.now(dt.UTC)):
        try:
            applied += await sync_feed(session, context, feed_id)
        except Exception:  # noqa: BLE001 — one calendar must not stop the others
            await session.rollback()
            log.exception("Calendar import crashed tenant=%s feed=%s", tenant_id, feed_id)
    return applied


async def sync_due(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        tenant_ids = list((await session.exec(select(col(Tenant.id)))).all())
    applied = 0
    for tenant_id in tenant_ids:
        try:
            async with session_factory() as session:
                await bind_tenant(session, tenant_id)
                applied += await sync_tenant(session, tenant_id)
        except Exception:  # noqa: BLE001 — keep going with the other tenants
            log.exception("Calendar sync failed for tenant=%s", tenant_id)
    return applied


async def run_calendar_sync(
    session_factory: async_sessionmaker[AsyncSession], stop: asyncio.Event, interval_seconds: int
) -> None:
    """The background loop started with the app."""
    log.info("Calendar link sync started (every %ss)", interval_seconds)
    while not stop.is_set():
        try:
            await sync_due(session_factory)
        except Exception:  # noqa: BLE001 — the loop must survive anything
            log.exception("Calendar link sync tick failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
        except TimeoutError:
            pass
    log.info("Calendar link sync stopped")
