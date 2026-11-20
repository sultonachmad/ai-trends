"""Simulated agency routes — development and test only.

POST /api/simulator/channels/listings     list the property on the simulated agency
GET  /api/simulator/channels/listings

Answers 404 unless PREFAB_CHANNEL_SIMULATOR_ENABLED is on.
"""

import datetime as dt
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import settings
from app.schemas.channels import ChannelRoomRead
from app.services import channel_test_listings as listings
from app.services.workspace import find_property
from app.tenancy.context import TenantContext, get_tenant_context
from app.tenancy.session import get_tenant_session

log = logging.getLogger(__name__)

if settings.CHANNEL_SIMULATOR_ENABLED:
    log.warning(
        "Channel SIMULATOR is ENABLED (PREFAB_CHANNEL_SIMULATOR_ENABLED): a simulated agency "
        "can be connected. Development only — it sells nothing to real guests."
    )


def require_channel_simulator_enabled() -> None:
    if not settings.CHANNEL_SIMULATOR_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


channel_simulator_router = APIRouter(
    prefix="/api/simulator/channels",
    tags=["simulator"],
    dependencies=[Depends(require_channel_simulator_enabled)],
)


class TestListingRead(BaseModel):
    hotel_id: str
    name: str
    rooms: list[ChannelRoomRead]
    created_at: dt.datetime


@channel_simulator_router.get("/listings", response_model=list[TestListingRead])
async def list_test_listings(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> list[TestListingRead]:
    prop = await find_property(session, context)
    found = await listings.list_test_listings(session, context, prop)
    return [TestListingRead.model_validate(item, from_attributes=True) for item in found]


@channel_simulator_router.post(
    "/listings", response_model=TestListingRead, status_code=status.HTTP_201_CREATED
)
async def create_test_listing(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> TestListingRead:
    prop = await find_property(session, context)
    try:
        listing = await listings.create_test_listing(session, context, prop)
    except listings.TooManyTestListingsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This property already has enough test listings.",
        ) from None
    return TestListingRead.model_validate(listing, from_attributes=True)
