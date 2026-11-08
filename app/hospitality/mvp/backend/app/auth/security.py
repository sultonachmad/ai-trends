"""Password hashing for credentials-based (email/password) authentication.

Uses the `bcrypt` package directly — NOT `passlib`. passlib is effectively
unmaintained and its bcrypt handler is incompatible with bcrypt>=4.1 (it
relies on a removed `bcrypt.__about__.__version__` attribute during an
internal self-test, which now raises instead of just warning). `verify_password`
runs a constant-time comparison inside `bcrypt.checkpw`, so timing side
channels aren't a concern.
"""
from __future__ import annotations

import bcrypt

MIN_PASSWORD_LENGTH = 8

# bcrypt silently truncates at 72 bytes; reject longer passwords explicitly
# rather than hashing a truncated value the user didn't type.
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise ValueError(f"password must be at most {MAX_PASSWORD_BYTES} bytes")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        return False
    return bcrypt.checkpw(encoded, hashed.encode("utf-8"))
