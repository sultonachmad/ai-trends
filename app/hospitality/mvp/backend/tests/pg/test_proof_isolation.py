"""Transfer proofs: duplicate images are flagged; nothing crosses tenants."""

import pytest
from sqlalchemy import text

from app.services import transfer_proofs
from tests.pg.conftest import (
    guest_uploads,
    image,
    make_link,
    set_bank_account,
    staff_uploads,
    start_workspace,
    token_of,
)

pytestmark = pytest.mark.integration

BASE = "/api/transfer-proofs"


async def _queue(client) -> list[dict]:
    return (await client.get(BASE)).json()["items"]


# ---- duplicates ------------------------------------------------------------------------


async def test_the_same_image_is_flagged_on_every_later_use(pg_client) -> None:
    await start_workspace(pg_client)
    same = image("reused")

    first = (await staff_uploads(pg_client, same, amount=100000, description="Pertama")).json()
    second = (await staff_uploads(pg_client, same, amount=200000, description="Kedua")).json()
    third = (await staff_uploads(pg_client, same, amount=300000, description="Ketiga")).json()
    other = (
        await staff_uploads(pg_client, image("other"), amount=400000, description="Lain")
    ).json()

    assert first["duplicate_of"] is None
    for later in (second, third):
        assert later["duplicate_of"]["id"] == first["id"]
        assert later["duplicate_of"]["description"] == "Pertama"
    assert other["duplicate_of"] is None  # a different image is not flagged
    listed = {p["description"]: p["duplicate_of"] for p in await _queue(pg_client)}
    assert listed["Pertama"] is None and listed["Kedua"]["id"] == first["id"]


async def test_a_duplicate_is_not_blocked(pg_client, guest) -> None:
    await start_workspace(pg_client)
    await set_bank_account(pg_client)
    token_one = token_of(await make_link(pg_client, description="Link satu"))
    token_two = token_of(await make_link(pg_client, description="Link dua"))

    first = await guest_uploads(guest, token_one, image("same"))
    second = await guest_uploads(guest, token_two, image("same"))

    assert (first.status_code, second.status_code) == (201, 201)
    assert "duplicate" not in second.text  # the guest is told nothing about it
    flagged = [p for p in await _queue(pg_client) if p["duplicate_of"]]
    assert [p["description"] for p in flagged] == ["Link dua"]


async def test_an_identical_image_at_another_property_is_not_a_duplicate(
    pg_client, other_client
) -> None:
    await start_workspace(pg_client)
    await start_workspace(other_client)
    same = image("shared-between-tenants")

    await staff_uploads(pg_client, same, amount=100000, description="Di A")
    at_b = (await staff_uploads(other_client, same, amount=100000, description="Di B")).json()

    assert at_b["duplicate_of"] is None


# ---- isolation -------------------------------------------------------------------------


async def test_other_tenant_cannot_reach_a_proof_or_its_image(pg_client, other_client) -> None:
    await start_workspace(pg_client)
    await start_workspace(other_client)
    proof = (
        await staff_uploads(pg_client, image("rahasia"), amount=100000, description="A")
    ).json()
    url = f"{BASE}/{proof['id']}"

    responses = [
        await other_client.get(url),
        await other_client.get(f"{url}/image"),
        await other_client.post(f"{url}/approve"),
        await other_client.post(f"{url}/reject", json={"reason": "bukan milik saya"}),
    ]

    assert [r.status_code for r in responses] == [404] * 4
    assert all(image("rahasia") not in r.content for r in responses)
    assert (await pg_client.get(url)).json()["state"] == "awaiting"


async def test_queues_and_counts_never_mix_tenants(pg_client, other_client) -> None:
    await start_workspace(pg_client)
    await start_workspace(other_client)
    await staff_uploads(pg_client, image("a"), amount=100000, description="milik A")
    await staff_uploads(other_client, image("b"), amount=100000, description="milik B")
    await staff_uploads(other_client, image("c"), amount=100000, description="milik B juga")

    assert [p["description"] for p in await _queue(pg_client)] == ["milik A"]
    assert sorted(p["description"] for p in await _queue(other_client)) == [
        "milik B",
        "milik B juga",
    ]
    assert (await pg_client.get("/api/workspace")).json()["proofs_awaiting_review"] == 1
    assert (await other_client.get("/api/workspace")).json()["proofs_awaiting_review"] == 2


async def test_cannot_attach_a_proof_to_another_tenants_link(pg_client, other_client) -> None:
    await start_workspace(pg_client)
    await start_workspace(other_client)
    created = await make_link(pg_client)

    response = await staff_uploads(other_client, payment_link_id=created["link"]["id"])

    assert response.status_code == 404
    assert await _queue(pg_client) == []
    assert await _queue(other_client) == []


async def test_files_are_kept_in_the_owning_tenants_folder(
    pg_client, other_client, _document_storage
) -> None:
    workspace_a = await start_workspace(pg_client)
    workspace_b = await start_workspace(other_client)

    await staff_uploads(pg_client, image("a"), amount=100000, description="A")
    await staff_uploads(other_client, image("b"), amount=100000, description="B")

    folders = {path.parent.name for path in _document_storage.rglob("*.jpg")}
    assert folders == {workspace_a["tenant"]["id"], workspace_b["tenant"]["id"]}
    in_a = list((_document_storage / workspace_a["tenant"]["id"]).iterdir())
    assert [p.read_bytes() for p in in_a] == [image("a")]


async def test_proof_routes_run_inside_the_tenant_scope(pg_client, monkeypatch) -> None:
    workspace = await start_workspace(pg_client)
    seen: dict[str, str] = {}
    real = transfer_proofs.list_proofs

    async def probing(session, context, *args, **kwargs):
        row = (
            await session.execute(
                text("SELECT current_user, current_setting('app.tenant_id', true)")
            )
        ).one()
        seen["role"], seen["tenant"] = row[0], row[1]
        return await real(session, context, *args, **kwargs)

    monkeypatch.setattr(transfer_proofs, "list_proofs", probing)

    assert (await pg_client.get(BASE)).status_code == 200
    assert seen == {"role": "app_rw", "tenant": workspace["tenant"]["id"]}


async def test_queue_uses_a_constant_number_of_queries(pg_client, pg_engine) -> None:
    from sqlalchemy import event

    await start_workspace(pg_client)
    same = image("x")
    for index in range(8):
        await staff_uploads(pg_client, same, amount=100000 + index, description=f"T{index}")
    statements: list[str] = []

    def record(_conn, _cursor, statement, *_args) -> None:
        if statement.lstrip().upper().startswith("SELECT") and "set_config" not in statement:
            statements.append(statement)

    event.listen(pg_engine.sync_engine, "before_cursor_execute", record)
    try:
        page = (await pg_client.get(BASE)).json()
    finally:
        event.remove(pg_engine.sync_engine, "before_cursor_execute", record)

    assert len(page["items"]) == 8
    # membership, property, proofs, staff names, documents, earlier proofs — not one per row
    assert len(statements) <= 7, statements
