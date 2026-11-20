"""Phone numbers in one canonical form: ``+<country code><number>`` (E.164)."""

import re

DEFAULT_COUNTRY_PREFIX = "+62"  # Indonesia: local numbers are written 08…
_SEPARATORS = re.compile(r"[\s\-().]")
_E164 = re.compile(r"\+[1-9]\d{7,14}")
_LOCAL = re.compile(r"0\d{8,13}")


class InvalidPhoneError(ValueError):
    """The value is not a usable phone number."""


def normalise_phone(raw: str) -> str:
    """Canonical form of `raw`, or `InvalidPhoneError`.

    Accepts international numbers written with ``+`` and Indonesian local numbers
    written with a leading ``0``. Bare digits without either are rejected, because
    the country cannot be known.
    """
    compact = _SEPARATORS.sub("", raw or "")
    if _LOCAL.fullmatch(compact):
        compact = DEFAULT_COUNTRY_PREFIX + compact[1:]
    if not _E164.fullmatch(compact):
        raise InvalidPhoneError("Enter a phone number like +6281234567890 or 081234567890")
    return compact
