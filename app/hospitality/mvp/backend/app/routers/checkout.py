"""Public pay page routes — no sign-in; the link token in the path is the credential.

GET  /api/pay/{token}             what the page shows
POST /api/pay/{token}/payments    choose a method, get payment instructions
POST /api/pay/{token}/proofs      upload a manual-transfer screenshot (multipart)

An unknown, malformed or foreign token always answers the same 404.
"""

from collections.abc import Awaitable, Callable
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.documents.storage import DocumentStorage, get_document_storage
from app.routers.transfer_proofs import read_upload, upload_error
from app.schemas.payment_links import PaymentInstructions, PublicPaymentLink, StartPaymentRequest
from app.services import checkout
from app.services import transfer_proofs as proofs
from app.tenancy.public import LINK_NOT_FOUND, PublicLinkScope, get_public_link_scope

checkout_router = APIRouter(prefix="/api/pay", tags=["checkout"])

T = TypeVar("T")
NOT_PAYABLE = {
    "paid": "This payment link has already been paid.",
    "expired": "This payment link has expired. Please ask the property for a new one.",
    "cancelled": "This payment link was cancelled. Please ask the property for a new one.",
}


async def guarded(call: Callable[[], Awaitable[T]]) -> T:
    """Run a checkout service call, turning its domain errors into HTTP answers."""
    try:
        return await call()
    except checkout.PublicLinkNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=LINK_NOT_FOUND) from None
    except checkout.LinkNotPayableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=NOT_PAYABLE.get(exc.state, "This payment link can no longer be paid."),
        ) from None
    except checkout.NoOpenPaymentError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Choose a payment method first."
        ) from None
    except checkout.BankRequiredError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Choose a bank for the virtual account.",
        ) from None
    except checkout.MethodNotAllowedError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This payment method is not available for this link.",
        ) from None
    except checkout.ManualTransferUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This property does not accept manual transfers through this link.",
        ) from None
    except proofs.LinkNotOpenForProofError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=NOT_PAYABLE.get(exc.state, "This payment link can no longer be paid."),
        ) from None
    except (
        proofs.EmptyFileError,
        proofs.NotAnImageError,
        proofs.FileTooLargeError,
        proofs.TooManyProofsError,
    ) as exc:
        raise upload_error(exc) from None
    except checkout.TooManyAttemptsError:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Too many payment attempts for this link. Please ask the property for a new one."
            ),
        ) from None
    except checkout.GatewayUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Payment instructions are not available right now. Please try again.",
        ) from None


@checkout_router.get("/{token}", response_model=PublicPaymentLink)
async def read_public_link(
    scope: PublicLinkScope = Depends(get_public_link_scope),
) -> PublicPaymentLink:
    return await guarded(lambda: checkout.public_view(scope))


@checkout_router.post(
    "/{token}/payments", response_model=PaymentInstructions, status_code=status.HTTP_201_CREATED
)
async def start_payment(
    body: StartPaymentRequest,
    scope: PublicLinkScope = Depends(get_public_link_scope),
) -> PaymentInstructions:
    return await guarded(lambda: checkout.start_payment(scope, body.method, body.bank))


@checkout_router.post(
    "/{token}/proofs", response_model=PublicPaymentLink, status_code=status.HTTP_201_CREATED
)
async def upload_proof(
    file: Annotated[UploadFile, File()],
    consent: Annotated[bool, Form()],
    scope: PublicLinkScope = Depends(get_public_link_scope),
    storage: DocumentStorage = Depends(get_document_storage),
) -> PublicPaymentLink:
    """A guest uploads their transfer screenshot. They must agree to the storage notice."""
    if not consent:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Please agree to the storage notice to upload your transfer proof.",
        )
    limit_mb = await guarded(lambda: checkout.property_upload_limit_mb(scope))
    upload = await read_upload(file, limit_mb)
    return await guarded(lambda: checkout.submit_proof(scope, storage, upload))
