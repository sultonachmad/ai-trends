"""Behaviours added after the security and code reviews of payment links."""

import asyncio
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlmodel import select

from app.models.tenant import Payment, PaymentLink
from app.payments import gateway as gateway_module
from app.payments.gateway import ChargeInstructions, ChargeRequest
from app.payments.tokens import fingerprint
from app.services import checkout, inbox
from app.services.gateway_events import PAID_EVENT, GatewayEvent, handle_gateway_event
from tests.pg.conftest import guest_says, make_link, pay, start_workspace, token_of

pytestmark = pytest.mark.integration

TOKEN_HEADERS = {
    "cache-control": "no-store",
    "referrer-policy": "no-referrer",
    "x-robots-tag": "noindex, nofollow",
}


async def _payments(pg_session, tenant_id: str) -> list[Payment]:
    rows = await pg_session.exec(
        select(Payment)
        .where(Payment.tenant_id == tenant_id)
        .order_by(Payment.created_at)
        .execution_options(populate_existing=True)
    )
    return list(rows.all())


# ---- the public lookup must not depend on the owner being a superuser -----------------


async def test_lookup_works_for_an_owner_bound_by_row_level_security(
    pg_client, pg_session_factory
) -> None:
    """FORCE RLS binds the table owner. A non-superuser owner needs the lookup policy."""
    workspace = await start_workspace(pg_client)
    token_hash = fingerprint(token_of(await make_link(pg_client)))
    owner = f"hosp_owner_{uuid.uuid4().hex[:8]}"

    async with pg_session_factory() as session:
        await session.execute(text(f"CREATE ROLE {owner} NOSUPERUSER NOBYPASSRLS NOLOGIN"))
        await session.execute(text(f"GRANT SELECT ON paymentlink TO {owner}"))
        await session.commit()
        try:
            # without a policy naming it, an RLS-bound role finds nothing …
            await session.execute(text(f"SET LOCAL ROLE {owner}"))
            hidden = (
                await session.execute(
                    text("SELECT tenant_id FROM paymentlink WHERE token_hash = :h"),
                    {"h": token_hash},
                )
            ).scalar_one_or_none()
            await session.rollback()
            # … and with the same policy the migration gives the real owner, it does.
            await session.execute(
                text(
                    f"CREATE POLICY probe_lookup ON paymentlink FOR SELECT TO {owner} USING (true)"
                )
            )
            await session.execute(text(f"SET LOCAL ROLE {owner}"))
            found = (
                await session.execute(
                    text("SELECT tenant_id FROM paymentlink WHERE token_hash = :h"),
                    {"h": token_hash},
                )
            ).scalar_one_or_none()
            await session.rollback()
        finally:
            await session.rollback()
            await session.execute(text("DROP POLICY IF EXISTS probe_lookup ON paymentlink"))
            await session.execute(text(f"REVOKE ALL ON paymentlink FROM {owner}"))
            await session.execute(text(f"DROP ROLE {owner}"))
            await session.commit()

    assert hidden is None
    assert str(found) == workspace["tenant"]["id"]


async def test_migration_gives_the_table_owner_the_lookup_policy(pg_session) -> None:
    row = (
        await pg_session.execute(
            text(
                "SELECT cmd, roles::text, qual FROM pg_policies "
                "WHERE tablename = 'paymentlink' AND policyname = 'payment_link_lookup'"
            )
        )
    ).one()
    owner = (
        await pg_session.execute(
            text("SELECT tableowner FROM pg_tables WHERE tablename = 'paymentlink'")
        )
    ).scalar_one()

    assert row[0] == "SELECT"
    assert row[1] == "{" + owner + "}"
    assert row[2] == "true"


# ---- token paths: no caching, no referrer, no indexing --------------------------------


async def test_token_paths_send_privacy_headers_on_success_and_errors(pg_client) -> None:
    await start_workspace(pg_client)
    token = token_of(await make_link(pg_client))

    responses = [
        await pg_client.get(f"/api/pay/{token}"),
        await pg_client.get("/api/pay/" + "x" * 43),  # 404
        await pg_client.post(f"/api/pay/{token}/payments", json={"method": "card"}),  # 422
        await pg_client.post(f"/api/simulator/payments/{token}/pay"),  # 409
    ]

    assert [r.status_code for r in responses] == [200, 404, 422, 409]
    for response in responses:
        for name, value in TOKEN_HEADERS.items():
            assert response.headers[name] == value
    assert "referrer-policy" not in (await pg_client.get("/api/health")).headers


