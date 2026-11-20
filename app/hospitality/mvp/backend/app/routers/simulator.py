"""Simulators — play the outside world while providers are simulated.

POST /api/simulator/whatsapp/inbound     a signed-in tester writes in "as a guest"
POST /api/simulator/payments/{token}/pay  the holder of a pay link "pays" it

Development only. Each answers 404 unless its switch is true
(PREFAB_MESSAGING_SIMULATOR_ENABLED / PREFAB_PAYMENT_SIMULATOR_ENABLED).

A simulated guest message always goes to the caller's own property, through the same
`receive_inbound` a real provider webhook will use.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import settings
from app.messaging.phone import InvalidPhoneError, normalise_phone
from app.routers.checkout import guarded as checkout_guarded
from app.schemas.inbox import InboundResult, SimulatedInboundRequest
from app.schemas.payment_links import PublicPaymentLink, SimulatePaymentRequest
from app.services import checkout
from app.services.gateway_events import PAID_EVENT, GatewayEvent, handle_gateway_event
from app.services.inbound import InboundMessage, receive_inbound
from app.services.messaging_accounts import get_or_create_whatsapp_account
from app.services.workspace import find_property
from app.tenancy.context import TenantContext, get_tenant_context
from app.tenancy.public import PublicLinkScope, get_public_link_scope
from app.tenancy.session import get_tenant_session

log = logging.getLogger(__name__)

if settings.MESSAGING_SIMULATOR_ENABLED:
    log.warning(
        "WhatsApp SIMULATOR is ENABLED (PREFAB_MESSAGING_SIMULATOR_ENABLED): any signed-in "
        "member can create guest messages. Development only — never enable with real guests."
    )


def require_simulator_enabled() -> None:
    if not settings.MESSAGING_SIMULATOR_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


simulator_router = APIRouter(
    prefix="/api/simulator",
    tags=["simulator"],
    dependencies=[Depends(require_simulator_enabled)],
)


@simulator_router.post(
    "/whatsapp/inbound", response_model=InboundResult, status_code=status.HTTP_201_CREATED
)
async def simulate_inbound(
    body: SimulatedInboundRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> InboundResult:
    try:
        phone = normalise_phone(body.from_phone)
    except InvalidPhoneError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from None
    prop = await find_property(session, context)
    account = await get_or_create_whatsapp_account(session, prop)
    outcome = await receive_inbound(
        session,
        account,
        InboundMessage(
            from_phone=phone,
            body=body.body,
            guest_name=body.guest_name,
            provider_message_id=f"sim-in-{uuid.uuid4().hex}",
        ),
    )
    return InboundResult(
        conversation_id=outcome.conversation_id,
        message_id=outcome.message_id,
        duplicate=outcome.duplicate,
    )


# ---- payments ------------------------------------------------------------------------

if settings.PAYMENT_SIMULATOR_ENABLED:
    log.warning(
        "Payment SIMULATOR is ENABLED (PREFAB_PAYMENT_SIMULATOR_ENABLED): anyone holding a "
        "pay link can mark it paid. Development only — never enable where money is taken."
    )


def require_payment_simulator_enabled() -> None:
    if not settings.PAYMENT_SIMULATOR_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


payment_simulator_router = APIRouter(
    prefix="/api/simulator/payments",
    tags=["simulator"],
    dependencies=[Depends(require_payment_simulator_enabled)],
)


@payment_simulator_router.post("/{token}/pay", response_model=PublicPaymentLink)
async def simulate_payment(
    body: SimulatePaymentRequest | None = None,
    scope: PublicLinkScope = Depends(get_public_link_scope),
) -> PublicPaymentLink:
    """Play the guest's banking app: report the open payment attempt as paid.

    Public like the pay page itself (the token is the credential). Goes through the
    same `handle_gateway_event` a real gateway webhook will use.
    """
    payment, account_id = await checkout_guarded(
        lambda: checkout.payment_awaiting_simulation(scope, body.reference if body else None)
    )
    await handle_gateway_event(
        scope.session,
        scope.tenant_id,
        account_id,
        GatewayEvent(
            gateway_event_id=f"sim-evt-{uuid.uuid4().hex}",
            event_type=PAID_EVENT,
            gateway_reference=payment.gateway_reference or "",
            amount=payment.amount,
            signature_valid=True,
            raw={"simulated": True, "reference": payment.gateway_reference},
        ),
    )
    return await checkout_guarded(lambda: checkout.public_view(scope))
