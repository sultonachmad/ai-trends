"""Gateway notifications: applied once, checked against the payment, never double-paying."""

import asyncio
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlmodel import select

from app.config import settings
from app.models.tenant import Payment, PaymentEvent, PaymentLink
from app.services.gateway_events import PAID_EVENT, GatewayEvent, handle_gateway_event
from tests.pg.conftest import make_link, pay, start_workspace, token_of

pytestmark = pytest.mark.integration


async def _start(client, token: str, method: str = "qris", bank: str | None = None) -> dict:
    body = {"method": method} if bank is None else {"method": method, "bank": bank}
    response = await client.post(f"/api/pay/{token}/payments", json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def _payments(pg_session, tenant_id: str) -> list[Payment]:
    rows = await pg_session.exec(
        select(Payment)
        .where(Payment.tenant_id == tenant_id)
        .order_by(Payment.created_at)
        .execution_options(populate_existing=True)  # re-read rows this session already holds
    )
    return list(rows.all())


def _event(reference: str, amount: str = "850000", **overrides) -> GatewayEvent:
    values = {
        "gateway_event_id": f"evt-{uuid.uuid4().hex}",
        "event_type": PAID_EVENT,
        "gateway_reference": reference,
        "amount": Decimal(amount),
        "signature_valid": True,
        "raw": {"reference": reference},
    }
    return GatewayEvent(**{**values, **overrides})


async def _apply(pg_session_factory, payment: Payment, event: GatewayEvent):
    async with pg_session_factory() as session:
        return await handle_gateway_event(
            session, payment.tenant_id, payment.gateway_account_id, event
        )


async def test_paying_marks_the_link_paid_everywhere(pg_client, pg_session) -> None:
    workspace = await start_workspace(pg_client)
    created = await make_link(pg_client)
    token = token_of(created)

    response = await pay(pg_client, token, "virtual_account", "BRI")

    assert response.status_code == 200
    assert response.json()["state"] == "paid"
    assert response.json()["instructions"] is None
    staff_view = (await pg_client.get(f"/api/payment-links/{created['link']['id']}")).json()
    assert (staff_view["state"], staff_view["paid_via"]) == ("paid", "Virtual account BRI")
    [payment] = await _payments(pg_session, workspace["tenant"]["id"])
    assert payment.status == "captured"
    assert (payment.authorized_amount, payment.captured_amount) == (850000, 850000)
    assert payment.captured_at is not None
    events = (
        await pg_session.exec(
            select(PaymentEvent).where(PaymentEvent.tenant_id == workspace["tenant"]["id"])
        )
    ).all()
    assert [(e.event_type, e.status, e.signature_valid) for e in events] == [
        ("payment.paid", "applied", True)
    ]
    assert events[0].processed_at is not None and events[0].payment_id == payment.id


async def test_other_open_attempts_are_cancelled_when_one_is_paid(pg_client, pg_session) -> None:
    workspace = await start_workspace(pg_client)
    token = token_of(await make_link(pg_client))
    await _start(pg_client, token, "qris")
    await _start(pg_client, token, "virtual_account", "BCA")  # the latest attempt is the one paid

    await pg_client.post(f"/api/simulator/payments/{token}/pay")

    statuses = sorted(
        (p.method, p.status) for p in await _payments(pg_session, workspace["tenant"]["id"])
    )
    assert statuses == [("qris", "cancelled"), ("virtual_account", "captured")]


async def test_repeated_event_changes_nothing(pg_client, pg_session, pg_session_factory) -> None:
    workspace = await start_workspace(pg_client)
    token = token_of(await make_link(pg_client))
    reference = (await _start(pg_client, token))["reference"]
    [payment] = await _payments(pg_session, workspace["tenant"]["id"])
    event = _event(reference)

    first = await _apply(pg_session_factory, payment, event)
    second = await _apply(pg_session_factory, payment, event)

    assert (first.result, second.result) == ("applied", "duplicate")
    count = (
        await pg_session.execute(
            text("SELECT count(*) FROM paymentevent WHERE tenant_id = :t"),
            {"t": workspace["tenant"]["id"]},
        )
    ).scalar_one()
    assert count == 1


async def test_second_event_for_a_captured_payment_is_a_duplicate(
    pg_client, pg_session, pg_session_factory
) -> None:
    workspace = await start_workspace(pg_client)
    token = token_of(await make_link(pg_client))
    reference = (await _start(pg_client, token))["reference"]
    [payment] = await _payments(pg_session, workspace["tenant"]["id"])

    first = await _apply(pg_session_factory, payment, _event(reference))
    second = await _apply(pg_session_factory, payment, _event(reference))  # new event id

    assert (first.result, second.result) == ("applied", "duplicate")


async def test_simultaneous_notifications_pay_the_link_once(
    pg_client, pg_session, pg_session_factory
) -> None:
    workspace = await start_workspace(pg_client)
    created = await make_link(pg_client)
    token = token_of(created)
    qris = (await _start(pg_client, token, "qris"))["reference"]
    bca = (await _start(pg_client, token, "virtual_account", "BCA"))["reference"]
    payments = await _payments(pg_session, workspace["tenant"]["id"])

    outcomes = await asyncio.gather(
        *(
            _apply(pg_session_factory, payments[0], _event(reference))
            for reference in (qris, bca, qris, bca)
        )
    )

    applied = [o for o in outcomes if o.result == "applied"]
    assert len(applied) == 1
    link = (
        await pg_session.exec(select(PaymentLink).where(PaymentLink.id == created["link"]["id"]))
    ).one()
    assert link.status == "paid"
    final = await _payments(pg_session, workspace["tenant"]["id"])
    assert sorted(p.status for p in final).count("captured") <= 2
    # exactly one payment made the link paid; a second capture, if any, is flagged for refund
    flagged = [p for p in final if (p.metadata_ or {}).get("needs_refund_review")]
    assert len([p for p in final if p.status == "captured"]) - len(flagged) == 1
    # the staff view agrees: paid by exactly the one unflagged capture
    staff_view = (await pg_client.get(f"/api/payment-links/{created['link']['id']}")).json()
    paid_by = next(p for p in final if p.status == "captured" and p not in flagged)
    expected = "QRIS" if paid_by.method == "qris" else "Virtual account BCA"
    assert (staff_view["state"], staff_view["paid_via"]) == ("paid", expected)
    assert staff_view["needs_refund_review"] is bool(flagged)


async def test_amount_mismatch_is_not_applied(pg_client, pg_session, pg_session_factory) -> None:
    workspace = await start_workspace(pg_client)
    created = await make_link(pg_client)
    reference = (await _start(pg_client, token_of(created)))["reference"]
    [payment] = await _payments(pg_session, workspace["tenant"]["id"])

    outcome = await _apply(pg_session_factory, payment, _event(reference, amount="1000"))

    assert (outcome.result, outcome.reason) == ("ignored", "amount_mismatch")
    assert (await pg_client.get(f"/api/payment-links/{created['link']['id']}")).json()[
        "state"
    ] == "pending"
    await pg_session.refresh(payment)
    assert (payment.status, payment.failure_reason) == ("pending", "amount_mismatch")


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"signature_valid": False}, "bad_signature"),
        ({"event_type": "payment.refunded"}, "unknown_type"),
        ({"gateway_reference": "simpay-does-not-exist"}, "unknown_payment"),
    ],
)
async def test_events_that_must_not_be_applied(
    pg_client, pg_session, pg_session_factory, overrides, reason
) -> None:
    workspace = await start_workspace(pg_client)
    created = await make_link(pg_client)
    reference = (await _start(pg_client, token_of(created)))["reference"]
    [payment] = await _payments(pg_session, workspace["tenant"]["id"])

    outcome = await _apply(pg_session_factory, payment, _event(reference, **overrides))

    assert (outcome.result, outcome.reason) == ("ignored", reason)
    assert (await pg_client.get(f"/api/payment-links/{created['link']['id']}")).json()[
        "state"
    ] == "pending"