# ---- payment attempts -----------------------------------------------------------------


async def test_simultaneous_requests_for_one_method_create_one_payment(
    pg_client, pg_session
) -> None:
    workspace = await start_workspace(pg_client)
    token = token_of(await make_link(pg_client))
    body = {"method": "virtual_account", "bank": "BCA"}

    responses = await asyncio.gather(
        *(pg_client.post(f"/api/pay/{token}/payments", json=body) for _ in range(5))
    )

    assert [r.status_code for r in responses] == [201] * 5
    assert len({r.json()["va_number"] for r in responses}) == 1
    payments = await _payments(pg_session, workspace["tenant"]["id"])
    assert [(p.method, p.status) for p in payments] == [("virtual_account", "pending")]


async def test_failed_attempts_are_capped_per_link(pg_client, pg_session, monkeypatch) -> None:
    class DownGateway:
        async def create_charge(self, request: ChargeRequest) -> ChargeInstructions:
            raise ConnectionError("gateway unreachable")

    workspace = await start_workspace(pg_client)
    token = token_of(await make_link(pg_client))
    monkeypatch.setitem(gateway_module._GATEWAYS, "simulator", DownGateway())
    monkeypatch.setattr(checkout, "MAX_ATTEMPTS_PER_LINK", 3)

    statuses = [
        (await pg_client.post(f"/api/pay/{token}/payments", json={"method": "qris"})).status_code
        for _ in range(5)
    ]

    assert statuses == [502, 502, 502, 429, 429]
    assert len(await _payments(pg_session, workspace["tenant"]["id"])) == 3


# ---- money for a link that is no longer payable ---------------------------------------


async def test_late_payment_is_visible_to_staff_and_the_lapse_is_written(
    pg_client, pg_session, pg_session_factory
) -> None:
    workspace = await start_workspace(pg_client)
    created = await make_link(pg_client)
    link_id, token = created["link"]["id"], token_of(created)
    qris = (await pg_client.post(f"/api/pay/{token}/payments", json={"method": "qris"})).json()
    await pg_client.post(
        f"/api/pay/{token}/payments", json={"method": "virtual_account", "bank": "BNI"}
    )
    payments = await _payments(pg_session, workspace["tenant"]["id"])
    await pg_session.execute(
        text("UPDATE paymentlink SET expires_at = now() - interval '1 minute' WHERE id = :i"),
        {"i": link_id},
    )
    await pg_session.commit()

    async with pg_session_factory() as session:
        outcome = await handle_gateway_event(
            session,
            payments[0].tenant_id,
            payments[0].gateway_account_id,
            GatewayEvent(
                gateway_event_id=f"evt-{uuid.uuid4().hex}",
                event_type=PAID_EVENT,
                gateway_reference=qris["reference"],
                amount=Decimal("850000"),
                signature_valid=True,
            ),
        )

    assert (outcome.result, outcome.reason) == ("ignored", "link_expired")
    staff_view = (await pg_client.get(f"/api/payment-links/{link_id}")).json()
    assert (staff_view["state"], staff_view["needs_refund_review"]) == ("expired", True)
    assert staff_view["paid_via"] is None
    listed = (await pg_client.get("/api/payment-links?state=expired")).json()["items"]
    assert [i["needs_refund_review"] for i in listed] == [True]
    stored = (
        await pg_session.exec(
            select(PaymentLink)
            .where(PaymentLink.id == link_id)
            .execution_options(populate_existing=True)
        )
    ).one()
    assert stored.status == "expired"
    statuses = sorted(
        (p.method, p.status) for p in await _payments(pg_session, workspace["tenant"]["id"])
    )
    assert statuses == [("qris", "captured"), ("virtual_account", "cancelled")]


