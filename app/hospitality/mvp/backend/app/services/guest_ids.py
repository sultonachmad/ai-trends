"""Capturing and confirming guest IDs at the front desk.

A photo is encrypted and stored first (`store_scan`), the reader suggests fields, and
staff confirm the fields they checked against the document (`confirm`). Only then is a
`guestdocument` written: the number encrypted, a keyed hash for "seen before", the
last four digits, and the guest's name, nationality, birth date and gender copied onto
their profile.

The booker is the main guest. Other adults are added as `reservationguest` rows on the
booking's first room. Writes lock the property, then the booking, like every other
booking change.
"""

import datetime as dt
import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.documents.images import detect_image_type
from app.documents.storage import DocumentStorage
from app.models.tenant import (
    Document,
    Guest,
    GuestDocument,
    Property,
    Reservation,
    ReservationGuest,
    ReservationUnit,
)
from app.schemas.guest_ids import ConfirmIdRequest
from app.services import calendar_dates as dates_of
from app.services import guest_id_errors as errors
from app.services import tenant_audit
from app.services.bookings import BookingNotFoundError, get_for_update, lines_of, lock_property
from app.services.guest_id_reads import ENTITY, IdentityScope, guests_of, locked_guest
from app.services.id_reader import IdReader, ReadFields
from app.services.id_validation import IdFields, problems
from app.services.stay_status import NOT_ACTIVE
from app.tenancy.business_settings import PropertySettings, resolve_property_settings
from app.tenancy.context import TenantContext

log = logging.getLogger(__name__)

SCAN_KIND = "identity_scan"
IDENTITY = "identity"
SCAN_EXTENSION = "bin"  # the file on disk is ciphertext, not an image
BYTES_PER_MB = 1024 * 1024
UNCONFIRMED_SCAN_DAYS = 1  # a photo nobody confirms is deleted the next day
REGISTERED = "registered"
MAX_UNCONFIRMED_SCANS = 20  # photos one person may leave unconfirmed in a day


@dataclass(frozen=True)
class ScanStored:
    scan_id: UUID
    reader: IdReader
    fields: ReadFields


# ---- scanning ---------------------------------------------------------------------------


def _check_image(content: bytes, settings: PropertySettings) -> str:
    """The image's real content type, or a named refusal."""
    if not content:
        raise errors.EmptyImageError
    if len(content) > settings.id_max_upload_mb * BYTES_PER_MB:
        raise errors.ImageTooLargeError
    image = detect_image_type(content)
    if image is None:
        raise errors.NotAnImageError
    return image.content_type


async def _open_booking(
    session: AsyncSession, context: TenantContext, prop: Property, booking_id: UUID
) -> Reservation:
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
    if booking.status in NOT_ACTIVE:
        raise errors.StayClosedError
    return booking


async def _unconfirmed_scans(scope: IdentityScope, since: dt.datetime) -> int:
    attached = select(GuestDocument.scan_document_id).where(
        col(GuestDocument.tenant_id) == scope.context.tenant_id,
        col(GuestDocument.scan_document_id).is_not(None),
    )
    count = await scope.session.exec(
        select(func.count())
        .select_from(Document)
        .where(
            col(Document.tenant_id) == scope.context.tenant_id,
            col(Document.kind) == SCAN_KIND,
            col(Document.uploaded_by) == str(scope.context.user_id),
            col(Document.purged_at).is_(None),
            col(Document.created_at) >= since,
            col(Document.id).not_in(attached),
        )
    )
    return count.one()


async def store_scan(
    scope: IdentityScope,
    storage: DocumentStorage,
    reader: IdReader,
    booking_id: UUID,
    doc_type: str,
    content: bytes,
) -> ScanStored:
    """Encrypt and keep the photo, and let the reader suggest fields. Commits."""
    session, context, prop = scope.session, scope.context, scope.prop
    await _open_booking(session, context, prop, booking_id)
    content_type = _check_image(content, resolve_property_settings(prop.settings))
    now = dt.datetime.now(dt.UTC)
    if await _unconfirmed_scans(scope, now - dt.timedelta(days=1)) >= MAX_UNCONFIRMED_SCANS:
        raise errors.TooManyScansError
    property_id, today = prop.id, dates_of.property_today(prop.timezone)
    await session.commit()  # no transaction stays open while the reader and disk work
    fields = await reader.read(doc_type, content, today)
    document = Document(
        tenant_id=context.tenant_id,
        property_id=property_id,
        kind=SCAN_KIND,
        classification=IDENTITY,
        storage_key="",
        content_type=content_type,
        size_bytes=len(content),
        retention_until=today + dt.timedelta(days=UNCONFIRMED_SCAN_DAYS),
        uploaded_by=str(context.user_id),
    )
    sealed = scope.cipher.encrypt_file(context.tenant_id, document.id, content)
    document.storage_key = await storage.save(context.tenant_id, sealed, SCAN_EXTENSION)
    try:
        session.add(document)
        await session.commit()
    except Exception:
        await session.rollback()
        await storage.delete(context.tenant_id, document.storage_key)
        raise
    return ScanStored(scan_id=document.id, reader=reader, fields=fields)


