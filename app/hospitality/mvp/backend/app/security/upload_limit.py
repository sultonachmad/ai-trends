"""A hard ceiling on the request body of the image-upload routes.

Multipart bodies are parsed (and file parts spooled to a temporary file) before a
route's own checks run, so the per-property size limit alone would still let anyone
send gigabytes to `/api/pay/<anything>/proofs`. This middleware refuses such a request
up front when it declares its length, and cuts it off while streaming when it does not.

The ceiling is the largest value the per-property setting can take plus room for the
multipart framing; the exact per-property limit is still enforced by the route.
"""

import json
import logging
import re

from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.tenancy.business_settings import MAX_PROOF_UPLOAD_MB

log = logging.getLogger(__name__)

BYTES_PER_MB = 1024 * 1024
FRAMING_ALLOWANCE_BYTES = BYTES_PER_MB
MAX_UPLOAD_BODY_BYTES = MAX_PROOF_UPLOAD_MB * BYTES_PER_MB + FRAMING_ALLOWANCE_BYTES
TOO_LARGE_DETAIL = "The upload is too large."
BAD_LENGTH_DETAIL = "Invalid Content-Length"

_UPLOAD_PATH = re.compile(
    r"^/api/(?:pay/[^/]+/proofs|transfer-proofs|bookings/[^/]+/guests/scan)/?$"
)


def is_upload_path(path: str) -> bool:
    """True for the routes that accept an image: transfer proofs and guest IDs."""
    return _UPLOAD_PATH.fullmatch(path) is not None


async def _refuse(send: Send, status_code: int, detail: str) -> None:
    body = json.dumps({"detail": detail}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"connection", b"close"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class UploadSizeLimitMiddleware:
    """Refuse (413) an upload whose body exceeds `max_bytes`, declared or streamed."""

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_UPLOAD_BODY_BYTES) -> None:
        self._app = app
        self._max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST":
            await self._app(scope, receive, send)
            return
        if not is_upload_path(scope["path"]):
            await self._app(scope, receive, send)
            return
        declared = Headers(scope=scope).get("content-length")
        if declared is not None and not declared.isdigit():
            await _refuse(send, 400, BAD_LENGTH_DETAIL)
            return
        if declared is not None and int(declared) > self._max_bytes:
            log.warning("Refused oversized upload to %s (%s bytes)", scope["path"], declared)
            await _refuse(send, 413, TOO_LARGE_DETAIL)
            return
        await self._app(scope, self._counting(receive, scope["path"]), send)

    def _counting(self, receive: Receive, path: str) -> Receive:
        """`receive` that stops the request once more than the ceiling has arrived."""
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self._max_bytes:
                    log.warning("Cut off oversized upload to %s", path)
                    # FastAPI re-raises an HTTPException met while reading the body.
                    raise HTTPException(status_code=413, detail=TOO_LARGE_DETAIL)
            return message

        return limited_receive
