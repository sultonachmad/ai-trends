"""Payment link routes — staff side.

POST /api/payment-links                 create (and send to a conversation)
GET  /api/payment-links?state=&limit=&cursor=
GET  /api/payment-links/{id}
POST /api/payment-links/{id}/cancel
"""

from collections.abc import Awaitable, Callable
from typing import TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.schemas.payment_links import (
    LinkFilter,
    PaymentLinkCreated,
    PaymentLinkCreateRequest,
    PaymentLinkPage,
    PaymentLinkRead,
)
from app.services import payment_links as links
from app.services.link_quota import PaymentLinkLimitReachedError
from app.services.workspace import find_property
from app.tenancy.context import TenantContext, get_tenant_context
from app.tenancy.session import get_tenant_session

payment_links_router = APIRouter(prefix="/api/payment-links", tags=["payment-links"])

NOT_FOUND = "Payment link not found"
NO_LINKS_IN_PLAN = "Payment links are not part of your plan."
T = TypeVar("T")


def _limit_message(exc: PaymentLinkLimitReachedError) -> str:
    if exc.quota.limit == 0:
        return NO_LINKS_IN_PLAN
    return (
        f"This month's limit of {exc.quota.limit} payment links is reached. "
        f"New links can be created again on {exc.quota.resets_on.isoformat()}."
    )


async def _guarded(call: Callable[[], Awaitable[T]]) -> T:
    """Run a payment-link service call, turning its domain errors into HTTP answers."""
    try:
        return await call()
    except links.PaymentLinkNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND) from None
    except links.LinkConversationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        ) from None
    except links.AmountOutOfRangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Amount must be between {links.format_rupiah(exc.minimum)} "
                f"and {links.format_rupiah(exc.maximum)}."
            ),
        ) from None
    except links.TotalBelowAmountError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The total must not be smaller than the amount to pay now.",
        ) from None
    except links.LinkNotPendingError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This link is {exc.state} and can no longer be cancelled.",
        ) from None
    except PaymentLinkLimitReachedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=_limit_message(exc)
        ) from None
    except links.InvalidCursorError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid cursor"
        ) from None


@payment_links_router.post(
    "", response_model=PaymentLinkCreated, status_code=status.HTTP_201_CREATED
)
async def create_payment_link(
    body: PaymentLinkCreateRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> PaymentLinkCreated:
    prop = await find_property(session, context)
    return await _guarded(lambda: links.create_link(session, context, prop, body))


@payment_links_router.get("", response_model=PaymentLinkPage)
async def list_payment_links(
    state: LinkFilter = Query(default="all"),
    limit: int = Query(default=links.DEFAULT_PAGE_SIZE, ge=1, le=links.MAX_PAGE_SIZE),
    cursor: str | None = Query(default=None, max_length=100),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> PaymentLinkPage:
    prop = await find_property(session, context)
    return await _guarded(lambda: links.list_links(session, context, prop.id, state, limit, cursor))


@payment_links_router.get("/{link_id}", response_model=PaymentLinkRead)
async def read_payment_link(
    link_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> PaymentLinkRead:
    prop = await find_property(session, context)
    return await _guarded(lambda: links.read_link(session, context, prop.id, link_id))


@payment_links_router.post("/{link_id}/cancel", response_model=PaymentLinkRead)
async def cancel_payment_link(
    link_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> PaymentLinkRead:
    prop = await find_property(session, context)
    return await _guarded(lambda: links.cancel_link(session, context, prop.id, link_id))