@pytest.mark.parametrize("final", ["expired", "cancelled"])
async def test_money_for_a_dead_link_is_recorded_and_flagged_not_applied(
    pg_client, pg_session, pg_session_factory, final
) -> None:
    workspace = await start_workspace(pg_client)
    created = await make_link(pg_client)
    link_id = created["link"]["id"]
    reference = (await _start(pg_client, token_of(created)))["reference"]
    [payment] = await _payments(pg_session, workspace["tenant"]["id"])
    if final == "expired":
        await pg_session.execute(
            text("UPDATE paymentlink SET expires_at = now() - interval '1 minute' WHERE id = :i"),
            {"i": link_id},
        )
    else:
        # cancelled by staff, but the bank still delivers a payment made just before
        await pg_session.execute(
            text("UPDATE paymentlink SET status = 'cancelled' WHERE id = :i"), {"i": link_id}
        )
    await pg_session.commit()

    outcome = await _apply(pg_session_factory, payment, _event(reference))

    assert (outcome.result, outcome.reason) == ("ignored", f"link_{final}")
    assert (await pg_client.get(f"/api/payment-links/{link_id}")).json()["state"] == final
    await pg_session.refresh(payment)
    assert payment.status == "captured"
    assert payment.metadata_["needs_refund_review"] == f"link_{final}"


async def test_simulate_before_choosing_a_method_is_refused(pg_client) -> None:
    await start_workspace(pg_client)
    token = token_of(await make_link(pg_client))

    response = await pg_client.post(f"/api/simulator/payments/{token}/pay")

    assert response.status_code == 409
    assert response.json() == {"detail": "Choose a payment method first."}


async def test_simulating_twice_does_not_pay_twice(pg_client) -> None:
    await start_workspace(pg_client)
    token = token_of(await make_link(pg_client))
    assert (await pay(pg_client, token)).status_code == 200

    again = await pg_client.post(f"/api/simulator/payments/{token}/pay")

    assert again.status_code == 409
    assert "already been paid" in again.json()["detail"]


async def test_payment_simulator_is_not_available_when_switched_off(pg_client, monkeypatch) -> None:
    await start_workspace(pg_client)
    token = token_of(await make_link(pg_client))
    await _start(pg_client, token)
    monkeypatch.setattr(settings, "PAYMENT_SIMULATOR_ENABLED", False)

    response = await pg_client.post(f"/api/simulator/payments/{token}/pay")

    assert response.status_code == 404
    page = (await pg_client.get(f"/api/pay/{token}")).json()
    assert (page["state"], page["simulator_enabled"]) == ("pending", False)
