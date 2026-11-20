"""Inbound guest messages: guest and conversation matching, idempotency, races."""

import asyncio
import uuid

import pytest
from sqlmodel import col, select

from app.models.tenant import Conversation, Guest, Message, MessagingAccount
from app.services.inbound import InboundMessage, receive_inbound
from tests.pg.conftest import guest_says, start_workspace

pytestmark = pytest.mark.integration


async def _rows(pg_session, model, tenant_id: str) -> list:
    return list(
        (await pg_session.exec(select(model).where(col(model.tenant_id) == tenant_id))).all()
    )


async def test_onboarding_creates_a_simulated_whatsapp_account(pg_client, pg_session) -> None:
    workspace = await start_workspace(pg_client)

    accounts = await _rows(pg_session, MessagingAccount, workspace["tenant"]["id"])

    assert [(a.channel_kind, a.provider, a.status) for a in accounts] == [
        ("whatsapp", "simulator", "active")
    ]
    assert str(accounts[0].property_id) == workspace["property"]["id"]


async def test_older_workspace_gets_its_account_on_first_message(pg_client, pg_session) -> None:
    workspace = await start_workspace(pg_client)
    for account in await _rows(pg_session, MessagingAccount, workspace["tenant"]["id"]):
        await pg_session.delete(account)
    await pg_session.commit()

    await guest_says(pg_client, "Halo")

    assert len(await _rows(pg_session, MessagingAccount, workspace["tenant"]["id"])) == 1


async def test_first_message_creates_guest_and_conversation(pg_client, pg_session) -> None:
    workspace = await start_workspace(pg_client)
    tenant_id = workspace["tenant"]["id"]

    result = await guest_says(pg_client, "Halo, ada kamar?", phone="0812 3456 7890", name="Budi")

    assert result["duplicate"] is False
    guests = await _rows(pg_session, Guest, tenant_id)
    conversations = await _rows(pg_session, Conversation, tenant_id)
    messages = await _rows(pg_session, Message, tenant_id)
    assert [(g.full_name, g.whatsapp_phone) for g in guests] == [("Budi", "+6281234567890")]
    assert len(conversations) == 1
    conversation = conversations[0]
    assert conversation.external_thread_id == "+6281234567890"
    assert conversation.guest_id == guests[0].id
    assert conversation.status == "open"
    assert conversation.unread_count == 1
    assert conversation.service_window_expires_at - conversation.last_inbound_at
    assert (conversation.service_window_expires_at - conversation.last_inbound_at).days == 1
    assert [(m.direction, m.sender_kind, m.status, m.body) for m in messages] == [
        ("inbound", "guest", "received", "Halo, ada kamar?")
    ]


async def test_second_message_reuses_guest_and_conversation(pg_client, pg_session) -> None:
    workspace = await start_workspace(pg_client)

    first = await guest_says(pg_client, "Halo")
    second = await guest_says(pg_client, "Untuk 2 malam")

    assert first["conversation_id"] == second["conversation_id"]
    tenant_id = workspace["tenant"]["id"]
    assert len(await _rows(pg_session, Guest, tenant_id)) == 1
    conversation = (await _rows(pg_session, Conversation, tenant_id))[0]
    assert conversation.unread_count == 2


async def test_guest_without_a_name_is_shown_by_number(pg_client, pg_session) -> None:
    workspace = await start_workspace(pg_client)

    await guest_says(pg_client, "Halo", name=None)

    guest = (await _rows(pg_session, Guest, workspace["tenant"]["id"]))[0]
    assert guest.full_name == "+6281234567890"


async def test_different_numbers_get_separate_conversations(pg_client) -> None:
    await start_workspace(pg_client)

    first = await guest_says(pg_client, "Halo", phone="+6281111111111")
    second = await guest_says(pg_client, "Hi", phone="+6282222222222")

    assert first["conversation_id"] != second["conversation_id"]


async def test_message_after_resolve_opens_a_new_conversation(pg_client) -> None:
    await start_workspace(pg_client)
    first = await guest_says(pg_client, "Halo")
    await pg_client.post(f"/api/conversations/{first['conversation_id']}/resolve")

    second = await guest_says(pg_client, "Saya mau pesan lagi")

    assert second["conversation_id"] != first["conversation_id"]
    resolved = (await pg_client.get("/api/conversations?status=resolved")).json()["items"]
    assert [c["id"] for c in resolved] == [first["conversation_id"]]


@pytest.mark.parametrize("phone", ["12345", "not-a-number", "6281234567890"])
async def test_invalid_phone_is_rejected(pg_client, phone) -> None:
    await start_workspace(pg_client)

    response = await pg_client.post(
        "/api/simulator/whatsapp/inbound", json={"from_phone": phone, "body": "Halo"}
    )

    assert response.status_code == 422


