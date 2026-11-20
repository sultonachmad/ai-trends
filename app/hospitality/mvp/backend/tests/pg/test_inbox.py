"""Inbox: list, read, reply, mark read, resolve / reopen."""

import datetime as dt

import pytest
from sqlalchemy import event, text

from app.messaging import provider as provider_module
from app.messaging.provider import SendResult
from tests.pg.conftest import guest_says, start_workspace

pytestmark = pytest.mark.integration


async def _open(client) -> list[dict]:
    return (await client.get("/api/conversations")).json()["items"]


async def test_inbox_requires_sign_in(pg_client) -> None:
    assert (await pg_client.get("/api/conversations")).status_code == 401
    assert (await pg_client.get("/api/inbox/summary")).status_code == 401


async def test_empty_inbox(pg_client) -> None:
    await start_workspace(pg_client)

    page = (await pg_client.get("/api/conversations")).json()

    assert page == {"items": [], "next_cursor": None}
    assert (await pg_client.get("/api/inbox/summary")).json() == {"unread_conversations": 0}


async def test_list_shows_guest_preview_and_unread(pg_client) -> None:
    await start_workspace(pg_client)
    await guest_says(pg_client, "Halo")
    await guest_says(pg_client, "Ada   kamar\nuntuk 2 malam?")

    [conversation] = await _open(pg_client)

    assert conversation["guest"]["name"] == "Budi"
    assert conversation["guest"]["phone"] == "+6281234567890"
    assert conversation["unread_count"] == 2
    assert conversation["status"] == "open"
    assert conversation["last_message"]["preview"] == "Ada kamar untuk 2 malam?"
    assert conversation["last_message"]["direction"] == "inbound"
    assert conversation["can_reply"] is True
    assert conversation["reply_blocked_reason"] is None


async def test_long_message_preview_is_trimmed(pg_client) -> None:
    await start_workspace(pg_client)
    await guest_says(pg_client, "a" * 500)

    [conversation] = await _open(pg_client)

    assert len(conversation["last_message"]["preview"]) == 140
    assert conversation["last_message"]["preview"].endswith("…")


async def test_newest_activity_first(pg_client) -> None:
    await start_workspace(pg_client)
    await guest_says(pg_client, "pertama", phone="+6281111111111", name="A")
    await guest_says(pg_client, "kedua", phone="+6282222222222", name="B")
    await guest_says(pg_client, "lagi", phone="+6281111111111", name="A")

    names = [c["guest"]["name"] for c in await _open(pg_client)]

    assert names == ["A", "B"]


async def test_paging_returns_every_conversation_once(pg_client) -> None:
    await start_workspace(pg_client)
    for index in range(5):
        await guest_says(pg_client, f"halo {index}", phone=f"+62811000000{index}", name=f"G{index}")

    first = (await pg_client.get("/api/conversations?limit=2")).json()
    second = (
        await pg_client.get(
            "/api/conversations", params={"limit": 2, "cursor": first["next_cursor"]}
        )
    ).json()
    third = (
        await pg_client.get(
            "/api/conversations", params={"limit": 2, "cursor": second["next_cursor"]}
        )
    ).json()

    names = [c["guest"]["name"] for page in (first, second, third) for c in page["items"]]
    assert names == ["G4", "G3", "G2", "G1", "G0"]
    assert third["next_cursor"] is None


@pytest.mark.parametrize("query", ["limit=0", "limit=51", "status=spam", "cursor=garbage"])
async def test_bad_list_parameters_are_rejected(pg_client, query) -> None:
    await start_workspace(pg_client)

    assert (await pg_client.get(f"/api/conversations?{query}")).status_code == 422


async def test_list_uses_a_constant_number_of_queries(pg_client, pg_engine) -> None:
    await start_workspace(pg_client)
    for index in range(12):
        await guest_says(pg_client, "halo", phone=f"+6281200000{index:03d}", name=f"G{index}")
    statements: list[str] = []

    def record(_conn, _cursor, statement, *_args) -> None:
        if statement.lstrip().upper().startswith("SELECT") and "FROM" in statement.upper():
            statements.append(statement)

    event.listen(pg_engine.sync_engine, "before_cursor_execute", record)
    try:
        page = (await pg_client.get("/api/conversations")).json()
    finally:
        event.remove(pg_engine.sync_engine, "before_cursor_execute", record)

    assert len(page["items"]) == 12
    table_reads = [s for s in statements if "set_config" not in s]
    # membership, property, conversations, last messages, guests — not one per row
    assert len(table_reads) <= 6, table_reads


