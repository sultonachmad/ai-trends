"""Booking numbers: short, readable aloud, unambiguous."""

import re

from app.services.booking_numbers import ALPHABET, new_booking_number, prefix_for


def test_prefix_comes_from_the_property_name() -> None:
    assert prefix_for("Villa Kalender") == "VK"
    assert prefix_for("  the  bamboo house ") == "TB"
    assert prefix_for("Rumah") == "RU"
    assert prefix_for("Ω-9 !!") == "BK"  # nothing usable: a neutral prefix
    assert prefix_for("a") == "AX"


def test_number_shape() -> None:
    number = new_booking_number("Villa Kalender")

    assert re.fullmatch(r"VK-[2-9A-HJ-NP-Z]{6}", number)


def test_alphabet_has_no_lookalikes() -> None:
    assert not set("01OI") & set(ALPHABET)
    assert len(set(ALPHABET)) == len(ALPHABET) == 32


def test_numbers_differ() -> None:
    assert len({new_booking_number("Villa") for _ in range(200)}) == 200
