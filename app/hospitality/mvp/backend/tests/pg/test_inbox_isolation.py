"""One property's conversations are invisible and unreachable from another tenant."""

import pytest

from tests.pg.conftest import guest_says, start_workspace

pytestmark = pytest.mark.integration


async def test_other_tenant_cannot_reach_a_conversation_by_id(pg_client, other_client) -> None:
    await start_workspace(pg_client)
    await start_workspace(other_client)
    conversation_id = (await guest_says(pg_client, "rahasia A"))["conversation_id"]
    base = f"/api/conversations/{conversation_id}"

    responses = [
        await other_client.get(base),
        await other_client.get(f"{base}/messages"),
        await other_client.post(f"{base}/messages", json={"body": "halo dari B"}),
        await other_client.post(f"{base}/read"),
        await other_client.post(f"{base}/resolve"),
        await other_client.post(f"{base}/reopen"),
    ]

    assert [r.status_code for r in responses] == [404] * 6
    # and nothing changed for the owner
    owner_view = (await pg_client.get(base)).json()
    assert (owner_view["status"], owner_view["unread_count"]) == ("open", 1)
    thread = (await pg_client.get(f"{base}/messages")).json()
    assert [m["body"] for m in thread] == ["rahasia A"]


async def test_lists_and_counts_never_mix_tenants(pg_client, other_client) -> None:
    await start_workspace(pg_client)
    await start_workspace(other_client)
    await guest_says(pg_client, "untuk A", phone="+6281111111111", name="Tamu A")
    await guest_says(other_client, "untuk B", phone="+6282222222222", name="Tamu B")
    await guest_says(other_client, "untuk B lagi", phone="+6283333333333", name="Tamu B2")

    mine = (await pg_client.get("/api/conversations")).json()["items"]
    theirs = (await other_client.get("/api/conversations")).json()["items"]

    assert [c["guest"]["name"] for c in mine] == ["Tamu A"]
    assert sorted(c["guest"]["name"] for c in theirs) == ["Tamu B", "Tamu B2"]
    assert (await pg_client.get("/api/inbox/summary")).json() == {"unread_conversations": 1}
    assert (await other_client.get("/api/inbox/summary")).json() == {"unread_conversations": 2}


async def test_same_guest_number_at_two_properties_stays_separate(pg_client, other_client) -> None:
    await start_workspace(pg_client)
    await start_workspace(other_client)

    at_a = await guest_says(pg_client, "halo A", phone="+6281234567890")
    at_b = await guest_says(other_client, "halo B", phone="+6281234567890")

    assert at_a["conversation_id"] != at_b["conversation_id"]
    thread_a = (
        await pg_client.get(f"/api/conversations/{at_a['conversation_id']}/messages")
    ).json()
    assert [m["body"] for m in thread_a] == ["halo A"]


async def test_inbox_routes_run_inside_the_tenant_scope(pg_client, monkeypatch) -> None:
    """Fails if the inbox stops binding the restricted role / tenant to its session."""
    from sqlalchemy import text

    from app.services import inbox

    workspace = await start_workspace(pg_client)
    seen: dict[str, str] = {}
    real = inbox.list_conversations

    async def probing(session, context, *args, **kwargs):
        row = (
            await session.execute(
                text("SELECT current_user, current_setting('app.tenant_id', true)")
            )
        ).one()
        seen["role"], seen["tenant"] = row[0], row[1]
        return await real(session, context, *args, **kwargs)

    monkeypatch.setattr(inbox, "list_conversations", probing)

    assert (await pg_client.get("/api/conversations")).status_code == 200
    assert seen == {"role": "app_rw", "tenant": workspace["tenant"]["id"]}
