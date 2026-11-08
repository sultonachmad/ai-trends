"""Audit append service — hash-chained inserts on their own connection.

`append()` is the ONLY sanctioned way to create an `AuditEntry` row. It:

  1. Opens its OWN session via `async_session_factory()` — a separate
     connection/transaction from whatever business transaction triggered the
     audited action. An audit entry never rides inside the caller's commit.
  2. Reads the current chain head (`prev_hash`) and computes this entry's
     `entry_hash` as an HMAC-SHA256 digest over `PINNED_FIELDS`, chained to
     that head.
  3. Commits on its own connection.

Read AGENTS.md "Threat model" and "Pinned columns" before touching
`PINNED_FIELDS` or `compute_entry_hash()` — this is the tamper-evidence
mechanism the whole prefab exists to provide, and it is easy to weaken by
accident (e.g. widening the hashed set to a mutable column).

`AUDIT_WRITE_MODE` (env-tunable, read once at import time here — this module
is the one place in the audit prefab that reads it) controls failure
semantics when the separate append fails:

  fail_closed (DEFAULT) — re-raise: the business request fails too, even
                           though the audit write used a separate connection.
  spool                 — swallow, log loudly, and hand the entry to
                           `_SPOOL` for a later retry; the business write is
                           allowed to complete un-audited in the interim.

See AGENTS.md for the full writeup, including when to deviate from these
defaults.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.audit.events import AUDIT_EVENTS
from app.audit.models import AuditEntry
from app.config import settings
from app.database import async_session_factory

log = logging.getLogger(__name__)


class AuditWriteMode(str, Enum):
    fail_closed = "fail_closed"
    spool = "spool"


def _read_write_mode() -> AuditWriteMode:
    """Read AUDIT_WRITE_MODE from the environment once, at import time.

    An unrecognised value falls back to the safe default (`fail_closed`) with
    a logged warning rather than crashing startup — the failure-safe default
    applies to config parsing too.
    """
    raw = os.getenv("AUDIT_WRITE_MODE", AuditWriteMode.fail_closed.value)
    try:
        return AuditWriteMode(raw)
    except ValueError:
        log.warning(
            "Unrecognised AUDIT_WRITE_MODE=%r; falling back to %r",
            raw,
            AuditWriteMode.fail_closed.value,
        )
        return AuditWriteMode.fail_closed


AUDIT_WRITE_MODE: AuditWriteMode = _read_write_mode()

# In-process retry spool used only in `spool` mode. This is intentionally a
# minimal, process-local list (POC-grade, matching auth-session's in-memory
# store) — a generated project running `spool` mode in production should back
# this with a durable queue instead.
_SPOOL: list[dict[str, Any]] = []

# ── Pinned columns — see AGENTS.md "Pinned columns" before changing this ──
#
# Explicit tuple, not "every AuditEntry column except N names" — see AGENTS.md
# for why an explicit list is required (BaseEntity's `updated_at` mutates on
# the erasure UPDATE too, and would silently break verify() if included).
PINNED_FIELDS: tuple[str, ...] = (
    "event_id",
    "actor_id",
    "occurred_at",
    "payload",
    "request_id",
    "session_id",
    "prev_hash",
)

# Default retention window (days) applied to any event_id without its own
# entry in RETENTION_WINDOWS. Generated projects override both per their own
# DS-3 `retention[]` policy.
DEFAULT_RETENTION_DAYS = 365

# Per-event_id retention override, in days. Empty by default — add entries as
# `{"event-id": days, ...}` when an event needs a window other than the
# default (e.g. a "critical" sensitivity event kept longer).
RETENTION_WINDOWS: dict[str, int] = {}


def _canonical_pinned_json(fields: dict[str, Any]) -> str:
    """Deterministic JSON serialisation of the pinned-field dict for hashing.

    `sort_keys=True` makes the serialisation independent of dict insertion
    order; `default=str` covers `datetime` values (ISO-8601 via `str()` on an
    aware datetime is not ISO — use `.isoformat()` explicitly at the call
    site instead, this default only guards against an unexpected type).
    """
    return json.dumps(fields, sort_keys=True, separators=(",", ":"), default=str)


def compute_entry_hash(prev_hash: str | None, pinned: dict[str, Any]) -> str:
    """HMAC-SHA256 over `{"prev_hash": ..., **pinned}`, keyed by settings.SECRET_KEY.

    Keying the digest (rather than a bare SHA-256) is what makes forging a
    replacement chain require the generated project's secret — see AGENTS.md
    "Threat model" for exactly what that does and does not protect against.
    """
    message = _canonical_pinned_json({"prev_hash": prev_hash, **pinned})
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def pinned_snapshot(entry: AuditEntry) -> dict[str, Any]:
    """Extract `PINNED_FIELDS` from `entry` as a hash-ready dict.

    Shared by `append()` (computing a new entry's hash) and
    `erasure.verify()` (recomputing an existing entry's hash) so both stay in
    lockstep with `PINNED_FIELDS`.
    """
    snapshot: dict[str, Any] = {}
    for field in PINNED_FIELDS:
        value = getattr(entry, field)
        snapshot[field] = value.isoformat() if isinstance(value, datetime) else value
    return snapshot


async def _chain_head(db: Any) -> str | None:
    """Return the `entry_hash` of the most recently inserted row, or None."""
    result = await db.exec(select(AuditEntry).order_by(AuditEntry.id.desc()).limit(1))
    head = result.first()
    return head.entry_hash if head is not None else None


async def append(
    *,
    event_id: str,
    actor_id: str | None = None,
    payload: dict[str, Any] | None = None,
    request_id: str | None = None,
    session_id: str | None = None,
    subject_key: str | None = None,
    occurred_at: datetime | None = None,
) -> AuditEntry | None:
    """Append one hash-chained audit entry on its own connection.

    Returns the persisted `AuditEntry` in `fail_closed` mode (the default),
    or the successfully-persisted entry / `None` in `spool` mode when the
    write failed and was handed to the retry spool instead.

    Raises whatever the underlying DB error is in `fail_closed` mode — the
    caller's business transaction is expected to fail too when this raises.
    """
    if event_id not in AUDIT_EVENTS:
        log.warning("append() called with unregistered event_id=%r", event_id)

    record = {
        "event_id": event_id,
        "actor_id": actor_id,
        "payload": payload or {},
        "request_id": request_id,
        "session_id": session_id,
        "subject_key": subject_key,
        "occurred_at": occurred_at or datetime.now(UTC),
    }

    try:
        return await _append_now(record)
    except Exception:
        if AUDIT_WRITE_MODE is AuditWriteMode.fail_closed:
            raise
        log.error("audit append failed in spool mode; queued for retry: %r", record, exc_info=True)
        _SPOOL.append(record)
        return None


_MAX_CHAIN_RETRIES = 3


async def _append_now(record: dict[str, Any]) -> AuditEntry:
    for attempt in range(_MAX_CHAIN_RETRIES):
        try:
            async with async_session_factory() as db:
                prev_hash = await _chain_head(db)
                entry = AuditEntry(prev_hash=prev_hash, entry_hash="", **record)
                entry.entry_hash = compute_entry_hash(prev_hash, pinned_snapshot(entry))
                db.add(entry)
                await db.commit()
                await db.refresh(entry)
                return entry
        except IntegrityError:
            if attempt == _MAX_CHAIN_RETRIES - 1:
                raise
            log.info("chain-head moved between read and insert (attempt %d); retrying", attempt + 1)
    raise AssertionError("unreachable")


async def retry_spool() -> int:
    """Retry every entry currently queued in `_SPOOL`. Returns the count retried.

    Call this from a periodic background task in `spool` mode (the generated
    project wires its own scheduler — this prefab does not start one).
    Entries that fail again stay in the spool for the next call.
    """
    pending = list(_SPOOL)
    _SPOOL.clear()
    retried = 0
    for record in pending:
        try:
            await _append_now(record)
            retried += 1
        except Exception:
            log.error("audit spool retry failed again; re-queued: %r", record, exc_info=True)
            _SPOOL.append(record)
    return retried


def retention_days_for(event_id: str) -> int:
    """Return the retention window, in days, for `event_id`."""
    return RETENTION_WINDOWS.get(event_id, DEFAULT_RETENTION_DAYS)
