"""OAuth-to-session bridge for the auth-oauth2 prefab.

After a successful OAuth sign-in (Google, Microsoft Entra ID), NextAuth
creates a JWT session on the frontend. The auth-session prefab's UI
components, however, rely on a backend-managed ``prefab_session`` cookie
resolved via ``GET /session/me``. This endpoint bridges the two: it accepts
the NextAuth-minted JWT as a Bearer token, verifies it, finds or creates a
local ``User`` record by email, and creates a ``prefab_session`` whose
``user_id`` is the database PK — not the external provider's identifier.

This matters because downstream modules (RBAC, audit trails, etc.) join on
``user.id`` (an integer PK). OAuth providers surface a UUID or opaque string
as the JWT ``sub`` claim; using that directly would break any ``int(user_id)``
cast.

Called automatically by the ``OAuthSessionBridge`` component in
``app/providers.tsx`` — no manual invocation needed.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth.jwt import verify_token
from app.auth.models import User
from app.database import get_session
from app.session.middleware import DEFAULT_COOKIE_NAME, DEFAULT_COOKIE_PATH

log = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_OAUTH_PASSWORD_SENTINEL = "!oauth"


async def _find_or_create_user(
    email: str, db: AsyncSession
) -> User:
    """Return the local User record for *email*, creating one if absent.

    OAuth users have no password — ``hashed_password`` is set to a sentinel
    that can never match a bcrypt hash, so credentials login is impossible
    until the user explicitly sets a password.
    """
    result = await db.exec(select(User).where(User.email == email.lower()))
    user = result.first()
    if user is not None:
        return user

    user = User(email=email.lower(), hashed_password=_OAUTH_PASSWORD_SENTINEL)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    log.info("OAuth bridge: created local user id=%s for %s", user.id, email)
    return user


@router.post("/oauth-bridge")
async def oauth_bridge(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Accept a NextAuth JWT and create a backend session for it."""
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    payload = verify_token(token)

    email = payload.get("email", "")
    name = payload.get("name", "")
    if not email:
        raise HTTPException(status_code=400, detail="JWT payload missing email claim")

    user = await _find_or_create_user(email, db)

    store = request.app.state.session_store
    session_id = await store.create(
        user_id=str(user.id),
        data={"email": email, "name": name},
    )
    response.set_cookie(
        key=DEFAULT_COOKIE_NAME,
        value=session_id,
        path=DEFAULT_COOKIE_PATH,
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return {"user_id": str(user.id), "email": email, "name": name}
