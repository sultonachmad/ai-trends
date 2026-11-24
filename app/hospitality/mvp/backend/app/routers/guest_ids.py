"""Guests on a booking and their KTP or passport.

GET    /api/bookings/{id}/guests                          guests, masked IDs, ready for check-in
POST   /api/bookings/{id}/guests/scan                     photo in, suggested fields out
POST   /api/bookings/{id}/guests                          confirm checked fields
DELETE /api/bookings/{id}/guests/{guest_id}               take a companion off the booking
POST   /api/bookings/{id}/guests/documents/{doc}/reveal   full number (logged)
GET    /api/bookings/{id}/guests/documents/{doc}/image    the photo (logged)
GET    /api/bookings/{id}/guests/history                  who confirmed or looked, and when
"""

from collections.abc import Awaitable, Callable
from typing import Annotated, TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.documents.storage import DocumentStorage, get_document_storage
from app.rbac.dependencies import require_permission
from app.schemas.guest_ids import (
    BookingGuests,
    ConfirmIdRequest,
    DocType,
    IdView,
    ReaderInfo,
    ReadFieldsOut,
    RevealedNumber,
    ScanResult,
)
from app.security.identity_crypto import IdentityCipher, get_identity_cipher
from app.services import guest_id_reads as reads
from app.services import guest_ids
from app.services.guest_id_errors import GuestIdError, InvalidIdError
from app.services.id_reader import IdReader, ReadFields, get_id_reader
from app.services.workspace import find_property
from app.tenancy.business_settings import MAX_PROOF_UPLOAD_MB
from app.tenancy.context import TenantContext, get_tenant_context
from app.tenancy.session import get_tenant_session

VIEW = require_permission("guestid:view", "See who is staying and their masked ID details")

EDIT = require_permission(
    "guestid:edit", "Capture and confirm guest IDs, and show full numbers and images"
)


T = TypeVar("T")
BYTES_PER_MB = 1024 * 1024
NO_STORE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}


def _no_store(response: Response) -> None:
    """Identity data must not be kept by browsers or proxies."""
    response.headers.update(NO_STORE)


guest_ids_router = APIRouter(
    prefix="/api/bookings/{booking_id}/guests",
    tags=["guest-ids"],
    dependencies=[Depends(_no_store)],
)


async def _scope(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    cipher: IdentityCipher = Depends(get_identity_cipher),
) -> reads.IdentityScope:
    return reads.IdentityScope(
        session=session, context=context, prop=await find_property(session, context), cipher=cipher
    )


Scope = Annotated[reads.IdentityScope, Depends(_scope)]


def _refused(exc: GuestIdError) -> HTTPException:
    detail: dict = {"code": exc.code, "message": exc.message}
    if isinstance(exc, InvalidIdError):
        detail["problems"] = [{"code": p.code, "field": p.field} for p in exc.problems]
    return HTTPException(status_code=exc.status_code, detail=detail)


async def _guarded(scope: reads.IdentityScope, call: Callable[[], Awaitable[T]]) -> T:
    try:
        return await call()
    except GuestIdError as exc:
        await scope.session.rollback()
        raise _refused(exc) from None


def _reader_info(reader: IdReader) -> ReaderInfo:
    return ReaderInfo(name=reader.name, simulated=reader.simulated)


def _fields_out(fields: ReadFields) -> ReadFieldsOut:
    return ReadFieldsOut(**fields.__dict__)


async def _guests(scope: reads.IdentityScope, booking_id: UUID, reader: IdReader) -> BookingGuests:
    view = await reads.read_guests(scope, booking_id)
    return BookingGuests(
        booking_id=view.booking.id,
        status=view.booking.status,
        main_guest_ready=view.main_guest_ready,
        can_change=reads.can_change(view.booking),
        reader=_reader_info(reader),
        guests=view.guests,
    )


@guest_ids_router.get("", response_model=BookingGuests)
async def read_guests(
    booking_id: UUID, scope: Scope, reader: IdReader = Depends(get_id_reader), _view=VIEW
) -> BookingGuests:
    return await _guarded(scope, lambda: _guests(scope, booking_id, reader))


@guest_ids_router.post("/scan", response_model=ScanResult, status_code=status.HTTP_201_CREATED)
async def scan(
    booking_id: UUID,
    scope: Scope,
    file: Annotated[UploadFile, File()],
    doc_type: Annotated[DocType, Form()],
    storage: DocumentStorage = Depends(get_document_storage),
    reader: IdReader = Depends(get_id_reader),
    _edit=EDIT,
) -> ScanResult:
    content = await file.read(MAX_PROOF_UPLOAD_MB * BYTES_PER_MB + 1)

    async def run() -> ScanResult:
        stored = await guest_ids.store_scan(scope, storage, reader, booking_id, doc_type, content)
        return ScanResult(
            scan_id=stored.scan_id,
            reader=_reader_info(stored.reader),
            fields=_fields_out(stored.fields),
        )

    return await _guarded(scope, run)


@guest_ids_router.post("", response_model=BookingGuests)
async def confirm(
    booking_id: UUID,
    body: ConfirmIdRequest,
    scope: Scope,
    reader: IdReader = Depends(get_id_reader),
    _edit=EDIT,
) -> BookingGuests:
    async def run() -> BookingGuests:
        await guest_ids.confirm(scope, booking_id, body, reader.simulated)
        return await _guests(scope, booking_id, reader)

    return await _guarded(scope, run)


@guest_ids_router.delete("/{guest_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_guest(booking_id: UUID, guest_id: UUID, scope: Scope, _edit=EDIT) -> Response:
    await _guarded(scope, lambda: guest_ids.remove_guest(scope, booking_id, guest_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@guest_ids_router.post("/documents/{document_id}/reveal", response_model=RevealedNumber)
async def reveal(booking_id: UUID, document_id: UUID, scope: Scope, _edit=EDIT) -> RevealedNumber:
    number = await _guarded(scope, lambda: reads.reveal_number(scope, booking_id, document_id))
    return RevealedNumber(number=number)


@guest_ids_router.get("/documents/{document_id}/image")
async def image(
    booking_id: UUID,
    document_id: UUID,
    scope: Scope,
    storage: DocumentStorage = Depends(get_document_storage),
    _edit=EDIT,
) -> Response:
    found = await _guarded(scope, lambda: reads.read_image(scope, storage, booking_id, document_id))
    return Response(content=found.content, media_type=found.content_type, headers=NO_STORE)


@guest_ids_router.get("/history", response_model=list[IdView])
async def history(booking_id: UUID, scope: Scope, _view=VIEW) -> list[IdView]:
    return await _guarded(scope, lambda: reads.id_history(scope, booking_id))
