"""Rate plan routes.

GET   /api/rate-plans
POST  /api/rate-plans
PATCH /api/rate-plans/{id}
"""

from collections.abc import Awaitable, Callable
from typing import TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.schemas.rate_plans import RatePlanCreateRequest, RatePlanRead, RatePlanUpdateRequest
from app.services import rate_plans as plans
from app.services.payment_links import format_rupiah
from app.services.workspace import find_property
from app.tenancy.context import TenantContext, get_tenant_context
from app.tenancy.session import get_tenant_session

rate_plans_router = APIRouter(prefix="/api/rate-plans", tags=["rate-plans"])

NOT_FOUND = "Rate plan not found"
T = TypeVar("T")


def rate_out_of_range(exc: plans.RateOutOfRangeError) -> HTTPException:
    """The HTTP answer for a price outside the property's range (shared with the calendar)."""
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=(
            f"A nightly price must be between {format_rupiah(exc.minimum)} "
            f"and {format_rupiah(exc.maximum)}."
        ),
    )


async def _guarded(call: Callable[[], Awaitable[T]]) -> T:
    """Run a rate-plan service call, turning its domain errors into HTTP answers."""
    try:
        return await call()
    except plans.RatePlanNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND) from None
    except plans.RatePlanNameTakenError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A rate plan with this name already exists.",
        ) from None
    except plans.RatePlanLimitError as exc:
        noun = "rate plan" if exc.limit == 1 else "rate plans"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A property can have at most {exc.limit} {noun} in use.",
        ) from None
    except plans.TooManySwitchedOffError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Too many switched-off rate plans. Switch one back on and change it instead.",
        ) from None
    except plans.UnknownRoomTypeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A price is for a room type that does not exist or is switched off.",
        ) from None
    except plans.RateOutOfRangeError as exc:
        raise rate_out_of_range(exc) from None


@rate_plans_router.get("", response_model=list[RatePlanRead])
async def list_rate_plans(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> list[RatePlanRead]:
    prop = await find_property(session, context)
    return await plans.list_rate_plans(session, context, prop.id)


@rate_plans_router.post("", response_model=RatePlanRead, status_code=status.HTTP_201_CREATED)
async def create_rate_plan(
    body: RatePlanCreateRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> RatePlanRead:
    prop = await find_property(session, context)
    return await _guarded(lambda: plans.create_rate_plan(session, context, prop, body))


@rate_plans_router.patch("/{rate_plan_id}", response_model=RatePlanRead)
async def update_rate_plan(
    rate_plan_id: UUID,
    body: RatePlanUpdateRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> RatePlanRead:
    prop = await find_property(session, context)
    return await _guarded(
        lambda: plans.update_rate_plan(session, context, prop, rate_plan_id, body)
    )
