"""CSRF defence for cookie-authenticated requests: refuse foreign web origins.

The session cookie is sent automatically by the browser, so a page on another site
could try to submit a state-changing request on a signed-in user's behalf. Browsers
attach `Origin` (or at least `Referer`) to such requests; this middleware rejects
unsafe methods whose source is neither a configured frontend origin
(`PREFAB_CORS_ORIGINS`) nor the API's own host.

Requests carrying neither header pass: they come from non-browser clients (server
code, scripts, tests), which do not hold a victim's cookies.
"""

import json
import logging
from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

log = logging.getLogger(__name__)

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
BLOCKED_DETAIL = "Cross-site request blocked"


def _origin_of(url: str) -> tuple[str, str] | None:
    """(scheme, host[:port]) of `url`, lowercased; None when it is not an http(s) URL."""
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        return None
    return parts.scheme.lower(), parts.netloc.lower()


def normalise_origins(origins: list[str]) -> frozenset[str]:
    """Configured origins as canonical `scheme://host[:port]` strings."""
    parsed = (_origin_of(origin) for origin in origins)
    return frozenset(f"{scheme}://{host}" for scheme, host in filter(None, parsed))


def is_trusted_source(source: str, allowed_origins: frozenset[str], request_host: str) -> bool:
    """True when `source` (an Origin or Referer value) is an allowed origin or this API."""
    origin = _origin_of(source)
    if origin is None:  # includes the opaque "null" origin
        return False
    scheme, host = origin
    return f"{scheme}://{host}" in allowed_origins or host == request_host.lower()


class OriginCheckMiddleware:
    """Reject unsafe-method requests whose Origin/Referer is not trusted (403)."""

    def __init__(self, app: ASGIApp, allowed_origins: list[str]) -> None:
        self._app = app
        self._allowed = normalise_origins(allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in SAFE_METHODS:
            await self._app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        source = headers.get("origin") or headers.get("referer")
        if source is None or is_trusted_source(source, self._allowed, headers.get("host", "")):
            await self._app(scope, receive, send)
            return
        log.warning(
            "Blocked cross-site %s %s from %s", scope["method"], scope["path"], source[:200]
        )
        body = json.dumps({"detail": BLOCKED_DETAIL}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