async def test_read_thread_oldest_first_and_incremental(pg_client) -> None:
    await start_workspace(pg_client)
    conversation_id = (await guest_says(pg_client, "satu"))["conversation_id"]
    await guest_says(pg_client, "dua")

    messages = (await pg_client.get(f"/api/conversations/{conversation_id}/messages")).json()
    await guest_says(pg_client, "tiga")
    newer = (
        await pg_client.get(
            f"/api/conversations/{conversation_id}/messages", params={"after": messages[-1]["id"]}
        )
    ).json()

    assert [m["body"] for m in messages] == ["satu", "dua"]
    assert [m["body"] for m in newer] == ["tiga"]
    assert messages[0]["direction"] == "inbound"
    assert messages[0]["sender_name"] is None


async def test_reading_messages_does_not_clear_unread_but_mark_read_does(pg_client) -> None:
    await start_workspace(pg_client)
    conversation_id = (await guest_says(pg_client, "Halo"))["conversation_id"]

    await pg_client.get(f"/api/conversations/{conversation_id}/messages")
    assert (await _open(pg_client))[0]["unread_count"] == 1
    assert (await pg_client.get("/api/inbox/summary")).json() == {"unread_conversations": 1}

    marked = await pg_client.post(f"/api/conversations/{conversation_id}/read")

    assert marked.status_code == 200
    assert marked.json()["unread_count"] == 0
    assert (await pg_client.get("/api/inbox/summary")).json() == {"unread_conversations": 0}
    assert (await pg_client.get("/api/workspace")).json()["unread_conversations"] == 0


async def test_reply_is_stored_and_clears_unread(pg_client) -> None:
    workspace = await start_workspace(pg_client)
    conversation_id = (await guest_says(pg_client, "Halo"))["conversation_id"]

    response = await pg_client.post(
        f"/api/conversations/{conversation_id}/messages", json={"body": "  Halo Budi, ada!  "}
    )

    assert response.status_code == 201, response.text
    reply = response.json()
    assert reply["body"] == "Halo Budi, ada!"
    assert (reply["direction"], reply["sender_kind"], reply["status"]) == (
        "outbound",
        "staff",
        "sent",
    )
    assert reply["sender_name"] == workspace["staff"]["display_name"]
    [conversation] = await _open(pg_client)
    assert conversation["unread_count"] == 0
    assert conversation["last_message"]["preview"] == "Halo Budi, ada!"
    assert conversation["last_message"]["direction"] == "outbound"
    thread = (await pg_client.get(f"/api/conversations/{conversation_id}/messages")).json()
    assert [m["body"] for m in thread] == ["Halo", "Halo Budi, ada!"]


@pytest.mark.parametrize("body", ["", "    ", "x" * 4097])
async def test_reply_body_is_validated(pg_client, body) -> None:
    await start_workspace(pg_client)
    conversation_id = (await guest_says(pg_client, "Halo"))["conversation_id"]

    response = await pg_client.post(
        f"/api/conversations/{conversation_id}/messages", json={"body": body}
    )

    assert response.status_code == 422


async def test_reply_rejects_unknown_fields(pg_client) -> None:
    await start_workspace(pg_client)
    conversation_id = (await guest_says(pg_client, "Halo"))["conversation_id"]

    response = await pg_client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"body": "ok", "sender_kind": "guest"},
    )

    assert response.status_code == 422


async def test_reply_after_the_24_hour_window_is_refused(pg_client, pg_session) -> None:
    await start_workspace(pg_client)
    conversation_id = (await guest_says(pg_client, "Halo"))["conversation_id"]
    await pg_session.execute(
        text("UPDATE conversation SET service_window_expires_at = :t WHERE id = :c"),
        {"t": dt.datetime.now(dt.UTC) - dt.timedelta(minutes=1), "c": conversation_id},
    )
    await pg_session.commit()

    response = await pg_client.post(
        f"/api/conversations/{conversation_id}/messages", json={"body": "Maaf baru balas"}
    )

    assert response.status_code == 409
    assert "24-hour" in response.json()["detail"]
    [conversation] = await _open(pg_client)
    assert (conversation["can_reply"], conversation["reply_blocked_reason"]) == (
        False,
        "window_closed",
    )
    thread = (await pg_client.get(f"/api/conversations/{conversation_id}/messages")).json()
    assert [m["body"] for m in thread] == ["Halo"]

    await guest_says(pg_client, "Halo lagi")  # a new guest message reopens the window
    again = await pg_client.post(
        f"/api/conversations/{conversation_id}/messages", json={"body": "Siap"}
    )
    assert again.status_code == 201


async def test_provider_refusal_is_kept_as_a_failed_message(pg_client, monkeypatch) -> None:
    class RefusingProvider:
        async def send_text(self, *, sender: str, recipient: str, body: str) -> SendResult:
            return SendResult(accepted=False, error="number not on WhatsApp")

    await start_workspace(pg_client)
    conversation_id = (await guest_says(pg_client, "Halo"))["conversation_id"]
    monkeypatch.setitem(provider_module._PROVIDERS, "simulator", RefusingProvider())

    response = await pg_client.post(
        f"/api/conversations/{conversation_id}/messages", json={"body": "Halo"}
    )

    assert response.status_code == 201
    assert response.json()["status"] == "failed"
    assert response.json()["error"] == "number not on WhatsApp"


