"""Session-resolving middleware for the auth-session prefab.

On every request, reads the session cookie, resolves it via `SessionStore`,
and attaches the result to `request.state.user` (`None` when absent,
invalid, or expired). Refreshes the session's sliding expiry and re-sets the
cookie on every response for a still-valid session; clears the cookie when
an invalid/expired/deleted session id was presented.

Validity is re-checked against the store *after* the route handler runs, not
reused from the pre-request lookup — a route (e.g. logout) may delete the
session during the request, and re-stamping the stale pre-request state
would silently resurrect the cookie the route just tried to clear.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.session.store import SessionStore

DEFAULT_COOKIE_NAME = "prefab_session"
DEFAULT_COOKIE_PATH = "/"


class SessionMiddleware(BaseHTTPMiddleware):
    """Resolves the session cookie into `request.state.user` on every request."""

    def __init__(
        self,
        app: ASGIApp,
        store: SessionStore,
        cookie_name: str = DEFAULT_COOKIE_NAME,
        cookie_path: str = DEFAULT_COOKIE_PATH,
        secure: bool = True,
        httponly: bool = True,
    ) -> None:
        super().__init__(app)
        self._store = store
        self._cookie_name = cookie_name
        self._cookie_path = cookie_path
        self._secure = secure
        self._httponly = httponly

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        session_id = request.cookies.get(self._cookie_name)
        session = await self._store.get(session_id) if session_id else None

        request.state.user = (
            {"user_id": session["user_id"], **session["data"]} if session is not None else None
        )

        response = await call_next(request)

        if session_id:
            # Re-check after the route ran: it may have deleted the session
            # (logout) or left it untouched — the pre-request `session`
            # value above is now stale either way.
            still_valid = await self._store.get(session_id)
            if still_valid is not None:
                await self._store.touch(session_id)
                response.set_cookie(
                    key=self._cookie_name,
                    value=session_id,
                    path=self._cookie_path,
                    secure=self._secure,
                    httponly=self._httponly,
                    samesite="lax",
                )
            else:
                # Stale/invalid/just-deleted cookie — clear it so the client
                # stops sending it.
                response.delete_cookie(key=self._cookie_name, path=self._cookie_path)

        return response
