"""Simulated agency routes — development and test only.

POST /api/simulator/channels/listings     list the property on the simulated agency
GET  /api/simulator/channels/listings

Answers 404 unless PREFAB_CHANNEL_SIMULATOR_ENABLED is on.
"""

import datetime as dt
import logging
from typing import Literal, Self

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import settings
from app.rbac.dependencies import require_permission
from app.schemas.calendar_links import SimulatedCalendarRead, SimulatedCalendarRequest
from app.schemas.channels import ChannelRoomRead
from app.services import channel_test_listings as listings
from app.services.workspace import find_property
from app.tenancy.context import TenantContext, get_tenant_context
from app.tenancy.session import get_tenant_session

VIEW = require_permission("channels:view", "See connected sales channels")

EDIT = require_permission("channels:edit", "Connect and manage sales channels")

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
    _view=VIEW,
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
    _edit=EDIT,
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


@channel_simulator_router.post("/listings/{hotel_id}/fail-next/{pushes}")
async def fail_next_pushes(
    hotel_id: str,
    pushes: int,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit: dict = EDIT,
) -> dict:
    """Make the simulated agency refuse its next `pushes` pushes (development and test)."""
    from app.channels.provider import UnknownChannelPropertyError
    from app.channels.simulator import set_fail_next

    try:
        await set_fail_next(session, context.tenant_id, hotel_id, pushes)
    except UnknownChannelPropertyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found") from None
    return {"hotel_id": hotel_id, "fail_next": pushes}


MAX_AGENCY_NIGHTS = 60
CollectModel = Literal["property", "channel", "mixed"]


class AgencyBookingRequest(BaseModel):
    """A booking to place on the simulated agency (development and test only)."""

    model_config = ConfigDict(extra="forbid")

    hotel_id: str
    external_room_id: str = "R1"
    external_rate_id: str = "P1"
    arrival: dt.date
    departure: dt.date
    total_amount: int = Field(gt=0)
    guest_name: str = "Tamu Kanal"
    guest_phone: str | None = None
    units: int = Field(default=1, ge=1, le=20)
    payment_collect: CollectModel = "channel"

    @model_validator(mode="after")
    def _stayable(self) -> Self:
        nights = (self.departure - self.arrival).days
        if nights < 1:
            raise ValueError("departure must be after arrival")
        if nights > MAX_AGENCY_NIGHTS:
            raise ValueError(f"a stay can cover at most {MAX_AGENCY_NIGHTS} nights")
        return self


class AgencyBookingChangeRequest(AgencyBookingRequest):
    external_booking_id: str
    version: int = Field(ge=2)
    kind: Literal["modify", "cancel"] | None = None  # omitted: derived from dates


@channel_simulator_router.post("/listings/bookings", status_code=status.HTTP_201_CREATED)
async def place_agency_booking(
    body: AgencyBookingRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit: dict = EDIT,
) -> dict:
    """Place a new booking on the agency, as a guest booking there would."""
    from app.channels import simulator

    event = simulator.make_booking_event(
        external_room_id=body.external_room_id,
        external_rate_id=body.external_rate_id,
        arrival=body.arrival.isoformat(),
        departure=body.departure.isoformat(),
        total_amount=body.total_amount,
        guest_name=body.guest_name,
        guest_phone=body.guest_phone,
        units=body.units,
        payment_collect=body.payment_collect,
    )
    await simulator.add_booking(session, context.tenant_id, body.hotel_id, event)
    return {"external_booking_id": event.external_booking_id, "version": event.version}


@channel_simulator_router.post("/listings/bookings/change", status_code=status.HTTP_201_CREATED)
async def change_agency_booking(
    body: AgencyBookingChangeRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit: dict = EDIT,
) -> dict:
    """Deliver a new version of an agency booking (a modification or a cancellation)."""
    from app.channels import simulator

    kind = body.kind or ("cancel" if body.arrival == body.departure else "modify")
    event = simulator.make_booking_event(
        external_booking_id=body.external_booking_id,
        version=body.version,
        kind=kind,
        external_room_id=body.external_room_id,
        external_rate_id=body.external_rate_id,
        arrival=body.arrival.isoformat(),
        departure=body.departure.isoformat(),
        total_amount=body.total_amount,
        guest_name=body.guest_name,
        guest_phone=body.guest_phone,
        units=body.units,
        payment_collect=body.payment_collect,
    )
    await simulator.add_booking(session, context.tenant_id, body.hotel_id, event)
    return {
        "external_booking_id": event.external_booking_id,
        "version": event.version,
        "kind": kind,
    }


@channel_simulator_router.put("/listings/{hotel_id}/calendar", response_model=SimulatedCalendarRead)
async def set_test_calendar(
    hotel_id: str,
    body: SimulatedCalendarRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    _edit: dict = EDIT,
) -> SimulatedCalendarRead:
    """What this test site's calendar shows, and the link to paste (development only)."""
    from app.channels.simulator import find_listing
    from app.services.calendar_link_sync import simulated_url

    listing = await find_listing(session, context.tenant_id, hotel_id)
    if listing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    listing.calendar = {
        "busy": sorted(day.isoformat() for day in body.busy),
        "broken": body.broken,
    }
    session.add(listing)
    await session.commit()
    return SimulatedCalendarRead(url=simulated_url(hotel_id))
