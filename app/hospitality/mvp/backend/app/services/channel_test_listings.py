"""Test listings on the simulated agency (development and test only).

A tester presses "Create a test listing" and gets what an agency would give a real
property: a property ID, and the agency's own rooms and rates. Connecting then works as
it would with a real agency.
"""

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.channels.simulator import find_listing, listing_rooms, new_hotel_id
from app.models.tenant import ChannelSimulatorListing, Property
from app.services.rate_plans import find_base_prices, find_rate_plans
from app.services.room_types import find_room_types
from app.tenancy.context import TenantContext

MAX_LISTINGS_PER_PROPERTY = 20
ID_ATTEMPTS = 5


class TooManyTestListingsError(Exception):
    """Enough test listings already; nothing more is created."""


async def list_test_listings(
    session: AsyncSession, context: TenantContext, prop: Property
) -> list[ChannelSimulatorListing]:
    rows = await session.exec(
        select(ChannelSimulatorListing)
        .where(
            col(ChannelSimulatorListing.tenant_id) == context.tenant_id,
            col(ChannelSimulatorListing.property_id) == prop.id,
        )
        .order_by(col(ChannelSimulatorListing.created_at).desc())
    )
    return list(rows.all())


async def create_test_listing(
    session: AsyncSession, context: TenantContext, prop: Property
) -> ChannelSimulatorListing:
    """List the property on the simulated agency from its rooms and rate plans. Commits."""
    await session.exec(
        select(col(Property.id))
        .where(col(Property.tenant_id) == context.tenant_id, col(Property.id) == prop.id)
        .with_for_update()
    )  # two listings made at once must not both pass the cap
    if len(await list_test_listings(session, context, prop)) >= MAX_LISTINGS_PER_PROPERTY:
        raise TooManyTestListingsError
    rooms = await find_room_types(session, context, prop.id, active_only=True)
    plans = await find_rate_plans(session, context, prop.id, active_only=True)
    links = await find_base_prices(session, context, [plan.id for plan in plans])
    sold_on = {
        room.id: {link.rate_plan_id for link in links if link.unit_type_id == room.id}
        for room in rooms
    }
    # The plans arrive in the property's own order, so the agency's rate list per room is
    # the same whichever way the unordered link query happens to return.
    described = [
        (
            room.name,
            room.max_occupancy,
            [plan.name for plan in plans if plan.id in sold_on.get(room.id, set())],
        )
        for room in rooms
    ]
    hotel_id = new_hotel_id()
    for _ in range(ID_ATTEMPTS):
        if await find_listing(session, context.tenant_id, hotel_id) is None:
            break
        hotel_id = new_hotel_id()
    listing = ChannelSimulatorListing(
        tenant_id=context.tenant_id,
        property_id=prop.id,
        hotel_id=hotel_id,
        name=f"{prop.name} (agency listing)",
        rooms=listing_rooms(described),
    )
    session.add(listing)
    await session.commit()
    await session.refresh(listing)
    return listing
