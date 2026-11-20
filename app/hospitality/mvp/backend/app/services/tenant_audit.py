"""A tenant's change history: who changed what, and when.

Entries are chained: each carries a keyed hash of its own content and of the entry
before it, so a row edited or removed afterwards breaks the chain and shows up in
`verify`. `record` takes a per-tenant advisory lock for the duration of the writing
transaction, so the chain has one writer at a time — whichever route is writing, and
also when a tenant has more than one property.
"""

import datetime as dt
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.audit.service import compute_entry_hash
from app.models.tenant import TenantAuditEntry
from app.tenancy.context import TenantContext

_CHAIN_LOCK = text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))")


def _pinned(entry: TenantAuditEntry) -> dict[str, Any]:
    """The fields the hash covers, in a form that serialises the same way every time."""
    return {
        "tenant_id": str(entry.tenant_id),
        "property_id": str(entry.property_id) if entry.property_id else None,
        "event_id": entry.event_id,
        "actor_id": entry.actor_id,
        "occurred_at": entry.occurred_at.astimezone(dt.UTC).isoformat(),
        "entity_table": entry.entity_table,
        "entity_id": str(entry.entity_id) if entry.entity_id else None,
        "payload": entry.payload,
    }


async def _latest_hash(session: AsyncSession, tenant_id: UUID) -> str | None:
    return (
        await session.exec(
            select(col(TenantAuditEntry.entry_hash))
            .where(col(TenantAuditEntry.tenant_id) == tenant_id)
            .order_by(col(TenantAuditEntry.occurred_at).desc(), col(TenantAuditEntry.id).desc())
            .limit(1)
        )
    ).first()


async def record(
    session: AsyncSession,
    context: TenantContext,
    event_id: str,
    *,
    property_id: UUID,
    entity_table: str,
    entity_id: UUID,
    payload: dict[str, Any] | None = None,
) -> TenantAuditEntry:
    """Add an entry to the tenant's history. Flushed, not committed."""
    # One writer per tenant until this transaction ends: two routes recording at once
    # (or two properties of one tenant) would otherwise read the same head and fork the
    # chain. Always taken last, after any row locks the caller holds, so it cannot cycle.
    await session.execute(_CHAIN_LOCK, {"key": f"tenant-audit-chain:{context.tenant_id}"})
    await session.flush()  # entries written earlier in this transaction must be visible
    entry = TenantAuditEntry(
        tenant_id=context.tenant_id,
        property_id=property_id,
        event_id=event_id,
        actor_id=str(context.user_id),
        occurred_at=dt.datetime.now(dt.UTC),
        entity_table=entity_table,
        entity_id=entity_id,
        payload=payload or {},
        prev_hash=await _latest_hash(session, context.tenant_id),
        entry_hash="",
    )
    entry.entry_hash = compute_entry_hash(entry.prev_hash, _pinned(entry))
    session.add(entry)
    await session.flush()
    return entry


async def history_of(
    session: AsyncSession, context: TenantContext, entity_table: str, entity_id: UUID, limit: int
) -> list[TenantAuditEntry]:
    """The newest entries about one record."""
    rows = await session.exec(
        select(TenantAuditEntry)
        .where(
            col(TenantAuditEntry.tenant_id) == context.tenant_id,
            col(TenantAuditEntry.entity_table) == entity_table,
            col(TenantAuditEntry.entity_id) == entity_id,
        )
        .order_by(col(TenantAuditEntry.occurred_at).desc(), col(TenantAuditEntry.id).desc())
        .limit(limit)
    )
    return list(rows.all())


def verify(entries: list[TenantAuditEntry]) -> bool:
    """True when `entries` (oldest first, a whole chain) are intact and in order."""
    previous: str | None = None
    for entry in entries:
        if entry.prev_hash != previous:
            return False
        if entry.entry_hash != compute_entry_hash(entry.prev_hash, _pinned(entry)):
            return False
        previous = entry.entry_hash
    return True
