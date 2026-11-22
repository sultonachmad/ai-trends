"""Simulated online travel agency.

It stands in for agencies that need partner certification. Its "extranet" — the
listings a tester creates — lives in `channelsimulatorlisting`. Connecting to it works
like connecting to a real agency: you need the property ID it gave the listing, and it
answers with its own room and rate IDs and names.

Pushed availability, prices and restrictions are acknowledged and stored on the
listing (`ari`), so the agency can be asked what it currently holds — and a tester can
make it fail its next N pushes (`fail_next`) to exercise retries and drift.
"""

import datetime as dt
import secrets
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.channels.provider import (
    AriDay,
    ChannelBookingEvent,
    ChannelCall,
    ChannelProperty,
    ChannelRate,
    ChannelRoom,
    ChannelStayGuest,
    ChannelUnavailableError,
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


def _day_as_stored(day: AriDay) -> dict[str, object]:
    return {
        "date": day.date,
        "available": day.available,
        "closed": day.closed,
        "min_stay": day.min_stay,
        "prices": dict(day.prices),
    }


def _day_from_stored(stored: dict[str, object]) -> AriDay:
    return AriDay(
        date=str(stored["date"]),
        available=int(stored["available"]),
        closed=bool(stored["closed"]),
        min_stay=int(stored["min_stay"]) if stored.get("min_stay") is not None else None,
        prices={str(k): int(v) for k, v in stored.get("prices", {}).items()},
    )


async def set_fail_next(session: AsyncSession, tenant_id: UUID, hotel_id: str, pushes: int) -> None:
    """Make the agency fail its next `pushes` pushes (development and test only)."""
    listing = await find_listing(session, tenant_id, hotel_id)
    if listing is None:
        raise UnknownChannelPropertyError(hotel_id)
    listing.fail_next = max(int(pushes), 0)
    session.add(listing)
    await session.commit()


class SimulatedChannel:
    async def fetch_property(self, call: ChannelCall, property_id: str) -> ChannelProperty:
        listing = await find_listing(call.session, call.tenant_id, property_id)
        if listing is None:
            raise UnknownChannelPropertyError(property_id)
        return _as_property(listing)

    async def push_ari(
        self, call: ChannelCall, property_id: str, days: dict[str, list[AriDay]]
    ) -> None:
        listing = await find_listing(call.session, call.tenant_id, property_id)
        if listing is None:
            raise UnknownChannelPropertyError(property_id)
        if (listing.fail_next or 0) > 0:
            listing.fail_next -= 1
            session = call.session
            session.add(listing)
            await session.commit()
            raise ChannelUnavailableError(f"simulated failure ({listing.fail_next} left)")
        ari = dict(listing.ari or {})
        for room_id, room_days in days.items():
            # copy the room's dict: mutating the one inside `listing.ari` in place is
            # not seen as a change to the JSONB column, and the push would be lost
            room = {date: dict(day) for date, day in ari.get(room_id, {}).items()}
            for day in room_days:
                room[day.date] = _day_as_stored(day)
            ari[room_id] = room
        listing.ari = ari
        call.session.add(listing)
        await call.session.commit()

    async def fetch_booking_changes(
        self, call: ChannelCall, property_id: str, since: str | None
    ) -> list["ChannelBookingEvent"]:
        listing = await find_listing(call.session, call.tenant_id, property_id)
        if listing is None:
            raise UnknownChannelPropertyError(property_id)
        history = [booking_event_from_stored(item) for item in (listing.bookings or [])]
        if since is None:
            return history
        return [event for event in history if event.occurred_at > since]

    async def fetch_current_ari(
        self, call: ChannelCall, property_id: str, room_ids: list[str], dates: list[str]
    ) -> dict[str, list[AriDay]]:
        listing = await find_listing(call.session, call.tenant_id, property_id)
        if listing is None:
            raise UnknownChannelPropertyError(property_id)
        ari = listing.ari or {}
        wanted = set(dates)
        return {
            room_id: sorted(
                (
                    _day_from_stored(stored)
                    for date, stored in ari.get(room_id, {}).items()
                    if date in wanted
                ),
                key=lambda day: day.date,
            )
            for room_id in room_ids
        }


register_channel(SIMULATOR_CHANNEL, SimulatedChannel())


def new_booking_reference() -> str:
    """An agency-style booking reference, e.g. AGY-7F3K2Q."""
    code = "".join(secrets.choice(_HOTEL_ID_ALPHABET) for _ in range(_HOTEL_ID_LENGTH))
    return f"AGY-{code}"


def booking_event_from_stored(stored: dict[str, object]) -> ChannelBookingEvent:
    """Rebuild an event from the listing's booking store."""
    guest = stored.get("guest") or {}
    return ChannelBookingEvent(
        external_booking_id=str(stored["external_booking_id"]),
        version=int(stored["version"]),
        kind=str(stored["kind"]),
        external_room_id=str(stored["external_room_id"]),
        external_rate_id=str(stored["external_rate_id"]),
        arrival=str(stored["arrival"]),
        departure=str(stored["departure"]),
        units=int(stored.get("units", 1)),
        guests=ChannelStayGuest(
            name=str(guest.get("name", "Tamu Kanal")), phone=guest.get("phone")
        ),
        total_amount=int(stored["total_amount"]),
        nightly_amounts=[int(n) for n in stored.get("nightly_amounts", [])],
        currency=str(stored.get("currency", "IDR")),
        payment_collect=str(stored.get("payment_collect", "channel")),
        occurred_at=str(stored["occurred_at"]),
        raw=dict(stored.get("raw", stored)),  # type: ignore[arg-type]
    )


def store_booking_event(
    listing: ChannelSimulatorListing,
    event: ChannelBookingEvent,
) -> list[dict[str, object]]:
    """Add the event to the listing's booking history (a copy, not a mutation)."""
    history = [dict(item) for item in (listing.bookings or [])]
    history.append(
        {
            "external_booking_id": event.external_booking_id,
            "version": event.version,
            "kind": event.kind,
            "external_room_id": event.external_room_id,
            "external_rate_id": event.external_rate_id,
            "arrival": event.arrival,
            "departure": event.departure,
            "units": event.units,
            "guest": {"name": event.guests.name, "phone": event.guests.phone},
            "total_amount": event.total_amount,
            "nightly_amounts": list(event.nightly_amounts),
            "currency": event.currency,
            "payment_collect": event.payment_collect,
            "occurred_at": event.occurred_at,
            "raw": dict(event.raw),
        }
    )
    return history


def make_booking_event(
    *,
    external_room_id: str,
    external_rate_id: str,
    arrival: str,
    departure: str,
    total_amount: int,
    guest_name: str = "Tamu Kanal",
    guest_phone: str | None = None,
    external_booking_id: str | None = None,
    version: int = 1,
    kind: str = "new",
    units: int = 1,
    payment_collect: str = "channel",
    occurred_at: str | None = None,
) -> ChannelBookingEvent:
    """Build an agency booking event; nightly amounts split the total evenly."""
    from datetime import date

    nights = (date.fromisoformat(departure) - date.fromisoformat(arrival)).days
    nights = max(nights, 1)
    base, extra = divmod(total_amount, nights)
    nightly = [base + (1 if i < extra else 0) for i in range(nights)]
    occurred = occurred_at or dt.datetime.now(dt.UTC).isoformat()
    return ChannelBookingEvent(
        external_booking_id=external_booking_id or new_booking_reference(),
        version=version,
        kind=kind,
        external_room_id=external_room_id,
        external_rate_id=external_rate_id,
        arrival=arrival,
        departure=departure,
        units=units,
        guests=ChannelStayGuest(name=guest_name, phone=guest_phone),
        total_amount=total_amount,
        nightly_amounts=nightly,
        currency="IDR",
        payment_collect=payment_collect,
        occurred_at=occurred,
        raw={"source": "simulator", "reference_verified": True},
    )


async def add_booking(
    session: AsyncSession, tenant_id: UUID, hotel_id: str, event: ChannelBookingEvent
) -> None:
    """Record a booking event on the agency's listing. Commits."""
    listing = await find_listing(session, tenant_id, hotel_id)
    if listing is None:
        raise UnknownChannelPropertyError(hotel_id)
    listing.bookings = store_booking_event(listing, event)
    session.add(listing)
    await session.commit()