async def test_a_normally_paid_link_needs_no_refund_review(pg_client) -> None:
    await start_workspace(pg_client)
    created = await make_link(pg_client)
    await pay(pg_client, token_of(created))

    link = (await pg_client.get(f"/api/payment-links/{created['link']['id']}")).json()

    assert (link["state"], link["needs_refund_review"]) == ("paid", False)


# ---- creating a link never loses its address ------------------------------------------


async def test_unexpected_chat_failure_still_returns_the_address(pg_client, monkeypatch) -> None:
    await start_workspace(pg_client)
    conversation_id = (await guest_says(pg_client, "Halo"))["conversation_id"]

    async def broken_send_reply(*args, **kwargs):
        raise RuntimeError("database hiccup while sending")

    monkeypatch.setattr(inbox, "send_reply", broken_send_reply)

    response = await pg_client.post(
        "/api/payment-links",
        json={"amount": 850000, "description": "DP", "conversation_id": conversation_id},
    )

    assert response.status_code == 201, response.text
    created = response.json()
    assert (created["sent_to_chat"], created["not_sent_reason"]) == (False, "send_failed")
    assert created["link"]["state"] == "pending"
    assert (await pg_client.get(f"/api/pay/{token_of(created)}")).status_code == 200


# ---- description is one line of plain text --------------------------------------------


@pytest.mark.parametrize(
    "description",
    [
        "DP Villa\nBayar di sini: https://evil.example/pay",
        "tab\there",
        "bell\x07",
        "null\x00byte",
        "\r\n",
    ],
)
async def test_description_with_control_characters_is_rejected(pg_client, description) -> None:
    await start_workspace(pg_client)

    response = await pg_client.post(
        "/api/payment-links", json={"amount": 850000, "description": description}
    )

    assert response.status_code == 422


async def test_description_keeps_ordinary_punctuation_and_other_scripts(pg_client) -> None:
    await start_workspace(pg_client)

    created = await make_link(pg_client, description="DP Vila “Senja” — 2 malam (民宿) ☀")

    assert created["link"]["description"] == "DP Vila “Senja” — 2 malam (民宿) ☀"


# ---- one payment per gateway reference -------------------------------------------------


async def test_gateway_reference_is_unique_per_account(pg_client, pg_session) -> None:
    workspace = await start_workspace(pg_client)
    token = token_of(await make_link(pg_client))
    reference = (
        await pg_client.post(f"/api/pay/{token}/payments", json={"method": "qris"})
    ).json()["reference"]
    await pg_client.post(
        f"/api/pay/{token}/payments", json={"method": "virtual_account", "bank": "BCA"}
    )

    with pytest.raises(DBAPIError):
        await pg_session.execute(
            text(
                "UPDATE payment SET gateway_reference = :r "
                "WHERE tenant_id = :t AND method = 'virtual_account'"
            ),
            {"r": reference, "t": workspace["tenant"]["id"]},
        )
    await pg_session.rollback()


# ---- the simulator pays the attempt the guest is looking at ---------------------------


async def test_simulator_pays_the_named_attempt_not_just_the_latest(pg_client) -> None:
    await start_workspace(pg_client)
    created = await make_link(pg_client)
    token = token_of(created)
    qris = (await pg_client.post(f"/api/pay/{token}/payments", json={"method": "qris"})).json()
    await pg_client.post(
        f"/api/pay/{token}/payments", json={"method": "virtual_account", "bank": "BCA"}
    )

    response = await pg_client.post(
        f"/api/simulator/payments/{token}/pay", json={"reference": qris["reference"]}
    )

    assert response.status_code == 200
    link = (await pg_client.get(f"/api/payment-links/{created['link']['id']}")).json()
    assert (link["state"], link["paid_via"]) == ("paid", "QRIS")


async def test_simulator_refuses_a_reference_that_is_not_an_open_attempt(pg_client) -> None:
    await start_workspace(pg_client)
    token = token_of(await make_link(pg_client))
    await pg_client.post(f"/api/pay/{token}/payments", json={"method": "qris"})

    response = await pg_client.post(
        f"/api/simulator/payments/{token}/pay", json={"reference": "simpay-someone-elses"}
    )

    assert response.status_code == 409
    assert (await pg_client.get(f"/api/pay/{token}")).json()["state"] == "pending"
