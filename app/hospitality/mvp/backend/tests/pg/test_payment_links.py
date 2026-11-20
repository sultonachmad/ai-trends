"""Payment links, staff side: create, send to chat, list, read, cancel."""

import datetime as dt

import pytest
from sqlalchemy import text
from sqlmodel import select

from app.models.tenant import PaymentGatewayAccount, PaymentLink
from app.payments.tokens import fingerprint
from tests.pg.conftest import guest_says, make_link, pay, start_workspace, token_of

pytestmark = pytest.mark.integration


async def _expire(pg_session, link_id: str) -> None:
    await pg_session.execute(
        text("UPDATE paymentlink SET expires_at = now() - interval '1 minute' WHERE id = :i"),
        {"i": link_id},
    )
    await pg_session.commit()


async def test_requires_sign_in(pg_client) -> None:
    assert (await pg_client.get("/api/payment-links")).status_code == 401
    assert (await pg_client.post("/api/payment-links", json={})).status_code == 401


async def test_onboarding_creates_a_simulated_gateway_account(pg_client, pg_session) -> None:
    workspace = await start_workspace(pg_client)

    accounts = (
        await pg_session.exec(
            select(PaymentGatewayAccount).where(
                PaymentGatewayAccount.tenant_id == workspace["tenant"]["id"]
            )
        )
    ).all()

    assert [(a.provider, a.status, a.is_default) for a in accounts] == [
        ("simulator", "active", True)
    ]
    assert sorted(accounts[0].supported_methods) == ["qris", "virtual_account"]


async def test_create_standalone_link_with_defaults(pg_client, pg_session) -> None:
    await start_workspace(pg_client)
    before = dt.datetime.now(dt.UTC)

    created = await make_link(pg_client)

    link = created["link"]
    assert link["state"] == "pending"
    assert link["amount"] == "850000.00"
    assert link["total_amount"] is None
    assert link["currency"] == "IDR"
    assert link["description"] == "DP Villa 2 malam"
    assert (link["guest"], link["conversation_id"], link["sent_to_chat"]) == (None, None, False)
    assert (created["sent_to_chat"], created["not_sent_reason"]) == (False, None)
    expires = dt.datetime.fromisoformat(link["expires_at"])
    assert dt.timedelta(hours=23, minutes=59) < expires - before < dt.timedelta(hours=24, minutes=1)
    # the url carries the token; the database holds only its fingerprint
    token = token_of(created)
    assert created["url"] == f"https://app.test/pay/{token}"
    stored = (await pg_session.exec(select(PaymentLink).where(PaymentLink.id == link["id"]))).one()
    assert stored.token_hash == fingerprint(token)
    assert token not in stored.token_hash
    assert sorted(stored.allowed_methods) == ["qris", "virtual_account"]


async def test_down_payment_and_custom_expiry(pg_client) -> None:
    await start_workspace(pg_client)
    before = dt.datetime.now(dt.UTC)

    created = await make_link(pg_client, amount=500000, total_amount=1700000, expires_in_hours=72)

    assert created["link"]["total_amount"] == "1700000.00"
    expires = dt.datetime.fromisoformat(created["link"]["expires_at"])
    assert dt.timedelta(hours=71, minutes=59) < expires - before < dt.timedelta(hours=72, minutes=1)


async def test_property_settings_drive_default_expiry_and_limits(pg_client, pg_session) -> None:
    workspace = await start_workspace(pg_client)
    await pg_session.execute(
        text(
            'UPDATE property SET settings = \'{"business": {"payment_link_expiry_hours": 2, '
            '"payment_link_max_amount_idr": 1000000}}\' WHERE id = :p'
        ),
        {"p": workspace["property"]["id"]},
    )
    await pg_session.commit()
    before = dt.datetime.now(dt.UTC)

    created = await make_link(pg_client, amount=1000000)
    too_much = await pg_client.post(
        "/api/payment-links", json={"amount": 1000001, "description": "x"}
    )

    expires = dt.datetime.fromisoformat(created["link"]["expires_at"])
    assert expires - before < dt.timedelta(hours=2, minutes=1)
    assert too_much.status_code == 422
    assert "Rp 10.000" in too_much.json()["detail"] and "Rp 1.000.000" in too_much.json()["detail"]


