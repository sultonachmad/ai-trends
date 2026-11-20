"""WhatsApp simulator — a signed-in tester sends a message in "as a guest".

POST /api/simulator/whatsapp/inbound

Development only. Every request answers 404 unless
PREFAB_MESSAGING_SIMULATOR_ENABLED is true. The message always goes to the
caller's own property, through the same `receive_inbound` a real provider
webhook will use.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import settings
from app.messaging.phone import InvalidPhoneError, normalise_phone
from app.schemas.inbox import InboundResult, SimulatedInboundRequest
from app.services.inbound import InboundMessage, receive_inbound
from app.services.messaging_accounts import get_or_create_whatsapp_account
from app.services.workspace import find_property
from app.tenancy.context import TenantContext, get_tenant_context
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