async def test_resolve_and_reopen(pg_client) -> None:
    await start_workspace(pg_client)
    conversation_id = (await guest_says(pg_client, "Halo"))["conversation_id"]

    resolved = await pg_client.post(f"/api/conversations/{conversation_id}/resolve")

    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["unread_count"] == 0
    assert await _open(pg_client) == []
    listed = (await pg_client.get("/api/conversations?status=resolved")).json()["items"]
    assert [c["id"] for c in listed] == [conversation_id]
    blocked = await pg_client.post(
        f"/api/conversations/{conversation_id}/messages", json={"body": "Halo"}
    )
    assert blocked.status_code == 409
    assert "resolved" in blocked.json()["detail"]

    reopened = await pg_client.post(f"/api/conversations/{conversation_id}/reopen")

    assert reopened.json()["status"] == "open"
    assert [c["id"] for c in await _open(pg_client)] == [conversation_id]


async def test_reopen_is_refused_when_the_guest_has_a_newer_conversation(pg_client) -> None:
    await start_workspace(pg_client)
    old_id = (await guest_says(pg_client, "Halo"))["conversation_id"]
    await pg_client.post(f"/api/conversations/{old_id}/resolve")
    await guest_says(pg_client, "Halo lagi")

    response = await pg_client.post(f"/api/conversations/{old_id}/reopen")

    assert response.status_code == 409
    assert "newer open conversation" in response.json()["detail"]
    assert (await pg_client.get(f"/api/conversations/{old_id}")).json()["status"] == "resolved"


@pytest.mark.parametrize(
    ("method", "suffix"),
    [
        ("get", ""),
        ("get", "/messages"),
        ("post", "/messages"),
        ("post", "/read"),
        ("post", "/resolve"),
        ("post", "/reopen"),
    ],
)
async def test_unknown_conversation_is_404_with_its_own_message(pg_client, method, suffix) -> None:
    await start_workspace(pg_client)
    url = f"/api/conversations/00000000-0000-4000-8000-000000000000{suffix}"
    kwargs = {"json": {"body": "x"}} if (method, suffix) == ("post", "/messages") else {}

    response = await getattr(pg_client, method)(url, **kwargs)

    assert response.status_code == 404
    assert response.json() == {"detail": "Conversation not found"}


async def test_malformed_conversation_id_is_rejected(pg_client) -> None:
    await start_workspace(pg_client)

    assert (await pg_client.get("/api/conversations/not-a-uuid")).status_code == 422


# ---- behaviours added after review -------------------------------------------------


def test_reply_window_closes_exactly_at_expiry() -> None:
    from app.models.tenant import Conversation
    from app.services.inbox import reply_block_reason

    now = dt.datetime(2026, 11, 20, 10, 0, tzinfo=dt.UTC)

    def conversation(expires: dt.datetime | None, status: str = "open") -> Conversation:
        return Conversation(status=status, service_window_expires_at=expires)

    assert reply_block_reason(conversation(now + dt.timedelta(seconds=1)), now) is None
    assert reply_block_reason(conversation(now), now) == "window_closed"
    assert reply_block_reason(conversation(None), now) == "window_closed"
    assert (
        reply_block_reason(conversation(now + dt.timedelta(hours=1), "resolved"), now) == "resolved"
    )


async def test_provider_crash_keeps_the_reply_as_failed(pg_client, monkeypatch) -> None:
    class CrashingProvider:
        async def send_text(self, *, sender: str, recipient: str, body: str) -> SendResult:
            raise ConnectionError("provider unreachable")

    await start_workspace(pg_client)
    conversation_id = (await guest_says(pg_client, "Halo"))["conversation_id"]
    monkeypatch.setitem(provider_module._PROVIDERS, "simulator", CrashingProvider())

    response = await pg_client.post(
        f"/api/conversations/{conversation_id}/messages", json={"body": "Halo juga"}
    )

    assert response.status_code == 201
    assert response.json()["status"] == "failed"
    assert response.json()["error"] == "The message could not be sent. Please try again."
    thread = (await pg_client.get(f"/api/conversations/{conversation_id}/messages")).json()
    assert [(m["body"], m["status"]) for m in thread] == [
        ("Halo", "received"),
        ("Halo juga", "failed"),
    ]


