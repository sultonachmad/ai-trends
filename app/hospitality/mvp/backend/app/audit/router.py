"""Audit query, verify, and retention-purge routers.

Registers a single `audit_router`, included in `main.py` via the prefab
integrate snippet:

    GET  /api/audit/entries           — query the trail (paginated, filtered)
    GET  /api/audit/verify            — recompute the hash chain, report the
                                         first tampering/corruption break
    POST /api/audit/retention/purge   — anonymise entries past their
                                         event_id's retention window

`audit_read_dep` and `audit_admin_dep` auto-wire to the `rbac` prefab's
`require_permission()` when `app.rbac.dependencies` is importable, and fall
back to "any authenticated session" (via auth-session's `get_current_user`)
otherwise — see AGENTS.md "`audit_read_dep` — auto-wiring to `rbac`" for the
authorization tradeoff that fallback accepts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.audit import erasure as audit_erasure
from app.audit.models import AuditEntry
from app.database import get_session

audit_router = APIRouter(tags=["audit"])


def _build_permission_dep(code: str, description: str) -> Any:
    """Return a FastAPI dependency gating `code` via rbac, or auth-only as fallback.

    See AGENTS.md "`audit_read_dep` — auto-wiring to `rbac`" for the
    authorization tradeoff of the fallback branch.
    """
    try:
        from app.rbac.dependencies import require_permission
    except ImportError:
        from app.session.dependencies import get_current_user

        async def _authenticated_only(user: dict = Depends(get_current_user)) -> dict:
            return user

        return Depends(_authenticated_only)
    else:
        return require_permission(code, description)


# Built once, at import time — mirrors rbac's own require_permission() call
# pattern so permission codes register (when rbac is present) before the
# startup seed runs.
audit_read_dep = _build_permission_dep("audit:read", "Read audit trail entries")
audit_admin_dep = _build_permission_dep(
    "audit:retention", "Purge expired audit entries (retention policy)"
)


# ── Pydantic schemas ─────────────────────────────────────────────────────────


class AuditEntryOut(BaseModel):
    id: int
    event_id: str
    actor_id: str | None
    occurred_at: datetime
    payload: dict
    request_id: str | None
    session_id: str | None
    subject_key: str | None
    anonymised: bool
    prev_hash: str | None
    entry_hash: str

    class Config:
        from_attributes = True


class VerifyOut(BaseModel):
    valid: bool
    checked: int
    first_break_id: int | None
    reason: str | None


class PurgeOut(BaseModel):
    purged: int


# ── Query ────────────────────────────────────────────────────────────────────


@audit_router.get("/api/audit/entries", response_model=list[AuditEntryOut])
async def list_entries(
    event_id: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    subject_key: str | None = Query(default=None),
    request_id: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: dict = audit_read_dep,
    db: AsyncSession = Depends(get_session),
) -> list[AuditEntry]:
    stmt = select(AuditEntry)
    if event_id is not None:
        stmt = stmt.where(AuditEntry.event_id == event_id)
    if actor_id is not None:
        stmt = stmt.where(AuditEntry.actor_id == actor_id)
    if subject_key is not None:
        stmt = stmt.where(AuditEntry.subject_key == subject_key)
    if request_id is not None:
        stmt = stmt.where(AuditEntry.request_id == request_id)
    if session_id is not None:
        stmt = stmt.where(AuditEntry.session_id == session_id)
    stmt = stmt.order_by(AuditEntry.id.desc()).offset(offset).limit(limit)
    result = await db.exec(stmt)
    return list(result.all())


# ── Verify ───────────────────────────────────────────────────────────────────


@audit_router.get("/api/audit/verify", response_model=VerifyOut)
async def verify_chain(
    limit: int | None = Query(default=None, ge=1),
    user: dict = audit_read_dep,
) -> VerifyOut:
    result = await audit_erasure.verify(limit=limit)
    return VerifyOut(
        valid=result.valid,
        checked=result.checked,
        first_break_id=result.first_break_id,
        reason=result.reason,
    )


# ── Retention purge ──────────────────────────────────────────────────────────


@audit_router.post("/api/audit/retention/purge", response_model=PurgeOut)
async def purge_expired(
    user: dict = audit_admin_dep,
) -> PurgeOut:
    purged = await audit_erasure.purge_expired()
    return PurgeOut(purged=purged)
