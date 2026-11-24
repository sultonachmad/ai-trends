"""Deleting guest ID images after the stay, and ID numbers after their retention date.

* Images (`document`, kind `identity_scan`): kept until `retention_until`, set at
  confirmation to departure + `id_image_retention_days` (7 by default), brought forward
  at check-out, no-show and cancellation, and one day for a photo nobody confirmed. The
  file is deleted and `purged_at` stamped; the row stays.
* Numbers (`guestdocument`): kept until `retention_until`, departure +
  `id_number_retention_days` (2 years by default, pending legal review). The encrypted
  number, its hash and last digits are cleared; the rest of the record stays.

Like the transfer-proof purge it walks tenant by tenant on tenant-scoped sessions, so
row-level security applies. It runs at start-up, every hour while the app runs
(`run_id_purge_loop`), or by hand (`python -m app.jobs.purge_ids`).
"""

import asyncio
import datetime as dt
import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.documents.storage import DocumentStorage
from app.models.control_plane import Tenant
from app.models.tenant import (
    Document,
    GuestDocument,
    Reservation,
    ReservationGuest,
    ReservationUnit,
)
from app.services.guest_id_reads import guests_of
from app.services.stay_status import NOT_ACTIVE
from app.tenancy.business_settings import resolve_property_settings
from app.tenancy.context import TenantContext
from app.tenancy.session import bind_tenant

log = logging.getLogger(__name__)

SCAN_KIND = "identity_scan"
BATCH = 200
MAX_BATCHES = 50  # at most 10,000 of each per tenant per run; the next run continues
PURGE_INTERVAL_SECONDS = 60 * 60  # hourly, so "the next day" and "7 days after" hold


@dataclass(frozen=True)
class Purged:
    images: int = 0
    numbers: int = 0

    def __add__(self, other: "Purged") -> "Purged":
        return Purged(self.images + other.images, self.numbers + other.numbers)


async def _still_staying(
    session: AsyncSession,
    context: TenantContext,
    booking: Reservation,
    guest_ids: list[UUID],
    today: dt.date,
) -> set[UUID]:
    """Guests who are on another live booking that has not ended yet."""
    live = (
        col(Reservation.tenant_id) == context.tenant_id,
        col(Reservation.id) != booking.id,
        col(Reservation.status).not_in(NOT_ACTIVE),
        col(Reservation.departure_date) >= today,
    )
    as_booker = await session.exec(
        select(Reservation.booker_guest_id).where(
            *live, col(Reservation.booker_guest_id).in_(guest_ids)
        )
    )
    as_guest = await session.exec(
        select(ReservationGuest.guest_id)
        .join(
            ReservationUnit,
            (col(ReservationUnit.tenant_id) == col(ReservationGuest.tenant_id))
            & (col(ReservationUnit.id) == col(ReservationGuest.reservation_unit_id)),
        )
        .join(
            Reservation,
            (col(Reservation.tenant_id) == col(ReservationUnit.tenant_id))
            & (col(Reservation.id) == col(ReservationUnit.reservation_id)),
        )
        .where(*live, col(ReservationGuest.guest_id).in_(guest_ids))
    )
    return {g for g in [*as_booker.all(), *as_guest.all()] if g is not None}


async def stay_ended(
    session: AsyncSession,
    context: TenantContext,
    booking: Reservation,
    lines: list[ReservationUnit],
    today: dt.date,
    settings: dict | None,
) -> None:
    """Bring image deletion forward to `today` + the image days. Flushed, not committed.

    Guests who still have another stay going on keep their photo until that one ends.
    """
    ids = [guest.id for guest, _ in await guests_of(session, context, booking, lines)]
    ids = [g for g in ids if g not in await _still_staying(session, context, booking, ids, today)]
    if not ids:
        return
    until = today + dt.timedelta(days=resolve_property_settings(settings).id_image_retention_days)
    scans = await session.exec(
        select(Document)
        .join(
            GuestDocument,
            (col(GuestDocument.tenant_id) == col(Document.tenant_id))
            & (col(GuestDocument.scan_document_id) == col(Document.id)),
        )
        .where(
            col(Document.tenant_id) == context.tenant_id,
            col(GuestDocument.guest_id).in_(ids),
            col(Document.purged_at).is_(None),
            (col(Document.retention_until).is_(None)) | (col(Document.retention_until) > until),
        )
    )
    for scan in scans.all():
        scan.retention_until = until
        session.add(scan)