@pytest.mark.parametrize(
    "payload",
    [
        {"amount": 9999, "description": "x"},
        {"amount": 500000001, "description": "x"},
        {"amount": 0, "description": "x"},
        {"amount": -5, "description": "x"},
        {"amount": 850000.5, "description": "x"},
        {"amount": "abc", "description": "x"},
        {"amount": 850000},
        {"amount": 850000, "description": "   "},
        {"amount": 850000, "description": "d" * 201},
        {"amount": 850000, "description": "x", "total_amount": 100000},
        {"amount": 850000, "description": "x", "expires_in_hours": 0},
        {"amount": 850000, "description": "x", "expires_in_hours": 2161},
        {"amount": 850000, "description": "x", "status": "paid"},
        {"amount": 850000, "description": "x", "tenant_id": "00000000-0000-4000-8000-000000000000"},
    ],
)
async def test_invalid_input_is_rejected(pg_client, payload) -> None:
    await start_workspace(pg_client)

    response = await pg_client.post("/api/payment-links", json=payload)

    assert response.status_code == 422, response.text
    assert (await pg_client.get("/api/payment-links")).json()["items"] == []


async def test_link_from_a_conversation_is_sent_into_the_thread(pg_client) -> None:
    await start_workspace(pg_client)
    conversation_id = (await guest_says(pg_client, "Mau booking"))["conversation_id"]

    created = await make_link(
        pg_client, amount=500000, total_amount=1700000, conversation_id=conversation_id
    )

    assert (created["sent_to_chat"], created["not_sent_reason"]) == (True, None)
    assert created["link"]["sent_to_chat"] is True
    assert created["link"]["conversation_id"] == conversation_id
    assert created["link"]["guest"]["name"] == "Budi"
    thread = (await pg_client.get(f"/api/conversations/{conversation_id}/messages")).json()
    body = thread[-1]["body"]
    assert (thread[-1]["direction"], thread[-1]["status"]) == ("outbound", "sent")
    assert created["url"] in body
    assert "DP Rp 500.000 dari total Rp 1.700.000" in body
    assert "DP Villa 2 malam" in body
    assert "Berlaku sampai" in body


@pytest.mark.parametrize(
    ("blocker", "reason"), [("resolved", "resolved"), ("window", "window_closed")]
)
async def test_link_is_created_even_when_it_cannot_be_sent(
    pg_client, pg_session, blocker, reason
) -> None:
    await start_workspace(pg_client)
    conversation_id = (await guest_says(pg_client, "Halo"))["conversation_id"]
    if blocker == "resolved":
        await pg_client.post(f"/api/conversations/{conversation_id}/resolve")
    else:
        await pg_session.execute(
            text(
                "UPDATE conversation SET service_window_expires_at = now() - interval '1 minute' "
                "WHERE id = :c"
            ),
            {"c": conversation_id},
        )
        await pg_session.commit()

    created = await make_link(pg_client, conversation_id=conversation_id)

    assert (created["sent_to_chat"], created["not_sent_reason"]) == (False, reason)
    assert created["link"]["state"] == "pending"
    assert created["link"]["sent_to_chat"] is False
    assert (await pg_client.get(f"/api/pay/{token_of(created)}")).status_code == 200
    thread = (await pg_client.get(f"/api/conversations/{conversation_id}/messages")).json()
    assert [m["body"] for m in thread] == ["Halo"]


