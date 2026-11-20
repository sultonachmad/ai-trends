"""Transfer proof routes — staff side.

GET  /api/transfer-proofs?state=awaiting|approved|rejected&limit=&cursor=
POST /api/transfer-proofs                 upload (multipart) for a link, or with no link
GET  /api/transfer-proofs/{id}
GET  /api/transfer-proofs/{id}/image      the screenshot; staff of the owning tenant only
POST /api/transfer-proofs/{id}/approve
POST /api/transfer-proofs/{id}/reject
"""

from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Annotated, TypeVar
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlmodel.ext.asyncio.session import AsyncSession

from app.documents.storage import DocumentStorage, get_document_storage
from app.rbac.dependencies import require_permission
from app.schemas.payment_links import Description, Rupiah
from app.schemas.transfer_proofs import ProofFilter, ProofPage, ProofRead, RejectRequest
from app.services import proof_review
from app.services import transfer_proofs as proofs
from app.services.payment_links import AmountOutOfRangeError, format_rupiah
from app.services.workspace import find_property
from app.tenancy.business_settings import resolve_property_settings
from app.tenancy.context import TenantContext, get_tenant_context
from app.tenancy.session import get_tenant_session

VIEW = require_permission("proofs:view", "See transfer proofs and their images")

EDIT = require_permission("proofs:edit", "Upload, approve and reject transfer proofs")

transfer_proofs_router = APIRouter(prefix="/api/transfer-proofs", tags=["transfer-proofs"])

NOT_FOUND = "Transfer proof not found"
UPLOAD_REFUSED = "This file cannot be accepted."
IMAGE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "private, no-store",
    "Content-Disposition": "inline",
    "Content-Security-Policy": "default-src 'none'; sandbox",
}
T = TypeVar("T")

_UPLOAD_ERRORS: dict[type[Exception], tuple[int, str]] = {
    proofs.EmptyFileError: (422, "The file is empty."),
    proofs.NotAnImageError: (422, "Upload a JPEG, PNG or WebP image."),
    proofs.TooManyProofsError: (
        429,
        "This link already has proofs waiting for review. Please wait for the property to check.",
    ),
}
_DECISION_ERRORS: dict[type[Exception], tuple[int, str]] = {
    proofs.SameApproverError: (
        409,
        "A different staff member must give the second approval.",
    ),
    proof_review.LinkAlreadyPaidError: (
        409,
        "This link is already paid. Reject the proof and refund the transfer.",
    ),
    proof_review.LinkCancelledError: (
        409,
        "This link was cancelled and cannot be marked paid. Reject the proof.",
    ),
}


def upload_error(exc: Exception) -> HTTPException:
    """The HTTP answer for a known upload problem, shared with the public route."""
    if isinstance(exc, proofs.FileTooLargeError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"The image must be at most {exc.limit_mb} MB.",
        )
    known = _UPLOAD_ERRORS.get(type(exc), (status.HTTP_422_UNPROCESSABLE_ENTITY, UPLOAD_REFUSED))
    return HTTPException(status_code=known[0], detail=known[1])


async def read_upload(file: UploadFile, limit_mb: int) -> proofs.ProofUpload:
    """Read at most one byte past the limit, so an oversized upload is never fully held."""
    content = await file.read(limit_mb * proofs.BYTES_PER_MB + 1)
    return proofs.ProofUpload(content=content, original_name=file.filename)


async def _guarded(call: Callable[[], Awaitable[T]]) -> T:
    """Run a transfer-proof service call, turning its domain errors into HTTP answers."""
    try:
        return await call()
    except proofs.ProofNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND) from None
    except proofs.ProofLinkNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Payment link not found"
        ) from None
    except proofs.ProofConversationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        ) from None
    except proofs.ProofImageGoneError:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This image was deleted after its retention period.",
        ) from None
    except proofs.LinkNotOpenForProofError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This link is {exc.state}; a transfer proof cannot be added to it.",
        ) from None
    except proofs.ProofAlreadyDecidedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This proof is already {exc.state}.",
        ) from None
    except AmountOutOfRangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Amount must be between {format_rupiah(exc.minimum)} "
                f"and {format_rupiah(exc.maximum)}."
            ),
        ) from None
    except proofs.InvalidCursorError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid cursor"
        ) from None
    except tuple(_UPLOAD_ERRORS) + (proofs.FileTooLargeError,) as exc:
        raise upload_error(exc) from None
    except tuple(_DECISION_ERRORS) as exc:
        code, detail = _DECISION_ERRORS[type(exc)]
        raise HTTPException(status_code=code, detail=detail) from None