async def test_repeated_provider_delivery_is_stored_once(
    pg_client, pg_session, pg_session_factory
) -> None:
    workspace = await start_workspace(pg_client)
    tenant_id = workspace["tenant"]["id"]
    account = (await _rows(pg_session, MessagingAccount, tenant_id))[0]
    inbound = InboundMessage(
        from_phone="+6281234567890", body="Halo", provider_message_id=f"wamid-{uuid.uuid4().hex}"
    )

    async with pg_session_factory() as session:
        first = await receive_inbound(session, account, inbound)
    async with pg_session_factory() as session:
        second = await receive_inbound(session, account, inbound)

    assert (first.duplicate, second.duplicate) == (False, True)
    assert second.message_id == first.message_id
    assert len(await _rows(pg_session, Message, tenant_id)) == 1
    assert (await _rows(pg_session, Conversation, tenant_id))[0].unread_count == 1


async def test_simultaneous_first_messages_open_one_conversation(
    pg_client, pg_session, pg_session_factory
) -> None:
    workspace = await start_workspace(pg_client)
    tenant_id = workspace["tenant"]["id"]
    account = (await _rows(pg_session, MessagingAccount, tenant_id))[0]

    async def deliver(index: int) -> None:
        async with pg_session_factory() as session:
            await receive_inbound(
                session,
                account,
                InboundMessage(
                    from_phone="+6289999999999",
                    body=f"pesan {index}",
                    provider_message_id=f"wamid-{uuid.uuid4().hex}",
                ),
            )

    await asyncio.gather(*(deliver(i) for i in range(6)))

    conversations = await _rows(pg_session, Conversation, tenant_id)
    assert len(conversations) == 1
    assert conversations[0].unread_count == 6
    assert len(await _rows(pg_session, Guest, tenant_id)) == 1
    assert len(await _rows(pg_session, Message, tenant_id)) == 6


async def test_simulator_is_not_available_when_switched_off(pg_client, monkeypatch) -> None:
    from app.config import settings

    await start_workspace(pg_client)
    monkeypatch.setattr(settings, "MESSAGING_SIMULATOR_ENABLED", False)

    response = await pg_client.post(
        "/api/simulator/whatsapp/inbound", json={"from_phone": "+6281234567890", "body": "Halo"}
    )

    assert response.status_code == 404
    assert (await pg_client.get("/api/workspace")).json()["simulator_enabled"] is False


async def test_simulator_requires_sign_in(pg_client) -> None:
    response = await pg_client.post(
        "/api/simulator/whatsapp/inbound", json={"from_phone": "+6281234567890", "body": "Halo"}
    )

    assert response.status_code == 401


async def test_simultaneous_first_use_creates_one_messaging_account(
    pg_client, pg_session, pg_session_factory
) -> None:
    from app.models.tenant import Property
    from app.services.messaging_accounts import get_or_create_whatsapp_account

    workspace = await start_workspace(pg_client)
    tenant_id = workspace["tenant"]["id"]
    for account in await _rows(pg_session, MessagingAccount, tenant_id):
        await pg_session.delete(account)
    await pg_session.commit()
    prop = (await _rows(pg_session, Property, tenant_id))[0]

    async def ensure() -> str:
        async with pg_session_factory() as session:
            account = await get_or_create_whatsapp_account(session, prop)
            await session.commit()
            return str(account.id)

    ids = await asyncio.gather(*(ensure() for _ in range(5)))

    assert len(set(ids)) == 1
    assert len(await _rows(pg_session, MessagingAccount, tenant_id)) == 1


async def test_provider_timestamp_is_kept_but_does_not_order_the_thread(
    pg_client, pg_session, pg_session_factory
) -> None:
    import datetime as dt

    workspace = await start_workspace(pg_client)
    tenant_id = workspace["tenant"]["id"]
    account = (await _rows(pg_session, MessagingAccount, tenant_id))[0]
    await guest_says(pg_client, "pertama")
    yesterday = dt.datetime.now(dt.UTC) - dt.timedelta(days=1)

    async with pg_session_factory() as session:
        await receive_inbound(
            session,
            account,
            InboundMessage(
                from_phone="+6281234567890",
                body="terlambat dikirim provider",
                provider_message_id=f"wamid-{uuid.uuid4().hex}",
                received_at=yesterday,
            ),
        )

    messages = sorted(await _rows(pg_session, Message, tenant_id), key=lambda m: m.created_at)
    assert [m.body for m in messages] == ["pertama", "terlambat dikirim provider"]
    assert messages[1].sent_at == yesterday
