"""The simulated agency's listing: agency-style names and something to get wrong."""

import re

import pytest

from app.channels.provider import UnknownChannelError, get_channel, is_connectable
from app.channels.simulator import (
    EXTRA_ROOM_NAME,
    SIMULATOR_CHANNEL,
    listing_rooms,
    new_hotel_id,
)


def test_hotel_ids_look_like_an_agency_id_and_differ() -> None:
    ids = {new_hotel_id() for _ in range(100)}

    assert len(ids) == 100
    assert all(re.fullmatch(r"SIM-[2-9A-HJ-NP-Z]{6}", hotel_id) for hotel_id in ids)


def test_listing_uses_the_agencys_own_ids_and_names() -> None:
    rooms = listing_rooms([("Deluxe", 2, ["Normal", "Hemat"]), ("Suite", 4, ["Normal"])])

    assert [room["id"] for room in rooms] == ["R1", "R2", "R3"]
    assert rooms[0]["name"] == "Deluxe — Double or Twin"
    assert rooms[0]["rates"] == [
        {"id": "P1", "name": "Normal — Agency Rate"},
        {"id": "P2", "name": "Hemat — Agency Rate"},
    ]
    assert rooms[1]["rates"] == [{"id": "P3", "name": "Normal — Agency Rate"}]


def test_listing_has_an_extra_room_and_a_smaller_last_room() -> None:
    rooms = listing_rooms([("Deluxe", 2, ["Normal"]), ("Suite", 4, ["Normal"])])

    assert rooms[-1]["name"] == EXTRA_ROOM_NAME
    assert [room["max_guests"] for room in rooms] == [2, 3, 4]


def test_a_single_room_keeps_its_capacity_and_one_guest_rooms_stay_at_one() -> None:
    assert listing_rooms([("Deluxe", 2, ["Normal"])])[0]["max_guests"] == 2
    assert listing_rooms([("A", 2, []), ("Single", 1, [])])[1]["max_guests"] == 1


def test_rate_ids_are_unique_across_the_listing() -> None:
    rooms = listing_rooms([("A", 2, ["x", "y"]), ("B", 2, ["x"]), ("C", 2, [])])

    rate_ids = [rate["id"] for room in rooms for rate in room["rates"]]
    assert len(rate_ids) == len(set(rate_ids)) == 4


def test_the_simulator_is_registered_and_nothing_else_is() -> None:
    assert is_connectable(SIMULATOR_CHANNEL)
    assert not is_connectable("traveloka")
    with pytest.raises(UnknownChannelError):
        get_channel("traveloka")
