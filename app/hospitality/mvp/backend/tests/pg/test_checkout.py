"""The public pay page: no sign-in, minimal data, payment instructions."""

import httpx
import pytest
from sqlalchemy import text
from sqlmodel import select

from app.main import app
from app.models.tenant import Payment
from app.payments import gateway as gateway_module
from app.payments.gateway import ChargeInstructions, ChargeRequest, GatewayError
from app.payments.tokens import new_token
from tests.pg.conftest import guest_says, make_link, pay, start_workspace, token_of

pytestmark = pytest.mark.integration

NOT_FOUND = {"detail": "Payment link not found"}


@pytest.fixture
async def guest(_pg_override):
    """A browser with no session at all — the guest opening the link."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


async def test_guest_sees_the_link_without_signing_in(pg_client, guest) -> None:
    workspace = await start_workspace(pg_client, property_name="Villa Senja")
    created = await make_link(pg_client, amount=500000, total_amount=1700000)

    response = await guest.get(f"/api/pay/{token_of(created)}")

    assert response.status_code == 200
    page = response.json()
    assert page["property_name"] == "Villa Senja"
    assert page["description"] == "DP Villa 2 malam"
    assert (page["amount"], page["total_amount"], page["currency"]) == (
        "500000.00",
        "1700000.00",
        "IDR",
    )
    assert page["state"] == "pending"
    assert sorted(page["methods"]) == ["qris", "virtual_account"]
    assert page["banks"] == ["BCA", "Mandiri", "BNI", "BRI", "Permata"]
    assert page["instructions"] is None
    assert page["simulator_enabled"] is True
    assert workspace["tenant"]["id"] not in response.text


async def test_public_page_exposes_no_guest_details_or_ids(pg_client, guest) -> None:
    workspace = await start_workspace(pg_client)
    conversation_id = (
        await guest_says(pg_client, "Halo", phone="+6281234567890", name="Budi Santoso")
    )["conversation_id"]
    created = await make_link(pg_client, conversation_id=conversation_id)

    body = (await guest.get(f"/api/pay/{token_of(created)}")).text

    for secret in (
        "Budi",
        "6281234567890",
        workspace["tenant"]["id"],
        workspace["property"]["id"],
        created["link"]["id"],
        conversation_id,
    ):
        assert secret not in body


@pytest.mark.parametrize(
    "token",
    ["short", "a" * 42, "a" * 44, "a" * 42 + "!", "%27%20OR%201%3D1--" + "a" * 30],
)
async def test_malformed_tokens_get_the_same_404(guest, token) -> None:
    for response in (
        await guest.get(f"/api/pay/{token}"),
        await guest.post(f"/api/pay/{token}/payments", json={"method": "qris"}),
        await guest.post(f"/api/simulator/payments/{token}/pay"),
    ):
        assert response.status_code == 404
        assert response.json() == NOT_FOUND


async def test_unknown_but_well_formed_token_gets_the_same_404(pg_client, guest) -> None:
    await start_workspace(pg_client)
    await make_link(pg_client)

    response = await guest.get(f"/api/pay/{new_token()}")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


async def test_qris_instructions(pg_client, guest) -> None:
    await start_workspace(pg_client)
    token = token_of(await make_link(pg_client))

    response = await guest.post(f"/api/pay/{token}/payments", json={"method": "qris"})

    assert response.status_code == 201, response.text
    instructions = response.json()
    assert instructions["method"] == "qris"
    assert instructions["reference"].startswith("simpay-")
    assert (
        "SIMULATED-QRIS" in instructions["qris_payload"]
        and "IDR850000" in instructions["qris_payload"]
    )
    assert (instructions["va_bank"], instructions["va_number"]) == (None, None)
    assert (await guest.get(f"/api/pay/{token}")).json()["instructions"] == instructions


async def test_virtual_account_instructions(pg_client, guest) -> None:
    await start_workspace(pg_client)
    token = token_of(await make_link(pg_client))

    response = await guest.post(
        f"/api/pay/{token}/payments", json={"method": "virtual_account", "bank": "Mandiri"}
    )

    instructions = response.json()
    assert (instructions["method"], instructions["va_bank"]) == ("virtual_account", "Mandiri")
    assert len(instructions["va_number"]) == 16 and instructions["va_number"].isdigit()
    assert instructions["qris_payload"] is None


async def test_asking_again_returns_the_same_payment(pg_client, guest, pg_session) -> None:
    workspace = await start_workspace(pg_client)
    token = token_of(await make_link(pg_client))
    body = {"method": "virtual_account", "bank": "BCA"}

    first = (await guest.post(f"/api/pay/{token}/payments", json=body)).json()
    second = (await guest.post(f"/api/pay/{token}/payments", json=body)).json()
    other_bank = (
        await guest.post(
            f"/api/pay/{token}/payments", json={"method": "virtual_account", "bank": "BNI"}
        )
    ).json()

    assert first == second
    assert other_bank["va_number"] != first["va_number"]
    payments = (
        await pg_session.exec(select(Payment).where(Payment.tenant_id == workspace["tenant"]["id"]))
    ).all()
    assert len(payments) == 2
    assert {(p.status, p.amount) for p in payments} == {("pending", 850000)}


@pytest.mark.parametrize(
    "body",
    [
        {"method": "virtual_account"},
        {"method": "virtual_account", "bank": "Bank Fiktif"},
        {"method": "card"},
        {"method": "qris", "amount": 1},
        {},
    ],
)
async def test_invalid_payment_requests_are_rejected(pg_client, guest, body) -> None:
    await start_workspace(pg_client)
    token = token_of(await make_link(pg_client))

    assert (await guest.post(f"/api/pay/{token}/payments", json=body)).status_code == 422


async def test_method_not_allowed_for_the_link(pg_client, guest, pg_session) -> None:
    await start_workspace(pg_client)
    created = await make_link(pg_client)
    await pg_session.execute(
        text("UPDATE paymentlink SET allowed_methods = '{qris}' WHERE id = :i"),
        {"i": created["link"]["id"]},
    )
    await pg_session.commit()

    response = await guest.post(
        f"/api/pay/{token_of(created)}/payments", json={"method": "virtual_account", "bank": "BCA"}
    )

    assert response.status_code == 422
    assert "not available" in response.json()["detail"]


@pytest.mark.parametrize("final", ["paid", "expired", "cancelled"])
async def test_a_finished_link_takes_no_more_payments(pg_client, guest, pg_session, final) -> None:
    await start_workspace(pg_client)
    created = await make_link(pg_client)
    token = token_of(created)
    if final == "paid":
        await pay(guest, token)
    elif final == "expired":
        await pg_session.execute(
            text("UPDATE paymentlink SET expires_at = now() - interval '1 minute' WHERE id = :i"),
            {"i": created["link"]["id"]},
        )
        await pg_session.commit()
    else:
        await pg_client.post(f"/api/payment-links/{created['link']['id']}/cancel")

    response = await guest.post(f"/api/pay/{token}/payments", json={"method": "qris"})

    assert response.status_code == 409
    assert final in response.json()["detail"] or "already been paid" in response.json()["detail"]
    page = (await guest.get(f"/api/pay/{token}")).json()
    assert (page["state"], page["instructions"]) == (final, None)


async def test_gateway_fault_keeps_a_failed_attempt_and_can_be_retried(
    pg_client, guest, pg_session, monkeypatch
) -> None:
    class DownGateway:
        async def create_charge(self, request: ChargeRequest) -> ChargeInstructions:
            raise ConnectionError("gateway unreachable")

    workspace = await start_workspace(pg_client)
    token = token_of(await make_link(pg_client))
    real = gateway_module._GATEWAYS["simulator"]
    monkeypatch.setitem(gateway_module._GATEWAYS, "simulator", DownGateway())

    failed = await guest.post(f"/api/pay/{token}/payments", json={"method": "qris"})

    assert failed.status_code == 502
    assert "try again" in failed.json()["detail"]
    payments = (
        await pg_session.exec(select(Payment).where(Payment.tenant_id == workspace["tenant"]["id"]))
    ).all()
    assert [(p.status, p.failure_reason) for p in payments] == [("failed", "gateway_unavailable")]

    monkeypatch.setitem(gateway_module._GATEWAYS, "simulator", real)
    retried = await guest.post(f"/api/pay/{token}/payments", json={"method": "qris"})
    assert retried.status_code == 201


async def test_gateway_refusal_is_also_a_clean_502(pg_client, guest, monkeypatch) -> None:
    class RefusingGateway:
        async def create_charge(self, request: ChargeRequest) -> ChargeInstructions:
            raise GatewayError("merchant suspended")

    await start_workspace(pg_client)
    token = token_of(await make_link(pg_client))
    monkeypatch.setitem(gateway_module._GATEWAYS, "simulator", RefusingGateway())

    response = await guest.post(f"/api/pay/{token}/payments", json={"method": "qris"})

    assert response.status_code == 502
    assert "merchant suspended" not in response.text


async def test_older_workspace_gets_its_gateway_account_on_first_payment(
    pg_client, guest, pg_session
) -> None:
    workspace = await start_workspace(pg_client)
    await pg_session.execute(
        text("DELETE FROM paymentgatewayaccount WHERE tenant_id = :t"),
        {"t": workspace["tenant"]["id"]},
    )
    await pg_session.commit()
    token = token_of(await make_link(pg_client))

    response = await guest.post(f"/api/pay/{token}/payments", json={"method": "qris"})

    assert response.status_code == 201
    count = (
        await pg_session.execute(
            text("SELECT count(*) FROM paymentgatewayaccount WHERE tenant_id = :t"),
            {"t": workspace["tenant"]["id"]},
        )
    ).scalar_one()
    assert count == 1
