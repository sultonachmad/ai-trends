"""Payment-link tokens.

The token is the secret part of a pay link (`/pay/<token>`). It is 256 random bits,
shown once, and never stored: the database keeps only its SHA-256 fingerprint.
"""

import hashlib
import re
import secrets

TOKEN_BYTES = 32
_TOKEN_SHAPE = re.compile(r"[A-Za-z0-9_-]{43}")  # urlsafe base64 of 32 bytes, unpadded


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def is_well_formed(token: str) -> bool:
    """Cheap shape check, so garbage never reaches the database."""
    return _TOKEN_SHAPE.fullmatch(token) is not None


def fingerprint(token: str) -> str:
    """What is stored and looked up instead of the token itself."""
    return hashlib.sha256(token.encode("ascii", "strict")).hexdigest()
