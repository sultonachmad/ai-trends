"""Reading guests and their IDs: masked by default, every full view logged.

`guestid:view` sees masked numbers and whether an image exists. Showing a full number
or the image needs `guestid:edit` (checked by the router) and always writes a history
entry naming who looked, before anything is returned.
"""

import datetime as dt
import logging
from dataclasses import dataclass
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.documents.storage import DocumentStorage
from app.models.tenant import (
    Document,
    Guest,
    GuestDocument,
    Property,
    Reservation,
    ReservationGuest,
    ReservationUnit,
    StaffMember,
    TenantAuditEntry,
)
from app.schemas.guest_ids import GuestOnBooking, IdDocumentRead, IdView
from app.security.identity_crypto import IdentityCipher, IdentityDecryptError
from app.services import calendar_dates as dates_of
from app.services import guest_id_errors as errors
from app.services import tenant_audit
from app.services.bookings import lines_of
from app.services.stay_status import NOT_ACTIVE
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

ENTITY = "reservation"  # ID events sit in the booking's history
ID_EVENTS = ("guestid.confirmed", "guestid.number_viewed", "guestid.image_viewed")
HISTORY_LIMIT = 100
_HIDDEN = "•" * 4


@dataclass(frozen=True)
class IdentityScope:
    """Everything an ID action needs about who is asking and where."""

    session: AsyncSession
    context: TenantContext
    prop: Property
    cipher: IdentityCipher


@dataclass(frozen=True)
class GuestsView:
    booking: Reservation
    main_guest_ready: bool
    guests: list[GuestOnBooking]


# ---- who is on the booking --------------------------------------------------------------


async def locked_guest(session: AsyncSession, context: TenantContext, guest_id: UUID) -> Guest:
    guest = (
        await session.exec(
            select(Guest)
            .where(col(Guest.tenant_id) == context.tenant_id, col(Guest.id) == guest_id)
            .with_for_update()
        )
    ).first()
    if guest is None:
        raise errors.GuestNotOnBookingError
    return guest


async def guests_of(
    session: AsyncSession,
    context: TenantContext,
    booking: Reservation,
    lines: list[ReservationUnit],
) -> list[tuple[Guest, bool]]:
    """(guest, is main) for everyone on the booking, the main guest first.

    The main guest is the booker; a booking whose booker was deleted falls back to the
    primary guest of its first room, then to the first guest listed.
    """
    linked = (
        await session.exec(
            select(ReservationGuest.guest_id, ReservationGuest.is_primary)
            .where(
                col(ReservationGuest.tenant_id) == context.tenant_id,
                col(ReservationGuest.reservation_unit_id).in_([line.id for line in lines]),
            )
            .order_by(
                col(ReservationGuest.is_primary).desc(),
                col(ReservationGuest.created_at),
                col(ReservationGuest.id),
            )
        )
    ).all()
    linked_ids = [guest_id for guest_id, _ in linked]
    ordered = list(dict.fromkeys([g for g in [booking.booker_guest_id, *linked_ids] if g]))
    if not ordered:
        return []
    rows = await session.exec(
        select(Guest).where(col(Guest.tenant_id) == context.tenant_id, col(Guest.id).in_(ordered))
    )
    by_id = {guest.id: guest for guest in rows.all()}
    return [(by_id[g], index == 0) for index, g in enumerate(ordered) if g in by_id]


def is_usable(document: GuestDocument, today: dt.date) -> bool:
    return (
        document.verified_at is not None
        and document.doc_number_encrypted is not None
        and (document.expires_on is None or document.expires_on >= today)
    )


async def documents_of(
    session: AsyncSession, context: TenantContext, guest_ids: list[UUID], today: dt.date
) -> dict[UUID, GuestDocument]:
    """Each guest's best confirmed document: a usable one first, the newest first."""
    rows = await session.exec(
        select(GuestDocument)
        .where(
            col(GuestDocument.tenant_id) == context.tenant_id,
            col(GuestDocument.guest_id).in_(guest_ids),
            col(GuestDocument.verified_at).is_not(None),
        )
        .order_by(col(GuestDocument.verified_at).desc())
    )
    best: dict[UUID, GuestDocument] = {}
    for document in rows.all():
        current = best.get(document.guest_id)
        if current is None or (is_usable(document, today) and not is_usable(current, today)):
            best[document.guest_id] = document
    return best


