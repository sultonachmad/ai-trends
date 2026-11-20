"""Phone numbers are stored in one canonical form: +<country><number>."""

import pytest

from app.messaging.phone import InvalidPhoneError, normalise_phone


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+6281234567890", "+6281234567890"),
        ("+62 812-3456-7890", "+6281234567890"),
        ("(+62) 812 3456 7890", "+6281234567890"),
        ("081234567890", "+6281234567890"),
        ("0812 3456 7890", "+6281234567890"),
        ("+14155552671", "+14155552671"),
        ("  +61412345678  ", "+61412345678"),
    ],
)
def test_normalise_phone(raw: str, expected: str) -> None:
    assert normalise_phone(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "abc",
        "+62",
        "+6281",
        "6281234567890",
        "+62812345678901234",
        "+0812345678",
        "08",
        "++628123456789",
        "+62812x456789",
    ],
)
def test_invalid_numbers_are_rejected(raw: str) -> None:
    with pytest.raises(InvalidPhoneError):
        normalise_phone(raw)
