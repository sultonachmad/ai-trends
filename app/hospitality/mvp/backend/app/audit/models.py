"""SQLModel table definition for the audit trail (DS-3 `audit_evidence_model`).

Table layout:
    audit_entries — one row per audited action, hash-chained to the row
                    before it via `prev_hash` / `entry_hash`.

This is the only table this prefab defines. It is append-only in spirit: the
only sanctioned mutation is `app/audit/erasure.py`'s `anonymise()`, which
flips `anonymised` and shreds `subject_key` — see AGENTS.md "Pinned columns"
for exactly which columns that mutation is allowed to touch, and why the rest
must never change after insert.

Audit columns (`created_at`, `updated_at`, `created_by`, `updated_by`) and the
auto-increment `id` PK come from BaseEntity (-> TimestampMixin -> SQLModel),
same as the `rbac` prefab's tables. `created_at` is this row's insert time;
`occurred_at` below is the audited action's own timestamp — they usually
match but are not the same field (an append retried from the `spool` write
mode inserts later than the action occurred).

No `from __future__ import annotations` here, matching rbac/models.py — keeps
the door open for a future Relationship() field without a silent breakage.
"""

from datetime import datetime

from sqlalchemy import JSON, Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.crud.base_model import BaseEntity, utc_datetime_field

# Generic JSON on every dialect, native JSONB when the generated project runs
# on Postgres (the common case) — sqlite (the scaffold's zero-config default)
# gets the portable JSON fallback instead of failing to compile the column.
_payload_type = JSON().with_variant(JSONB(), "postgresql")


class AuditEntry(BaseEntity, table=True):
    """One append-only, hash-chained audit-log row.

    Pinned columns (hashed into `entry_hash`, see AGENTS.md): every column on
    this model EXCEPT `anonymised` and `subject_key`.
    """

    __tablename__ = "audit_entries"

    event_id: str = Field(
        index=True,
        max_length=200,
        description="AUDIT_EVENTS registry key (app/audit/events.py) this row records.",
    )
    actor_id: str | None = Field(
        default=None,
        index=True,
        max_length=200,
        description="Acting principal id (e.g. user id). NULL for system-initiated events.",
    )
    occurred_at: datetime = utc_datetime_field(
        default_now=True,
        description="When the audited action occurred (UTC) — the DS-3 'timestamp' field.",
    )
    payload: dict = Field(
        default_factory=dict,
        sa_column=Column(_payload_type),
        description="Event-specific structured detail. Keep subject-identifying data out of "
        "here — use `subject_key` instead so erasure has something narrow to shred.",
    )
    request_id: str | None = Field(
        default=None,
        index=True,
        max_length=200,
        description="Correlation id for the originating HTTP request, if any.",
    )
    session_id: str | None = Field(
        default=None,
        index=True,
        max_length=200,
        description="Correlation id for the originating session, if any.",
    )

    # ── Columns EXCLUDED from the pinned set (erasure.anonymise() mutates these) ──
    subject_key: str | None = Field(
        default=None,
        index=True,
        max_length=200,
        description="Pseudonymised subject reference. Shredded (set NULL) by "
        "erasure.anonymise() — EXCLUDED from verify()'s pinned column set.",
    )
    anonymised: bool = Field(
        default=False,
        description="True once erasure.anonymise() has run for this row. EXCLUDED from "
        "verify()'s pinned column set.",
    )

    # ── Hash chain ──
    prev_hash: str | None = Field(
        default=None,
        unique=True,
        max_length=64,
        description="entry_hash of the immediately preceding row; NULL for the first entry. "
        "UNIQUE so concurrent appends linearise at the DB level — the second writer "
        "gets IntegrityError and retries with the updated head. Note: PG's default "
        "NULLS DISTINCT means two concurrent genesis inserts (both NULL) can both "
        "commit — see AGENTS.md 'Concurrency' caveat.",
    )
    entry_hash: str = Field(
        index=True,
        max_length=64,
        description="HMAC-SHA256 digest chaining this row to prev_hash over the pinned "
        "columns — see AGENTS.md 'Threat model' and 'Pinned columns'.",
    )
