"""Booking numbers staff and guests can read aloud: `VK-7F3K2Q`.

Two letters from the property's name, then six characters from an alphabet without
look-alikes (no 0/O, 1/I). The caller checks the number is unused and asks again if not.
"""

import re
import secrets

ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
CODE_LENGTH = 6
PREFIX_LENGTH = 2
NEUTRAL_PREFIX = "BK"
PAD_LETTER = "X"


def prefix_for(property_name: str) -> str:
    """Initials of the first two words, or the first two letters of a single word."""
    words = [word for word in re.findall(r"[A-Za-z]+", property_name)]
    if not words:
        return NEUTRAL_PREFIX
    letters = words[0][0] + words[1][0] if len(words) >= PREFIX_LENGTH else words[0][:PREFIX_LENGTH]
    return letters.upper().ljust(PREFIX_LENGTH, PAD_LETTER)


def new_booking_number(property_name: str) -> str:
    code = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
    return f"{prefix_for(property_name)}-{code}"