async def _live_scans(session: AsyncSession, context: TenantContext, ids: list[UUID]) -> set:
    if not ids:
        return set()
    rows = await session.exec(
        select(Document.id).where(
            col(Document.tenant_id) == context.tenant_id,
            col(Document.id).in_(ids),
            col(Document.purged_at).is_(None),
        )
    )
    return set(rows.all())


async def staff_names(session: AsyncSession, context: TenantContext, users: set[str]) -> dict:
    ids = [int(u) for u in users if u and u.isdigit()]
    if not ids:
        return {}
    rows = await session.exec(
        select(StaffMember.user_id, StaffMember.display_name).where(
            col(StaffMember.tenant_id) == context.tenant_id, col(StaffMember.user_id).in_(ids)
        )
    )
    return {str(user): name for user, name in rows.all()}


def _document_read(document: GuestDocument, today, scans: set, names: dict) -> IdDocumentRead:
    last4 = document.doc_number_last4
    return IdDocumentRead(
        id=document.id,
        doc_type=document.doc_type,
        masked_number=f"{_HIDDEN}{last4}" if last4 and document.doc_number_encrypted else None,
        issuing_country=document.issuing_country,
        expires_on=document.expires_on,
        visa_type=document.visa_type,
        entry_date=document.entry_stamp_date,
        confirmed_at=document.verified_at,
        confirmed_by=names.get(document.verified_by or "", document.verified_by),
        has_image=document.scan_document_id in scans,
        usable=is_usable(document, today),
    )


# ---- reads ------------------------------------------------------------------------------


async def booking_of(
    session: AsyncSession, context: TenantContext, prop: Property, booking_id: UUID
) -> tuple[Reservation, list[ReservationUnit]]:
    booking = (
        await session.exec(
            select(Reservation).where(
                col(Reservation.tenant_id) == context.tenant_id,
                col(Reservation.property_id) == prop.id,
                col(Reservation.id) == booking_id,
            )
        )
    ).first()
    if booking is None:
        raise errors.DocumentNotFoundError
    return booking, await lines_of(session, context, [booking.id])


async def main_guest_ready(
    session: AsyncSession,
    context: TenantContext,
    booking: Reservation,
    lines: list[ReservationUnit],
    today: dt.date,
) -> bool:
    """True when the main guest has a confirmed, unexpired ID with its number kept."""
    on_booking = await guests_of(session, context, booking, lines)
    if not on_booking:
        return False
    main = on_booking[0][0]
    document = (await documents_of(session, context, [main.id], today)).get(main.id)
    return document is not None and is_usable(document, today)


async def read_guests(scope: IdentityScope, booking_id: UUID) -> GuestsView:
    session, context = scope.session, scope.context
    today = dates_of.property_today(scope.prop.timezone)
    booking, lines = await booking_of(session, context, scope.prop, booking_id)
    on_booking = await guests_of(session, context, booking, lines)
    documents = await documents_of(session, context, [g.id for g, _ in on_booking], today)
    scans = await _live_scans(
        session, context, [d.scan_document_id for d in documents.values() if d.scan_document_id]
    )
    names = await staff_names(session, context, {d.verified_by or "" for d in documents.values()})
    guests = [
        GuestOnBooking(
            guest_id=guest.id,
            full_name=guest.full_name,
            is_main=is_main,
            nationality=guest.nationality,
            birth_date=guest.birth_date,
            gender=guest.gender,
            document=(
                _document_read(documents[guest.id], today, scans, names)
                if guest.id in documents
                else None
            ),
        )
        for guest, is_main in on_booking
    ]
    ready = bool(guests) and guests[0].document is not None and guests[0].document.usable
    return GuestsView(booking=booking, main_guest_ready=ready, guests=guests)


def can_change(booking: Reservation) -> bool:
    return booking.status not in NOT_ACTIVE


# ---- full views, always logged ----------------------------------------------------------