async def test_unknown_conversation_is_404_and_nothing_is_created(pg_client) -> None:
    await start_workspace(pg_client)

    response = await pg_client.post(
        "/api/payment-links",
        json={
            "amount": 850000,
            "description": "x",
            "conversation_id": "00000000-0000-4000-8000-000000000000",
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Conversation not found"}
    assert (await pg_client.get("/api/payment-links")).json()["items"] == []


async def test_list_newest_first_with_paging_and_no_secrets(pg_client) -> None:
    await start_workspace(pg_client)
    tokens = []
    for index in range(5):
        created = await make_link(pg_client, description=f"Link {index}")
        tokens.append(token_of(created))

    first = (await pg_client.get("/api/payment-links?limit=2")).json()
    second = (
        await pg_client.get(
            "/api/payment-links", params={"limit": 2, "cursor": first["next_cursor"]}
        )
    ).json()
    third = (
        await pg_client.get(
            "/api/payment-links", params={"limit": 2, "cursor": second["next_cursor"]}
        )
    ).json()

    names = [i["description"] for page in (first, second, third) for i in page["items"]]
    assert names == ["Link 4", "Link 3", "Link 2", "Link 1", "Link 0"]
    assert third["next_cursor"] is None
    everything = (await pg_client.get("/api/payment-links")).text
    assert not any(token in everything for token in tokens)
    assert "token" not in everything and "url" not in everything


async def test_filter_by_state_uses_the_expiry_time(pg_client, pg_session) -> None:
    await start_workspace(pg_client)
    pending = await make_link(pg_client, description="pending")
    paid = await make_link(pg_client, description="paid")
    expired = await make_link(pg_client, description="expired")
    cancelled = await make_link(pg_client, description="cancelled")
    assert (await pay(pg_client, token_of(paid))).status_code == 200
    await _expire(pg_session, expired["link"]["id"])
    await pg_client.post(f"/api/payment-links/{cancelled['link']['id']}/cancel")

    async def names(state: str) -> list[str]:
        items = (await pg_client.get(f"/api/payment-links?state={state}")).json()["items"]
        assert all(i["state"] == state for i in items) or state == "all"
        return sorted(i["description"] for i in items)

    assert await names("pending") == ["pending"]
    assert await names("paid") == ["paid"]
    assert await names("expired") == ["expired"]
    assert await names("cancelled") == ["cancelled"]
    assert len(await names("all")) == 4
    assert pending["link"]["state"] == "pending"


@pytest.mark.parametrize(
    "query",
    [
        "limit=0",
        "limit=51",
        "state=refunded",
        "cursor=garbage",
        "cursor=2026-11-20T10:00:00|00000000-0000-4000-8000-000000000000",
    ],
)
async def test_bad_list_parameters_are_rejected(pg_client, query) -> None:
    await start_workspace(pg_client)

    assert (await pg_client.get(f"/api/payment-links?{query}")).status_code == 422


async def test_read_shows_how_a_link_was_paid(pg_client) -> None:
    await start_workspace(pg_client)
    created = await make_link(pg_client)
    await pay(pg_client, token_of(created), "virtual_account", "BCA")

    link = (await pg_client.get(f"/api/payment-links/{created['link']['id']}")).json()

    assert link["state"] == "paid"
    assert link["paid_via"] == "Virtual account BCA"
    assert link["paid_at"] is not None


async def test_cancel_a_pending_link(pg_client) -> None:
    await start_workspace(pg_client)
    created = await make_link(pg_client)
    token = token_of(created)
    await pg_client.post(f"/api/pay/{token}/payments", json={"method": "qris"})

    cancelled = await pg_client.post(f"/api/payment-links/{created['link']['id']}/cancel")

    assert cancelled.status_code == 200
    assert cancelled.json()["state"] == "cancelled"
    assert (await pg_client.get(f"/api/pay/{token}")).json()["state"] == "cancelled"
    assert (await pg_client.post(f"/api/simulator/payments/{token}/pay")).status_code == 409


@pytest.mark.parametrize("final", ["paid", "expired", "cancelled"])
async def test_only_a_pending_link_can_be_cancelled(pg_client, pg_session, final) -> None:
    await start_workspace(pg_client)
    created = await make_link(pg_client)
    link_id = created["link"]["id"]
    if final == "paid":
        await pay(pg_client, token_of(created))
    elif final == "expired":
        await _expire(pg_session, link_id)
    else:
        await pg_client.post(f"/api/payment-links/{link_id}/cancel")

    response = await pg_client.post(f"/api/payment-links/{link_id}/cancel")

    assert response.status_code == 409
    assert final in response.json()["detail"]
    assert (await pg_client.get(f"/api/payment-links/{link_id}")).json()["state"] == final


async def test_expired_link_reads_as_expired_before_anything_writes_it(
    pg_client, pg_session
) -> None:
    await start_workspace(pg_client)
    created = await make_link(pg_client)
    await _expire(pg_session, created["link"]["id"])

    stored = (
        await pg_session.exec(select(PaymentLink).where(PaymentLink.id == created["link"]["id"]))
    ).one()
    assert stored.status == "active"  # nothing has written the lapse yet
    assert (await pg_client.get(f"/api/payment-links/{created['link']['id']}")).json()[
        "state"
    ] == "expired"
    assert (await pg_client.get(f"/api/pay/{token_of(created)}")).json()["state"] == "expired"


@pytest.mark.parametrize(("method", "suffix"), [("get", ""), ("post", "/cancel")])
async def test_unknown_link_is_404_with_its_own_message(pg_client, method, suffix) -> None:
    await start_workspace(pg_client)

    response = await getattr(pg_client, method)(
        f"/api/payment-links/00000000-0000-4000-8000-000000000000{suffix}"
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Payment link not found"}


async def test_dashboard_usage_counts_created_links(pg_client) -> None:
    await start_workspace(pg_client)
    await make_link(pg_client)
    await make_link(pg_client)

    usage = (await pg_client.get("/api/workspace")).json()["usage"]

    assert (usage["payment_links_used"], usage["payment_links_limit"]) == (2, 30)
