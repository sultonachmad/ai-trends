"""Simulated online travel agency.

It stands in for agencies that need partner certification. Its "extranet" — the
listings a tester creates — lives in `channelsimulatorlisting`. Connecting to it works
like connecting to a real agency: you need the property ID it gave the listing, and it
answers with its own room and rate IDs and names.
"""

import secrets
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.channels.provider import (
    ChannelCall,
    ChannelProperty,
    ChannelRate,
    ChannelRoom,
    UnknownChannelPropertyError,
    register_channel,
)
from app.models.tenant import ChannelSimulatorListing

SIMULATOR_CHANNEL = "simulator"
HOTEL_ID_PREFIX = "SIM-"
_HOTEL_ID_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
_HOTEL_ID_LENGTH = 6
EXTRA_ROOM_NAME = "Family Room with Balcony"
STANDARD_RATE_NAME = "Standard Rate"


def new_hotel_id() -> str:
    code = "".join(secrets.choice(_HOTEL_ID_ALPHABET) for _ in range(_HOTEL_ID_LENGTH))
    return f"{HOTEL_ID_PREFIX}{code}"


def listing_rooms(
    rooms: list[tuple[str, int, list[str]]],
) -> list[dict[str, object]]:
    """The agency's rooms for a property's `(room name, guests, rate plan names)`.

    Names are the agency's own wording, the last real room fits one guest fewer than
    ours (agencies often do), and one extra room exists only on the agency — so matching
    has something to get wrong, as it does in real life.
    """
    listed: list[dict[str, object]] = []
    rate_number = 0
    for index, (name, guests, plan_names) in enumerate(rooms, start=1):
        rates = []
        for plan_name in plan_names:
            rate_number += 1
            rates.append({"id": f"P{rate_number}", "name": f"{plan_name} — Agency Rate"})
        is_last = index == len(rooms)
        listed.append(
            {
                "id": f"R{index}",
                "name": f"{name} — Double or Twin",
                "max_guests": max(guests - 1, 1) if is_last and len(rooms) > 1 else guests,
                "rates": rates,
            }
        )
    listed.append(
        {
            "id": f"R{len(rooms) + 1}",
            "name": EXTRA_ROOM_NAME,
            "max_guests": 4,
            "rates": [{"id": f"P{rate_number + 1}", "name": STANDARD_RATE_NAME}],
        }
    )
    return listed


def _as_property(listing: ChannelSimulatorListing) -> ChannelProperty:
    return ChannelProperty(
        property_id=listing.hotel_id,
        name=listing.name,
        rooms=tuple(
            ChannelRoom(
                id=str(room["id"]),
                name=str(room["name"]),
                max_guests=int(room["max_guests"]),
                rates=tuple(
                    ChannelRate(id=str(rate["id"]), name=str(rate["name"]))
                    for rate in room.get("rates", [])
                ),
            )
            for room in listing.rooms
        ),
    )


async def find_listing(
    session: AsyncSession, tenant_id: UUID, hotel_id: str
) -> ChannelSimulatorListing | None:
    return (
        await session.exec(
            select(ChannelSimulatorListing).where(
                col(ChannelSimulatorListing.tenant_id) == tenant_id,
                col(ChannelSimulatorListing.hotel_id) == hotel_id,
            )
        )
    ).first()


class SimulatedChannel:
    async def fetch_property(self, call: ChannelCall, property_id: str) -> ChannelProperty:
        listing = await find_listing(call.session, call.tenant_id, property_id)
        if listing is None:
            raise UnknownChannelPropertyError(property_id)
        return _as_property(listing)


register_channel(SIMULATOR_CHANNEL, SimulatedChannel())