async def _document_on_booking(
    scope: IdentityScope, booking_id: UUID, document_id: UUID
) -> tuple[Reservation, GuestDocument]:
    booking, lines = await booking_of(scope.session, scope.context, scope.prop, booking_id)
    guest_ids = {g.id for g, _ in await guests_of(scope.session, scope.context, booking, lines)}
    document = (
        await scope.session.exec(
            select(GuestDocument).where(
                col(GuestDocument.tenant_id) == scope.context.tenant_id,
                col(GuestDocument.id) == document_id,
            )
        )
    ).first()
    if document is None or document.guest_id not in guest_ids:
        raise errors.DocumentNotFoundError
    return booking, document


async def _log_view(
    scope: IdentityScope, booking: Reservation, document: GuestDocument, event: str
) -> None:
    await tenant_audit.record(
        scope.session,
        scope.context,
        event,
        property_id=booking.property_id,
        entity_table=ENTITY,
        entity_id=booking.id,
        payload={"guest_id": str(document.guest_id), "document_id": str(document.id)},
    )
    await scope.session.commit()


async def reveal_number(scope: IdentityScope, booking_id: UUID, document_id: UUID) -> str:
    """The full number. The view is logged (and committed) before it is returned."""
    booking, document = await _document_on_booking(scope, booking_id, document_id)
    if document.doc_number_encrypted is None:
        raise errors.NumberClearedError
    try:
        number = scope.cipher.decrypt_number(
            scope.context.tenant_id, document.id, document.doc_number_encrypted
        )
    except IdentityDecryptError:
        # Not a retention case: the key changed or the row was altered. Say so in the log.
        log.error("ID number does not decrypt document=%s (key changed?)", document.id)
        raise errors.NumberUnreadableError from None
    await _log_view(scope, booking, document, "guestid.number_viewed")
    return number


@dataclass(frozen=True)
class ScanImage:
    content: bytes
    content_type: str


async def read_image(
    scope: IdentityScope, storage: DocumentStorage, booking_id: UUID, document_id: UUID
) -> ScanImage:
    """The decrypted photo. The view is logged (and committed) before it is returned."""
    booking, document = await _document_on_booking(scope, booking_id, document_id)
    scan = (
        await scope.session.get(Document, document.scan_document_id)
        if document.scan_document_id
        else None
    )
    if scan is None or scan.purged_at is not None:
        raise errors.ImageGoneError
    try:
        sealed = await storage.read(scope.context.tenant_id, scan.storage_key)
        content = scope.cipher.decrypt_file(scope.context.tenant_id, scan.id, sealed)
    except FileNotFoundError:
        raise errors.ImageGoneError from None
    except IdentityDecryptError:
        log.error("ID photo does not decrypt document=%s (key changed?)", scan.id)
        raise errors.NumberUnreadableError from None
    await _log_view(scope, booking, document, "guestid.image_viewed")
    return ScanImage(content=content, content_type=scan.content_type)


async def id_history(scope: IdentityScope, booking_id: UUID) -> list[IdView]:
    """Who confirmed or looked at this booking's IDs, newest first."""
    booking, _ = await booking_of(scope.session, scope.context, scope.prop, booking_id)
    rows = (
        await scope.session.exec(
            select(TenantAuditEntry)
            .where(
                col(TenantAuditEntry.tenant_id) == scope.context.tenant_id,
                col(TenantAuditEntry.entity_table) == ENTITY,
                col(TenantAuditEntry.entity_id) == booking.id,
                col(TenantAuditEntry.event_id).in_(ID_EVENTS),
            )
            .order_by(col(TenantAuditEntry.occurred_at).desc())
            .limit(HISTORY_LIMIT)
        )
    ).all()
    names = await staff_names(scope.session, scope.context, {r.actor_id or "" for r in rows})
    return [
        IdView(
            event=row.event_id.removeprefix("guestid."),
            at=row.occurred_at,
            by=names.get(row.actor_id or "", row.actor_id or ""),
            guest_id=row.payload.get("guest_id"),
            document_id=row.payload.get("document_id"),
        )
        for row in rows
    ]