async def _purge_images(
    session: AsyncSession, storage: DocumentStorage, tenant_id: UUID, today: dt.date
) -> int:
    due = (
        await session.exec(
            select(Document)
            .where(
                col(Document.tenant_id) == tenant_id,
                col(Document.kind) == SCAN_KIND,
                col(Document.purged_at).is_(None),
                col(Document.retention_until) < today,
            )
            .order_by(col(Document.retention_until))
            .limit(BATCH)
            .with_for_update(skip_locked=True)
        )
    ).all()
    purged = 0
    for document in due:
        try:
            await storage.delete(tenant_id, document.storage_key)
        except Exception:  # noqa: BLE001 — one bad file must not stop the rest
            log.exception("Could not delete expired ID image document=%s", document.id)
            continue
        document.purged_at = dt.datetime.now(dt.UTC)
        session.add(document)
        purged += 1
    return purged


async def _clear_numbers(session: AsyncSession, tenant_id: UUID, today: dt.date) -> int:
    due = (
        await session.exec(
            select(GuestDocument)
            .where(
                col(GuestDocument.tenant_id) == tenant_id,
                col(GuestDocument.doc_number_encrypted).is_not(None),
                col(GuestDocument.retention_until) < today,
            )
            .order_by(col(GuestDocument.retention_until))
            .limit(BATCH)
            .with_for_update(skip_locked=True)
        )
    ).all()
    for document in due:
        document.doc_number_encrypted = None
        document.doc_number_hash = None
        document.doc_number_last4 = None
        session.add(document)
    return len(due)


async def _purge_tenant(
    session: AsyncSession, storage: DocumentStorage, tenant_id: UUID, today: dt.date
) -> Purged:
    """Batch by batch, each committed, so check-in and confirm are never held up long."""
    total = Purged()
    for _ in range(MAX_BATCHES):
        done = Purged(
            images=await _purge_images(session, storage, tenant_id, today),
            numbers=await _clear_numbers(session, tenant_id, today),
        )
        await session.commit()
        total += done
        if done.images < BATCH and done.numbers < BATCH:
            break
    return total


async def purge_expired_ids(
    session_factory: async_sessionmaker[AsyncSession],
    storage: DocumentStorage,
    today: dt.date | None = None,
) -> Purged:
    """Delete every ID image and number past its date. Returns how many."""
    today = today or dt.datetime.now(dt.UTC).date()
    async with session_factory() as session:
        tenant_ids = list((await session.exec(select(Tenant.id))).all())
    total = Purged()
    for tenant_id in tenant_ids:
        try:
            async with session_factory() as session:
                await bind_tenant(session, tenant_id)
                total += await _purge_tenant(session, storage, tenant_id, today)
        except Exception:  # noqa: BLE001 — keep going with the other tenants
            log.exception("ID retention failed for tenant=%s", tenant_id)
    if total.images or total.numbers:
        log.info("Deleted %d ID image(s) and %d ID number(s)", total.images, total.numbers)
    return total


async def run_id_purge_loop(
    session_factory: async_sessionmaker[AsyncSession],
    stop: asyncio.Event,
    interval_seconds: int = PURGE_INTERVAL_SECONDS,
) -> None:
    """Background loop started with the app: purge, then wait. Never raises."""
    log.info("Guest ID retention runs every %ss", interval_seconds)
    while not stop.is_set():
        try:
            await purge_expired_ids(session_factory, DocumentStorage())
        except Exception:  # noqa: BLE001 — the loop must survive anything
            log.exception("Guest ID retention tick failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
        except TimeoutError:
            pass