# ---- confirming -------------------------------------------------------------------------


def fields_of(request: ConfirmIdRequest) -> IdFields:
    return IdFields(
        doc_type=request.doc_type,
        number=request.number,
        full_name=request.full_name,
        birth_date=request.birth_date,
        gender=request.gender,
        nationality=request.nationality or ("ID" if request.doc_type == "ktp" else None),
        expires_on=request.expires_on,
        visa_type=request.visa_type,
        entry_date=request.entry_date,
    )


async def _locked_booking(
    scope: IdentityScope, booking_id: UUID
) -> tuple[Reservation, list[ReservationUnit]]:
    await lock_property(scope.session, scope.context, scope.prop.id)
    try:
        booking = await get_for_update(scope.session, scope.context, scope.prop.id, booking_id)
    except BookingNotFoundError:
        raise errors.DocumentNotFoundError from None
    if booking.status in NOT_ACTIVE:
        raise errors.StayClosedError
    return booking, await lines_of(scope.session, scope.context, [booking.id])


async def _documents_with_hash(
    scope: IdentityScope, doc_type: str, digest: str
) -> list[GuestDocument]:
    rows = await scope.session.exec(
        select(GuestDocument).where(
            col(GuestDocument.tenant_id) == scope.context.tenant_id,
            col(GuestDocument.doc_type) == doc_type,
            col(GuestDocument.doc_number_hash) == digest,
        )
    )
    return list(rows.all())


