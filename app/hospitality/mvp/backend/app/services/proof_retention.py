"""Deleting transfer-proof images after their retention period.

The PRD keeps the payment record and deletes the screenshot 90 days (a property
setting) after the decision. `document.retention_until` is set at upload (so an image
nobody reviews is still deleted) and restarted when the proof is approved or rejected;
this module removes files whose date has passed and stamps `purged_at`. The rows stay.

It walks tenant by tenant on tenant-scoped sessions, so row-level security applies
here as it does for requests. Run it at start-up, by hand
(`python -m app.jobs.purge_proofs`) or from a scheduler.
"""

import datetime as dt
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.documents.storage import DocumentStorage
from app.models.control_plane import Tenant
from app.models.tenant import Document
from app.tenancy.session import bind_tenant

log = logging.getLogger(__name__)

PROOF_KIND = "transfer_proof"


async def _purge_tenant(
    session: AsyncSession, storage: DocumentStorage, tenant_id: UUID, today: dt.date
) -> int:
    due = (
        await session.exec(
            select(Document)
            .where(
                col(Document.tenant_id) == tenant_id,
                col(Document.kind) == PROOF_KIND,
                col(Document.purged_at).is_(None),
                col(Document.retention_until) < today,
            )
            .with_for_update(skip_locked=True)
        )
    ).all()
    purged = 0
    for document in due:
        try:
            await storage.delete(tenant_id, document.storage_key)
        except Exception:  # noqa: BLE001 — one bad file must not stop the rest
            log.exception("Could not delete expired proof image document=%s", document.id)
            continue
        document.purged_at = dt.datetime.now(dt.UTC)
        session.add(document)
        purged += 1
    await session.commit()
    return purged


async def purge_expired_proofs(
    session_factory: async_sessionmaker[AsyncSession],
    storage: DocumentStorage,
    today: dt.date | None = None,
) -> int:
    """Delete every proof image past its retention date. Returns how many were deleted."""
    today = today or dt.datetime.now(dt.UTC).date()
    async with session_factory() as session:
        tenant_ids = list((await session.exec(select(Tenant.id))).all())
    total = 0
    for tenant_id in tenant_ids:
        try:
            async with session_factory() as session:
                await bind_tenant(session, tenant_id)
                total += await _purge_tenant(session, storage, tenant_id, today)
        except Exception:  # noqa: BLE001 — keep going with the other tenants
            log.exception("Proof retention failed for tenant=%s", tenant_id)
    if total:
        log.info("Deleted %d transfer-proof image(s) past retention", total)
    return total


async def run_startup_purge(engine: AsyncEngine) -> None:
    """Start-up hook: purge once, never raise. Only PostgreSQL holds the tenant tables."""
    if engine.dialect.name != "postgresql":
        return
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        await purge_expired_proofs(factory, DocumentStorage())
    except Exception:  # noqa: BLE001 — retention must never block start-up
        log.exception("Transfer-proof retention could not run at start-up")
