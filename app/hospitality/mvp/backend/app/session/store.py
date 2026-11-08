"""In-memory session store for the auth-session prefab.

This is a POC-grade store: sessions live in process memory and are lost on
restart and are not shared across worker processes. Swap this module for a
Redis-backed implementation (same public interface) before running with more
than one worker or in production.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

from itsdangerous import BadSignature, URLSafeTimedSerializer

DEFAULT_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days
_SIGNING_SALT = "prefab-auth-session"


@dataclass
class _SessionRecord:
    user_id: str
    data: dict[str, Any]
    created_at: float
    last_accessed: float


class SessionStore:
    """Creates, reads, refreshes, and deletes signed, TTL-bound sessions."""

    def __init__(self, secret_key: str, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._serializer = URLSafeTimedSerializer(secret_key, salt=_SIGNING_SALT)
        self._ttl_seconds = ttl_seconds
        self._sessions: dict[str, _SessionRecord] = {}

    async def create(self, user_id: str, data: dict[str, Any]) -> str:
        """Create a new session for `user_id` and return its signed session id."""
        session_id = self._serializer.dumps(uuid.uuid4().hex)
        now = time.time()
        self._sessions[session_id] = _SessionRecord(
            user_id=user_id,
            data=dict(data),
            created_at=now,
            last_accessed=now,
        )
        return session_id

    async def get(self, session_id: str) -> dict[str, Any] | None:
        """Return `{"user_id", "data", "created_at", "last_accessed"}`, or None
        if `session_id` is missing, has an invalid signature, or has expired."""
        if not self._has_valid_signature(session_id):
            return None

        record = self._sessions.get(session_id)
        if record is None:
            return None

        if self._is_expired(record):
            self._sessions.pop(session_id, None)
            return None

        return {
            "user_id": record.user_id,
            "data": dict(record.data),
            "created_at": record.created_at,
            "last_accessed": record.last_accessed,
        }

    async def delete(self, session_id: str) -> None:
        """Remove a session. No-op if it does not exist."""
        self._sessions.pop(session_id, None)

    async def touch(self, session_id: str) -> None:
        """Refresh `last_accessed`, extending the session's sliding expiry."""
        record = self._sessions.get(session_id)
        if record is not None:
            record.last_accessed = time.time()

    def _has_valid_signature(self, session_id: str) -> bool:
        try:
            self._serializer.loads(session_id)
        except BadSignature:
            return False
        return True

    def _is_expired(self, record: _SessionRecord) -> bool:
        return (time.time() - record.last_accessed) > self._ttl_seconds