async def test_reply_is_recorded_before_the_provider_is_called(
    pg_client, pg_session_factory, monkeypatch
) -> None:
    """A message the guest received always has a record, even if we crash afterwards."""
    seen: list[tuple[str, str]] = []

    class InspectingProvider:
        async def send_text(self, *, sender: str, recipient: str, body: str) -> SendResult:
            async with pg_session_factory() as other:  # a different connection: committed data only
                rows = await other.execute(
                    text("SELECT body, status FROM message WHERE body = :b"), {"b": body}
                )
                seen.extend((row[0], row[1]) for row in rows)
            return SendResult(accepted=True, provider_message_id="wamid-1")

    await start_workspace(pg_client)
    conversation_id = (await guest_says(pg_client, "Halo"))["conversation_id"]
    monkeypatch.setitem(provider_module._PROVIDERS, "simulator", InspectingProvider())

    response = await pg_client.post(
        f"/api/conversations/{conversation_id}/messages", json={"body": "tercatat dulu"}
    )

    assert seen == [("tercatat dulu", "queued")]
    assert response.json()["status"] == "sent"


async def test_cursor_without_timezone_is_rejected(pg_client) -> None:
    await start_workspace(pg_client)

    response = await pg_client.get(
        "/api/conversations",
        params={"cursor": "2026-11-20T10:00:00|00000000-0000-4000-8000-000000000000"},
    )

    assert response.status_code == 422


async def test_incremental_fetch_never_misses_a_message(pg_client, pg_session) -> None:
    """Message times never go backwards in a conversation, so `after` paging is complete."""
    await start_workspace(pg_client)
    conversation_id = (await guest_says(pg_client, "satu"))["conversation_id"]
    # Pretend the last message was stored by a server whose clock is ahead of ours.
    await pg_session.execute(
        text(
            "UPDATE message SET created_at = now() + interval '1 hour' WHERE conversation_id = :c;"
        ),
        {"c": conversation_id},
    )
    await pg_session.execute(
        text("UPDATE conversation SET last_message_at = now() + interval '1 hour' WHERE id = :c"),
        {"c": conversation_id},
    )
    await pg_session.commit()
    first = (await pg_client.get(f"/api/conversations/{conversation_id}/messages")).json()

    await guest_says(pg_client, "dua")
    await pg_client.post(f"/api/conversations/{conversation_id}/messages", json={"body": "tiga"})
    newer = (
        await pg_client.get(
            f"/api/conversations/{conversation_id}/messages", params={"after": first[-1]["id"]}
        )
    ).json()

    assert [m["body"] for m in newer] == ["dua", "tiga"]
    everything = (await pg_client.get(f"/api/conversations/{conversation_id}/messages")).json()
    assert [m["body"] for m in everything] == ["satu", "dua", "tiga"]


async def test_reply_racing_inbound_keeps_counts_and_order_consistent(
    pg_client, pg_session, pg_session_factory
) -> None:
    import asyncio
    import uuid

    from sqlmodel import select

    from app.models.tenant import Conversation, Message, MessagingAccount
    from app.services.inbound import InboundMessage, receive_inbound

    workspace = await start_workspace(pg_client)
    conversation_id = (await guest_says(pg_client, "awal"))["conversation_id"]
    account = (
        await pg_session.exec(
            select(MessagingAccount).where(MessagingAccount.tenant_id == workspace["tenant"]["id"])
        )
    ).one()

    async def inbound(index: int) -> None:
        async with pg_session_factory() as session:
            await receive_inbound(
                session,
                account,
                InboundMessage(
                    from_phone="+6281234567890",
                    body=f"masuk {index}",
                    provider_message_id=f"wamid-{uuid.uuid4().hex}",
                ),
            )

    async def reply(index: int) -> None:
        response = await pg_client.post(
            f"/api/conversations/{conversation_id}/messages", json={"body": f"balas {index}"}
        )
        assert response.status_code == 201

    await asyncio.gather(*(inbound(i) for i in range(4)), *(reply(i) for i in range(3)))

    messages = (
        await pg_session.exec(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at, Message.id)
        )
    ).all()
    assert len(messages) == 8
    times = [m.created_at for m in messages]
    assert len(set(times)) == len(times), "two messages share a timestamp"
    conversation = (
        await pg_session.exec(select(Conversation).where(Conversation.id == conversation_id))
    ).one()
    assert conversation.last_message_at == times[-1]
    # unread = inbound messages stored after the last reply
    last_reply = max(i for i, m in enumerate(messages) if m.direction == "outbound")
    assert conversation.unread_count == len(messages) - 1 - last_reply


async def test_spam_conversations_do_not_count_as_unread(pg_client, pg_session) -> None:
    await start_workspace(pg_client)
    conversation_id = (await guest_says(pg_client, "promo!!!"))["conversation_id"]
    await pg_session.execute(
        text("UPDATE conversation SET status = 'spam' WHERE id = :c"), {"c": conversation_id}
    )
    await pg_session.commit()

    assert (await pg_client.get("/api/inbox/summary")).json() == {"unread_conversations": 0}
    assert (await pg_client.get("/api/conversations")).json()["items"] == []
