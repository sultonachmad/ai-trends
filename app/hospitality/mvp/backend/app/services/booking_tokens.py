"""Tokens of a direct booking: the pay link and the guest's private link.

Each is derived from a random per-booking seed and the app secret, so the same link can
be sent again (a retried checkout, the WhatsApp confirmation) without storing it. Finding
a token needs both the database and the secret; lookups use only its fingerprint.
"""

import base64
import hashlib
import hmac
import secrets

from app.config import frontend_base_url, settings

PAY, GUEST = "pay", "guest"
GUEST_PATH = "/booking/"


def new_seed() -> str:
    return secrets.token_urlsafe(32)


def derive(seed: str, purpose: str) -> str:
    """A 43-character URL-safe token, the same shape as a payment-link token."""
    digest = hmac.new(
        settings.SECRET_KEY.encode(), f"{purpose}:{seed}".encode(), hashlib.sha256
    ).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def guest_path(seed: str) -> str:
    return f"{GUEST_PATH}{derive(seed, GUEST)}"


def guest_url(seed: str) -> str:
    return f"{frontend_base_url()}{guest_path(seed)}"
