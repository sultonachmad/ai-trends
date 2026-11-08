"""Erasure and verification — the ONLY sanctioned mutation surface for `AuditEntry` rows.

`anonymise()` is how a right-to-erasure ("subject wants their data forgotten")
request is honoured against the audit trail: it flips `anonymised=True` and
shreds `subject_key` (sets it to `NULL`) on every matching row, then appends
a NEW audit entry recording that the erasure happened — the erasure is
itself auditable, chained into the same hash chain as everything else.

`purge_expired()` is the retention-window counterpart: it runs the SAME
narrow mutation (anonymise in place) against rows older than their
`event_id`'s retention window, instead of matching by `subject_key`. Retention
purge deliberately does NOT hard-delete rows — deleting a row would leave the
next row's stored `prev_hash` pointing at a hash chain segment `verify()` can
no longer read off a live row, which `verify()` cannot distinguish from
tampering. Anonymising in place keeps every row (and the chain) intact while
still shredding the subject-identifying column, which is what "retention"
means for an append-only ledger: reduce what personal data is retained
without breaking tamper evidence for the entries that stay.

`verify()` recomputes the hash chain over `service.PINNED_FIELDS`
(EXCLUDING `anonymised` and `subject_key` — see AGENTS.md "Pinned columns")
for every stored row, in insertion order, and reports the first row (if any)
whose stored `entry_hash` does not match what the pinned columns + the
previous row's `entry_hash` recompute to.

Read AGENTS.md "Threat model" before changing either function — this module
is where the tamper-evidence guarantee is actually checked (`verify()`) and
where the only legitimate exception to "never mutate a row" lives
(`anonymise()` / `purge_expired()`).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import select

from app.audit import service as audit_service
from app.audit.events import EVT_SUBJECT_ERASED
from app.audit.models import AuditEntry
from app.database import async_session_factory

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class VerifyResult:
    valid: bool
    checked: int
    first_break_id: int | None
    reason: str | None


async def _anonymise_rows(rows: list[AuditEntry], db: Any) -> int:
    """Shared mutation: flip anonymised=True, shred subject_key, on each row.

    This is the ONE place `AuditEntry.anonymised` / `AuditEntry.subject_key`
    are ever assigned outside the initial insert in `service.append()`.
    """
    count = 0
    for row in rows:
        if row.anonymised:
            continue
        row.subject_key = None
        row.anonymised = True
        db.add(row)
        count += 1
    if count:
        await db.commit()
    return count


async def anonymise(
    subject_key: str,
    *,
    actor_id: str | None = None,
    reason: str | None = None,
) -> int:
    """Anonymise every non-anonymised row for `subject_key`. Returns the row count.

    Appends an `EVT_SUBJECT_ERASED` entry (via `audit_service.append()`, so it
    is chained and HMAC-sealed like every other entry) recording the erasure
    itself — with `subject_key=None`, since the mapping this call just
    shredded must not be re-recorded on the very entry documenting the shred.

    **WARNING**: `reason` is written into the erasure entry's payload, which is
    append-only and unshreddable. Never put subject-identifying data (names,
    emails, IDs that resolve to a person) into `reason` — it would re-enter
    the ledger on the very entry documenting the subject's erasure.
    """
    async with async_session_factory() as db:
        result = await db.exec(
            select(AuditEntry).where(
                AuditEntry.subject_key == subject_key,
                AuditEntry.anonymised == False,  # noqa: E712 — SQLAlchemy needs `== False`
            )
        )
        rows = list(result.all())
        erased_count = await _anonymise_rows(rows, db)

    if erased_count:
        await audit_service.append(
            event_id=EVT_SUBJECT_ERASED.id,
            actor_id=actor_id,
            payload={"erased_count": erased_count, "reason": reason},
        )
    return erased_count


async def purge_expired(*, now: datetime | None = None) -> int:
    """Anonymise every row past its `event_id`'s retention window. Returns the count.

    Retention windows come from `audit_service.retention_days_for(event_id)`.
    See the module docstring for why this anonymises in place instead of
    deleting rows.
    """
    now = now or datetime.now(UTC)
    async with async_session_factory() as db:
        result = await db.exec(
            select(AuditEntry).where(AuditEntry.anonymised == False)  # noqa: E712
        )
        rows = list(result.all())
        expired = [
            row
            for row in rows
            if now - row.occurred_at
            > timedelta(days=audit_service.retention_days_for(row.event_id))
        ]
        purged_count = await _anonymise_rows(expired, db)

    if purged_count:
        log.info("audit retention purge: anonymised %d expired entries", purged_count)
    return purged_count


async def verify(*, limit: int | None = None) -> VerifyResult:
    """Recompute the hash chain over PINNED_FIELDS and report the first break, if any."""
    async with async_session_factory() as db:
        stmt = select(AuditEntry).order_by(AuditEntry.id.asc())
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await db.exec(stmt)
        rows = list(result.all())

    prev_hash: str | None = None
    for checked, row in enumerate(rows, start=1):
        if row.prev_hash != prev_hash:
            return VerifyResult(
                valid=False,
                checked=checked,
                first_break_id=row.id,
                reason="prev_hash does not match the preceding entry's entry_hash",
            )
        expected = audit_service.compute_entry_hash(prev_hash, audit_service.pinned_snapshot(row))
        if row.entry_hash != expected:
            return VerifyResult(
                valid=False,
                checked=checked,
                first_break_id=row.id,
                reason="entry_hash does not match the recomputed digest over pinned fields",
            )
        prev_hash = row.entry_hash

    return VerifyResult(valid=True, checked=len(rows), first_break_id=None, reason=None)