@transfer_proofs_router.get("", response_model=ProofPage)
async def list_transfer_proofs(
    state: ProofFilter = Query(default="awaiting"),
    limit: int = Query(default=proofs.DEFAULT_PAGE_SIZE, ge=1, le=proofs.MAX_PAGE_SIZE),
    cursor: str | None = Query(default=None, max_length=100),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
) -> ProofPage:
    prop = await find_property(session, context)
    return await _guarded(lambda: proofs.list_proofs(session, context, prop, state, limit, cursor))


@transfer_proofs_router.post("", response_model=ProofRead, status_code=status.HTTP_201_CREATED)
async def upload_transfer_proof(
    file: Annotated[UploadFile, File()],
    payment_link_id: Annotated[UUID | None, Form()] = None,
    amount: Annotated[Rupiah | None, Form()] = None,
    description: Annotated[Description | None, Form()] = None,
    conversation_id: Annotated[UUID | None, Form()] = None,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    storage: DocumentStorage = Depends(get_document_storage),
    _edit=EDIT,
) -> ProofRead:
    """Staff upload: for a pay link, or — with amount and description — with no link."""
    for_link = payment_link_id is not None
    without_link = amount is not None and description is not None
    if for_link == without_link or (for_link and (amount is not None or description is not None)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Give either a payment link, or an amount and what it was for.",
        )
    prop = await find_property(session, context)
    upload = await read_upload(file, resolve_property_settings(prop.settings).proof_max_upload_mb)

    async def submit() -> ProofRead:
        proof = await proofs.submit_by_staff(
            session,
            storage,
            context,
            prop,
            upload,
            payment_link_id=payment_link_id,
            amount=Decimal(amount) if amount is not None else None,
            description=description,
            conversation_id=conversation_id,
        )
        return await proofs.read_one(session, proof, prop)

    return await _guarded(submit)


@transfer_proofs_router.get("/{proof_id}", response_model=ProofRead)
async def read_transfer_proof(
    proof_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _view=VIEW,
) -> ProofRead:
    prop = await find_property(session, context)

    async def read() -> ProofRead:
        proof = await proofs.get_proof(session, context, prop.id, proof_id)
        return await proofs.read_one(session, proof, prop)

    return await _guarded(read)


@transfer_proofs_router.get("/{proof_id}/image")
async def read_transfer_proof_image(
    proof_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    storage: DocumentStorage = Depends(get_document_storage),
    _view=VIEW,
) -> Response:
    prop = await find_property(session, context)
    content, content_type = await _guarded(
        lambda: proofs.read_image(session, storage, context, prop.id, proof_id)
    )
    return Response(content=content, media_type=content_type, headers=IMAGE_HEADERS)


@transfer_proofs_router.post("/{proof_id}/approve", response_model=ProofRead)
async def approve_transfer_proof(
    proof_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> ProofRead:
    prop = await find_property(session, context)

    async def decide() -> ProofRead:
        proof = await proof_review.approve(session, context, prop, proof_id)
        return await proofs.read_one(session, proof, prop)

    return await _guarded(decide)


@transfer_proofs_router.post("/{proof_id}/reject", response_model=ProofRead)
async def reject_transfer_proof(
    proof_id: UUID,
    body: RejectRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit=EDIT,
) -> ProofRead:
    prop = await find_property(session, context)

    async def decide() -> ProofRead:
        proof = await proof_review.reject(session, context, prop, proof_id, body.reason)
        return await proofs.read_one(session, proof, prop)

    return await _guarded(decide)
