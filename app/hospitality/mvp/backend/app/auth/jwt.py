"""JWT verification for tokens issued by the OAuth2 login flow."""

from typing import Any

from fastapi import HTTPException, status
from jose import ExpiredSignatureError, JWTError, jwt

from app.config import settings

# `JWT_ALGORITHM` is optional on the base Settings class — add
# `JWT_ALGORITHM: str = "HS256"` to app/config.py to control it via the
# PREFAB_JWT_ALGORITHM env var. Falls back to HS256 when absent.
JWT_ALGORITHM: str = getattr(settings, "JWT_ALGORITHM", "HS256")


def verify_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT, raising HTTP 401 on any failure."""
    try:
        payload: dict[str, Any] = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        ) from exc
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc

    return payload