async def _existing_document(
    scope: IdentityScope, guest_id: UUID, doc_type: str
) -> GuestDocument | None:
    """The guest's document of this type, locked and read fresh (the purge may touch it)."""
    return (
        await scope.session.exec(
            select(GuestDocument)
            .where(
                col(GuestDocument.tenant_id) == scope.context.tenant_id,
                col(GuestDocument.guest_id) == guest_id,
                col(GuestDocument.doc_type) == doc_type,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).first()


def _capacity(booking: Reservation) -> int:
    """How many people the booking is for: the most guests it can list."""
    return max(booking.adults + booking.children, 1)


async def _target_guest(
    scope: IdentityScope,
    booking: Reservation,
    on_booking: list[tuple[Guest, bool]],
    lines: list[ReservationUnit],
    guest_id: UUID | None,
) -> tuple[Guest, bool]:
    """(guest whose ID this is, is the main guest). A new guest when `guest_id` is None.

    A number is never used to pull in another profile: that would let anyone who knows
    a number see that person's details and photo.
    """
    ids = {guest.id: is_main for guest, is_main in on_booking}
    if guest_id is not None:
        if guest_id not in ids:
            raise errors.GuestNotOnBookingError
        return await locked_guest(scope.session, scope.context, guest_id), ids[guest_id]
    if len(ids) >= _capacity(booking):
        raise errors.TooManyGuestsError
    guest = Guest(tenant_id=scope.context.tenant_id, full_name="-")
    scope.session.add(guest)
    await scope.session.flush()
    scope.session.add(
        ReservationGuest(
            tenant_id=scope.context.tenant_id,
            reservation_unit_id=lines[0].id,
            guest_id=guest.id,
            registration_status=REGISTERED,
            created_by=str(scope.context.user_id),
        )
    )
    return guest, False


async def _usable_scan(scope: IdentityScope, scan_id: UUID, keep_for: UUID | None) -> Document:
    """A photo this staff member uploaded here, not yet deleted or used for another ID."""
    scan = (
        await scope.session.exec(
            select(Document)
            .where(
                col(Document.tenant_id) == scope.context.tenant_id,
                col(Document.id) == scan_id,
                col(Document.kind) == SCAN_KIND,
                col(Document.property_id) == scope.prop.id,
                col(Document.uploaded_by) == str(scope.context.user_id),
                col(Document.purged_at).is_(None),
            )
            .with_for_update()
        )
    ).first()
    if scan is None:
        raise errors.ScanNotUsableError
    taken = await scope.session.exec(
        select(GuestDocument.id).where(
            col(GuestDocument.tenant_id) == scope.context.tenant_id,
            col(GuestDocument.scan_document_id) == scan_id,
        )
    )
    if any(found != keep_for for found in taken.all()):
        raise errors.ScanNotUsableError
    return scan


def _copy_to_profile(guest: Guest, fields: IdFields, user: str) -> None:
    guest.full_name = fields.full_name.strip()
    guest.nationality = fields.nationality or guest.nationality
    guest.birth_date = fields.birth_date or guest.birth_date
    guest.gender = fields.gender or guest.gender
    guest.updated_by = user


@dataclass(frozen=True)
class _Kept:
    """Until when the number and the image of a document are kept."""

    number_until: dt.date
    image_until: dt.date


def _kept(booking: Reservation, today: dt.date, settings: PropertySettings) -> _Kept:
    end = max(booking.departure_date, today)
    return _Kept(
        number_until=end + dt.timedelta(days=settings.id_number_retention_days),
        image_until=end + dt.timedelta(days=settings.id_image_retention_days),
    )


async def _write_document(
    scope: IdentityScope,
    guest: Guest,
    fields: IdFields,
    existing: GuestDocument | None,
    kept: _Kept,
) -> GuestDocument:
    """Create the guest's document of this type, or replace what it says. Flushed."""
    tenant_id, user = scope.context.tenant_id, str(scope.context.user_id)
    number = fields.clean_number
    document = existing or GuestDocument(
        tenant_id=tenant_id, guest_id=guest.id, doc_type=fields.doc_type, created_by=user
    )
    document.doc_number_encrypted = scope.cipher.encrypt_number(tenant_id, document.id, number)
    document.doc_number_hash = scope.cipher.number_hash(tenant_id, fields.doc_type, number)
    document.doc_number_last4 = number[-4:]
    document.issuing_country = fields.nationality
    document.expires_on = fields.expires_on if fields.doc_type == "passport" else None
    document.visa_type = fields.visa_type if fields.is_foreign else None
    document.entry_stamp_date = fields.entry_date if fields.is_foreign else None
    document.verified_at = dt.datetime.now(dt.UTC)
    document.verified_by = user
    document.extracted_by_ai = False
    document.retention_until = max(document.retention_until or kept.number_until, kept.number_until)
    document.updated_by = user
    scope.session.add(document)
    await scope.session.flush()
    return document


async def _retire_scan(scope: IdentityScope, scan_id: UUID | None, today: dt.date) -> None:
    """A replaced photo is deleted at the next purge."""
    old = await scope.session.get(Document, scan_id) if scan_id else None
    if old is not None and old.purged_at is None:
        old.retention_until = today - dt.timedelta(days=1)
        scope.session.add(old)


async def _attach_scan(
    scope: IdentityScope,
    document: GuestDocument,
    scan_id: UUID | None,
    kept: _Kept,
    today: dt.date,
    number_changed: bool,
) -> None:
    """Link the new photo, retire a replaced one, and keep the photo for this stay."""
    if scan_id is not None and scan_id != document.scan_document_id:
        scan = await _usable_scan(scope, scan_id, document.id)
        await _retire_scan(scope, document.scan_document_id, today)
        document.scan_document_id = scan.id
    elif scan_id is None and number_changed:
        await _retire_scan(scope, document.scan_document_id, today)  # it shows another number
        document.scan_document_id = None
    current = (
        await scope.session.get(Document, document.scan_document_id)
        if document.scan_document_id
        else None
    )
    if current is not None:
        current.retention_until = max(current.retention_until or kept.image_until, kept.image_until)
        scope.session.add(current)
    scope.session.add(document)


async def _mark_main_registered(
    scope: IdentityScope, lines: list[ReservationUnit], guest: Guest
) -> None:
    """The first room's primary guest is this guest, registered."""
    user = str(scope.context.user_id)
    rows = await scope.session.exec(
        select(ReservationGuest).where(
            col(ReservationGuest.tenant_id) == scope.context.tenant_id,
            col(ReservationGuest.reservation_unit_id) == lines[0].id,
            col(ReservationGuest.is_primary).is_(True)
            | (col(ReservationGuest.guest_id) == guest.id),
        )
    )
    mine = None
    for row in rows.all():
        if row.guest_id == guest.id:
            mine = row
        elif row.is_primary:
            row.is_primary, row.updated_by = False, user
            scope.session.add(row)
    await scope.session.flush()  # only one primary per room at any moment
    mine = mine or ReservationGuest(
        tenant_id=scope.context.tenant_id,
        reservation_unit_id=lines[0].id,
        guest_id=guest.id,
        created_by=user,
    )
    mine.is_primary, mine.registration_status, mine.updated_by = True, REGISTERED, user
    scope.session.add(mine)


def _check_number_free(
    on_booking: list[tuple[Guest, bool]], guest: Guest, seen: list[GuestDocument]
) -> None:
    """Two people on one booking cannot hold the same document."""
    others = {g.id for g, _ in on_booking} - {guest.id}
    if any(document.guest_id in others for document in seen):
        raise errors.NumberOnOtherGuestError


async def confirm(
    scope: IdentityScope, booking_id: UUID, request: ConfirmIdRequest, simulated: bool
) -> UUID:
    """Save the fields staff checked. Returns the document id. Commits."""
    today = dates_of.property_today(scope.prop.timezone)
    fields = fields_of(request)
    found = problems(fields, today)
    if found:
        raise errors.InvalidIdError(found)
    booking, lines = await _locked_booking(scope, booking_id)
    on_booking = await guests_of(scope.session, scope.context, booking, lines)
    guest, is_main = await _target_guest(scope, booking, on_booking, lines, request.guest_id)
    digest = scope.cipher.number_hash(scope.context.tenant_id, fields.doc_type, fields.clean_number)
    seen = await _documents_with_hash(scope, fields.doc_type, digest)
    _check_number_free(on_booking, guest, seen)
    existing = await _existing_document(scope, guest.id, fields.doc_type)
    number_changed = existing is not None and existing.doc_number_hash != digest
    _copy_to_profile(guest, fields, str(scope.context.user_id))
    scope.session.add(guest)
    kept = _kept(booking, today, resolve_property_settings(scope.prop.settings))
    try:
        document = await _write_document(scope, guest, fields, existing, kept)
    except IntegrityError:  # the same guest confirmed at the same moment elsewhere
        await scope.session.rollback()
        raise errors.TryAgainError from None
    await _attach_scan(scope, document, request.scan_id, kept, today, number_changed)
    if is_main:
        await _mark_main_registered(scope, lines, guest)
    await tenant_audit.record(
        scope.session,
        scope.context,
        "guestid.confirmed",
        property_id=booking.property_id,
        entity_table=ENTITY,
        entity_id=booking.id,
        payload={
            "guest_id": str(guest.id),
            "document_id": str(document.id),
            "doc_type": fields.doc_type,
            "main_guest": is_main,
            "replaced_number": number_changed,
            "seen_on_another_profile": any(d.guest_id != guest.id for d in seen),
            "with_image": document.scan_document_id is not None,
            "simulated_reader": simulated and request.scan_id is not None,
        },
    )
    await scope.session.commit()
    log.info("guest id confirmed booking=%s document=%s", booking.id, document.id)
    return document.id


# ---- removing ---------------------------------------------------------------------------


async def remove_guest(scope: IdentityScope, booking_id: UUID, guest_id: UUID) -> None:
    """Take a companion off the booking. Their ID record stays on their profile. Commits."""
    booking, lines = await _locked_booking(scope, booking_id)
    if guest_id == booking.booker_guest_id:
        raise errors.MainGuestRemovalError
    links = (
        await scope.session.exec(
            select(ReservationGuest).where(
                col(ReservationGuest.tenant_id) == scope.context.tenant_id,
                col(ReservationGuest.reservation_unit_id).in_([line.id for line in lines]),
                col(ReservationGuest.guest_id) == guest_id,
                col(ReservationGuest.is_primary).is_(False),
            )
        )
    ).all()
    if not links:
        raise errors.GuestNotOnBookingError
    for link in links:
        await scope.session.delete(link)
    await tenant_audit.record(
        scope.session,
        scope.context,
        "guestid.guest_removed",
        property_id=booking.property_id,
        entity_table=ENTITY,
        entity_id=booking.id,
        payload={"guest_id": str(guest_id)},
    )
    await scope.session.commit()
