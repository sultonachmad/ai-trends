"""Transfer-proof images are deleted after the retention period; records stay.

The clean-up covers every tenant in the shared test database, so these tests look at
their own tenant's records and files, never at the overall count.
"""

import datetime as dt

import pytest
from sqlalchemy import text
from sqlmodel import select

from app.documents.storage import DocumentStorage
from app.models.tenant import Document, Payment, TransferProof
from app.services.proof_retention import purge_expired_proofs, run_startup_purge
from tests.pg.conftest import image, staff_uploads, start_workspace

pytestmark = pytest.mark.integration

BASE = "/api/transfer-proofs"


def _in_days(days: int) -> dt.date:
    return dt.datetime.now(dt.UTC).date() + dt.timedelta(days=days)


async def _decided_proof(client, seed: str, *, approve: bool = True) -> dict:
    proof = (await staff_uploads(client, image(seed), amount=100000, description=seed)).json()
    if approve:
        await client.post(f"{BASE}/{proof['id']}/approve")
    else:
        await client.post(f"{BASE}/{proof['id']}/reject", json={"reason": "tidak cocok"})
    return proof


async def _documents(pg_session, tenant_id: str) -> list[Document]:
    rows = await pg_session.exec(
        select(Document)
        .where(Document.tenant_id == tenant_id)
        .order_by(Document.created_at)
        .execution_options(populate_existing=True)
    )
    return list(rows.all())


def _files(folder) -> int:
    return len(list(folder.rglob("*.jpg")))


async def test_proof_images_are_purged_after_the_retention_period(
    pg_client, pg_session, pg_session_factory, _document_storage
) -> None:
    workspace = await start_workspace(pg_client)
    tenant_id = workspace["tenant"]["id"]
    approved = await _decided_proof(pg_client, "approved")
    await _decided_proof(pg_client, "rejected", approve=False)
    await staff_uploads(pg_client, image("waiting"), amount=100000, description="waiting")
    assert _files(_document_storage) == 3
    storage = DocumentStorage()

    await purge_expired_proofs(pg_session_factory, storage, _in_days(90))
    assert _files(_document_storage) == 3  # day 90: nothing is due yet
    assert not any(d.purged_at for d in await _documents(pg_session, tenant_id))

    await purge_expired_proofs(pg_session_factory, storage, _in_days(91))
    again = await purge_expired_proofs(pg_session_factory, storage, _in_days(91))

    assert again == 0  # nothing is left to delete anywhere: safe to run twice
    assert _files(_document_storage) == 0  # including the one nobody reviewed
    documents = await _documents(pg_session, tenant_id)
    assert [d.purged_at is not None for d in documents] == [True, True, True]
    # records stay: the proofs and their payments
    proofs = (
        await pg_session.exec(select(TransferProof).where(TransferProof.tenant_id == tenant_id))
    ).all()
    payments = (await pg_session.exec(select(Payment).where(Payment.tenant_id == tenant_id))).all()
    assert (len(proofs), len(payments)) == (3, 3)

    read = (await pg_client.get(f"{BASE}/{approved['id']}")).json()
    gone = await pg_client.get(f"{BASE}/{approved['id']}/image")
    assert (read["state"], read["image_available"]) == ("approved", False)
    assert gone.status_code == 410
    assert "retention period" in gone.json()["detail"]


async def test_retention_period_is_a_property_setting(
    pg_client, pg_session, pg_session_factory, _document_storage
) -> None:
    workspace = await start_workspace(pg_client)
    await pg_session.execute(
        text(
            "UPDATE property SET settings = "
            '\'{"business": {"proof_retention_days": 7}}\' WHERE id = :p'
        ),
        {"p": workspace["property"]["id"]},
    )
    await pg_session.commit()
    await _decided_proof(pg_client, "short")
    storage = DocumentStorage()

    await purge_expired_proofs(pg_session_factory, storage, _in_days(7))
    assert _files(_document_storage) == 1  # day 7: not due yet

    await purge_expired_proofs(pg_session_factory, storage, _in_days(8))
    assert _files(_document_storage) == 0
    [document] = await _documents(pg_session, workspace["tenant"]["id"])
    assert document.purged_at is not None


async def test_a_missing_file_does_not_stop_the_run(
    pg_client, other_client, pg_session, pg_session_factory, _document_storage
) -> None:
    workspace_a = await start_workspace(pg_client)
    workspace_b = await start_workspace(other_client)
    await _decided_proof(pg_client, "lost")
    await _decided_proof(other_client, "kept")
    for path in (_document_storage / workspace_a["tenant"]["id"]).iterdir():
        path.unlink()  # someone removed the file by hand

    await purge_expired_proofs(pg_session_factory, DocumentStorage(), _in_days(91))

    # both tenants are done: the missing file counts as already gone, the other is deleted
    assert _files(_document_storage) == 0
    for workspace in (workspace_a, workspace_b):
        [document] = await _documents(pg_session, workspace["tenant"]["id"])
        assert document.purged_at is not None


async def test_a_file_that_cannot_be_deleted_is_left_for_the_next_run(
    pg_client, pg_session, pg_session_factory, monkeypatch
) -> None:
    workspace = await start_workspace(pg_client)
    await _decided_proof(pg_client, "stuck")
    storage = DocumentStorage()

    async def refuse(*args, **kwargs):
        raise PermissionError("read-only volume")

    monkeypatch.setattr(storage, "delete", refuse)

    await purge_expired_proofs(pg_session_factory, storage, _in_days(91))

    [document] = await _documents(pg_session, workspace["tenant"]["id"])
    assert document.purged_at is None  # not stamped, so the next run tries again


async def test_startup_purge_never_raises(pg_engine, monkeypatch) -> None:
    from app.services import proof_retention

    async def explode(*args, **kwargs):
        raise RuntimeError("storage offline")

    monkeypatch.setattr(proof_retention, "purge_expired_proofs", explode)

    await run_startup_purge(pg_engine)  # logged, not raised


async def test_startup_purge_skips_non_postgres_databases() -> None:
    from app.database import engine as sqlite_engine

    await run_startup_purge(sqlite_engine)
