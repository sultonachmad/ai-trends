"""Session lifecycle routes for the auth-session prefab: login, who-am-i, logout.

All routes rely on `SessionMiddleware` having already run (it resolves the
session cookie into `request.state.user` on every request — see
`app/session/middleware.py`). `logout` additionally deletes the underlying
session record via `request.app.state.session_store`, the same `SessionStore`
instance the middleware uses — see the integrate script for why a route
handler must never construct a second `SessionStore()` of its own.

Session user shape (available as `request.state.user` on every request):
    {"user_id": "42", "email": "user@example.com"}

`user_id` is always the string representation of the integer PK from the
`user` table — use `int(user["user_id"])` to convert back where needed.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth.models import User
from app.auth.security import verify_password
from app.database import get_session
from app.session.middleware import DEFAULT_COOKIE_NAME, DEFAULT_COOKIE_PATH

router = APIRouter(prefix="/session", tags=["session"])


class LoginBody(BaseModel):
    email: str
    password: str


@router.post("/login")
async def login(
    body: LoginBody,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Verify credentials, create a session, and set the session cookie.

    `user_id` is stored as `str(user.id)` so every downstream consumer can
    safely call `int(user["user_id"])` to recover the integer PK.
    """
    result = await db.exec(select(User).where(User.email == body.email.lower()))
    user = result.first()
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    store = request.app.state.session_store
    session_id = await store.create(
        user_id=str(user.id),
        data={"email": user.email},
    )
    response.set_cookie(
        key=DEFAULT_COOKIE_NAME,
        value=session_id,
        path=DEFAULT_COOKIE_PATH,
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return {"message": "Logged in", "email": user.email}


@router.get("/me")
async def get_me(request: Request) -> dict[str, Any]:
    """Return the current session's user data, or 401 if there is none."""
    if request.state.user is None:
        raise HTTPException(status_code=401, detail="No active session")
    return request.state.user


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response) -> None:
    """Delete the current session (if any) and clear the session cookie.

    Always clears the cookie, even if no session record was found for it
    (e.g. it already expired) — the goal is "the browser stops sending this
    cookie", not "a session existed to delete".
    """
    session_id = request.cookies.get(DEFAULT_COOKIE_NAME)
    if session_id is not None:
        await request.app.state.session_store.delete(session_id)
    response.delete_cookie(key=DEFAULT_COOKIE_NAME, path=DEFAULT_COOKIE_PATH)
