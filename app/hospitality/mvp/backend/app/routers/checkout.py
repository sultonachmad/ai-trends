"""Public pay page routes — no sign-in; the link token in the path is the credential.

GET  /api/pay/{token}             what the page shows
POST /api/pay/{token}/payments    choose a method, get payment instructions

An unknown, malformed or foreign token always answers the same 404.
"""

from collections.abc import Awaitable, Callable
from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.payment_links import PaymentInstructions, PublicPaymentLink, StartPaymentRequest
from app.services import checkout
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
