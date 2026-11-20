"""Reviewing transfer proofs: queue, image, approve (two-person rule), reject."""

import asyncio

import pytest
from sqlalchemy import text
from sqlmodel import select

from app.models.tenant import Document, Payment
from app.services import inbox
from tests.pg.conftest import (
    add_staff_member,
    guest_says,
    guest_uploads,
    image,
    make_link,
    pay,
    set_bank_account,
    staff_uploads,
    start_workspace,
    token_of,
)

pytestmark = pytest.mark.integration

BASE = "/api/transfer-proofs"


async def _ready(pg_client, **link) -> tuple[dict, dict, str]:
    workspace = await start_workspace(pg_client)
    await set_bank_account(pg_client)
    created = await make_link(pg_client, **link)
    return workspace, created, token_of(created)


async def _queue(client, state: str = "awaiting") -> list[dict]:
    return (await client.get(f"{BASE}?state={state}")).json()["items"]


async def _link_state(client, created: dict) -> dict:
    return (await client.get(f"/api/payment-links/{created['link']['id']}")).json()


# ---- queue and image -------------------------------------------------------------------


async def test_requires_sign_in(pg_client) -> None:
    assert (await pg_client.get(BASE)).status_code == 401
    assert (await staff_uploads(pg_client, amount=100000, description="x")).status_code == 401


async def test_queue_shows_what_a_reviewer_needs(pg_client, guest) -> None:
    _workspace, created, token = await _ready(pg_client)
    await guest_uploads(guest, token, image("one"))

    [proof] = await _queue(pg_client)

    assert proof["state"] == "awaiting"
    assert proof["amount"] == "850000.00"
    assert proof["description"] == "DP Villa 2 malam"
    assert proof["payment_link_id"] == created["link"]["id"]
    assert (proof["submitted_by_guest"], proof["uploaded_by_name"]) == (True, None)
    assert (proof["needs_second_approval"], proof["duplicate_of"]) == (False, None)
    assert proof["image_available"] is True
    assert (await pg_client.get("/api/workspace")).json()["proofs_awaiting_review"] == 1
    assert (await pg_client.get(f"{BASE}/{proof['id']}")).json() == proof


async def test_image_is_served_to_staff_with_safe_headers(pg_client, guest) -> None:
    _workspace, _created, token = await _ready(pg_client)
    await guest_uploads(guest, token, image("pixels"))
    [proof] = await _queue(pg_client)

    response = await pg_client.get(f"{BASE}/{proof['id']}/image")

    assert response.status_code == 200
    assert response.content == image("pixels")
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "no-store" in response.headers["cache-control"]
    assert "sandbox" in response.headers["content-security-policy"]
    assert (await guest.get(f"{BASE}/{proof['id']}/image")).status_code == 401


async def test_queue_paging_and_filters(pg_client) -> None:
    await start_workspace(pg_client)
    for index in range(5):
        response = await staff_uploads(
            pg_client, image(f"p{index}"), amount=100000 + index, description=f"Transfer {index}"
        )
        assert response.status_code == 201, response.text

    first = (await pg_client.get(f"{BASE}?limit=2")).json()
    second = (await pg_client.get(BASE, params={"limit": 2, "cursor": first["next_cursor"]})).json()
    third = (await pg_client.get(BASE, params={"limit": 2, "cursor": second["next_cursor"]})).json()

    names = [i["description"] for page in (first, second, third) for i in page["items"]]
    assert names == [f"Transfer {index}" for index in (4, 3, 2, 1, 0)]
    assert third["next_cursor"] is None
    assert await _queue(pg_client, "approved") == []
    for query in ("state=pending", "limit=0", "limit=51", "cursor=garbage"):
        assert (await pg_client.get(f"{BASE}?{query}")).status_code == 422


# ---- staff upload ---------------------------------------------------------------------


async def test_staff_upload_for_a_link(pg_client) -> None:
    workspace, created, _token = await _ready(pg_client)

    response = await staff_uploads(pg_client, payment_link_id=created["link"]["id"])

    assert response.status_code == 201, response.text
    proof = response.json()
    assert (proof["submitted_by_guest"], proof["amount"]) == (False, "850000.00")
    assert proof["uploaded_by_name"] == workspace["staff"]["display_name"]


async def test_staff_can_add_a_proof_to_an_expired_link_but_a_guest_cannot(
    pg_client, guest, pg_session
) -> None:
    _workspace, created, token = await _ready(pg_client)
    await pg_session.execute(
        text("UPDATE paymentlink SET expires_at = now() - interval '1 minute' WHERE id = :i"),
        {"i": created["link"]["id"]},
    )
    await pg_session.commit()

    by_guest = await guest_uploads(guest, token)
    by_staff = await staff_uploads(pg_client, payment_link_id=created["link"]["id"])

    assert (by_guest.status_code, by_staff.status_code) == (409, 201)


async def test_transfer_without_a_link(pg_client) -> None:
    await start_workspace(pg_client)
    conversation_id = (await guest_says(pg_client, "Sudah saya transfer ya"))["conversation_id"]

    response = await staff_uploads(
        pg_client, amount=1250000, description="Sewa 1 malam", conversation_id=conversation_id
    )

    assert response.status_code == 201, response.text
    proof = response.json()
    assert (proof["amount"], proof["description"]) == ("1250000.00", "Sewa 1 malam")
    assert (proof["payment_link_id"], proof["conversation_id"]) == (None, conversation_id)
    assert proof["guest"]["name"] == "Budi"

    approved = await pg_client.post(f"{BASE}/{proof['id']}/approve")
    assert approved.json()["state"] == "approved"


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"amount": 100000},
        {"description": "x"},
        {"amount": 9999, "description": "terlalu kecil"},
        {"amount": 600000000, "description": "terlalu besar"},
        {"amount": "12.5", "description": "x"},
        {"amount": 100000, "description": "baris\nbaru"},
        {
            "payment_link_id": "00000000-0000-4000-8000-000000000000",
            "amount": 100000,
            "description": "x",
        },
    ],
)
async def test_staff_upload_validation(pg_client, fields) -> None:
    await start_workspace(pg_client)

    assert (await staff_uploads(pg_client, **fields)).status_code == 422


async def test_staff_upload_to_unknown_link_or_conversation_is_404(pg_client) -> None:
    await start_workspace(pg_client)
    missing = "00000000-0000-4000-8000-000000000000"

    link = await staff_uploads(pg_client, payment_link_id=missing)
    conversation = await staff_uploads(
        pg_client, amount=100000, description="x", conversation_id=missing
    )

    assert (link.status_code, link.json()["detail"]) == (404, "Payment link not found")
    assert (conversation.status_code, conversation.json()["detail"]) == (
        404,
        "Conversation not found",
    )


@pytest.mark.parametrize("final", ["paid", "cancelled"])
async def test_staff_cannot_add_a_proof_to_a_paid_or_cancelled_link(pg_client, final) -> None:
    _workspace, created, token = await _ready(pg_client)
    if final == "paid":
        await pay(pg_client, token)
    else:
        await pg_client.post(f"/api/payment-links/{created['link']['id']}/cancel")

    response = await staff_uploads(pg_client, payment_link_id=created["link"]["id"])

    assert response.status_code == 409
    assert final in response.json()["detail"]


# ---- approve --------------------------------------------------------------------------


async def test_approval_marks_the_link_paid_by_bank_transfer(pg_client, guest, pg_session) -> None:
    workspace, created, token = await _ready(pg_client)
    await guest.post(f"/api/pay/{token}/payments", json={"method": "qris"})  # an open attempt
    await guest_uploads(guest, token)
    [proof] = await _queue(pg_client)

    response = await pg_client.post(f"{BASE}/{proof['id']}/approve")

    assert response.status_code == 200, response.text
    approved = response.json()
    assert approved["state"] == "approved"
    assert approved["reviewed_by_name"] == workspace["staff"]["display_name"]
    assert approved["reviewed_at"] is not None
    link = await _link_state(pg_client, created)
    assert (link["state"], link["paid_via"], link["needs_refund_review"]) == (
        "paid",
        "Bank transfer",
        False,
    )
    assert (await guest.get(f"/api/pay/{token}")).json()["state"] == "paid"
    payments = (
        await pg_session.exec(select(Payment).where(Payment.tenant_id == workspace["tenant"]["id"]))
    ).all()
    assert sorted((p.method, p.status) for p in payments) == [
        ("bank_transfer", "captured"),
        ("qris", "cancelled"),
    ]
    assert await _queue(pg_client) == []
    assert [p["id"] for p in await _queue(pg_client, "approved")] == [proof["id"]]


async def test_approval_stamps_the_image_deletion_date(pg_client, guest, pg_session) -> None:
    import datetime as dt

    workspace, _created, token = await _ready(pg_client)
    await guest_uploads(guest, token)
    [proof] = await _queue(pg_client)

    await pg_client.post(f"{BASE}/{proof['id']}/approve")

    [document] = (
        await pg_session.exec(
            select(Document).where(Document.tenant_id == workspace["tenant"]["id"])
        )
    ).all()
    assert document.retention_until == dt.datetime.now(dt.UTC).date() + dt.timedelta(days=90)


async def test_an_expired_link_can_still_be_approved(pg_client, guest, pg_session) -> None:
    _workspace, created, token = await _ready(pg_client)
    await guest_uploads(guest, token)  # uploaded in time …
    await pg_session.execute(
        text("UPDATE paymentlink SET expires_at = now() - interval '1 minute' WHERE id = :i"),
        {"i": created["link"]["id"]},
    )
    await pg_session.commit()  # … staff check after the deadline
    [proof] = await _queue(pg_client)

    response = await pg_client.post(f"{BASE}/{proof['id']}/approve")

    assert response.status_code == 200
    assert (await _link_state(pg_client, created))["state"] == "paid"


@pytest.mark.parametrize("final", ["paid", "cancelled"])
async def test_approval_is_refused_when_the_link_is_paid_or_cancelled(
    pg_client, guest, final
) -> None:
    _workspace, created, token = await _ready(pg_client)
    await guest_uploads(guest, token)
    [proof] = await _queue(pg_client)
    if final == "paid":
        await pay(guest, token)
    else:
        await pg_client.post(f"/api/payment-links/{created['link']['id']}/cancel")

    response = await pg_client.post(f"{BASE}/{proof['id']}/approve")

    assert response.status_code == 409
    assert "Reject the proof" in response.json()["detail"]
    assert (await pg_client.get(f"{BASE}/{proof['id']}")).json()["state"] == "awaiting"
    assert (await _link_state(pg_client, created))["state"] == final


async def test_a_decision_is_final(pg_client, guest) -> None:
    _workspace, _created, token = await _ready(pg_client)
    await guest_uploads(guest, token)
    [proof] = await _queue(pg_client)
    await pg_client.post(f"{BASE}/{proof['id']}/approve")

    again = await pg_client.post(f"{BASE}/{proof['id']}/approve")
    reject = await pg_client.post(
        f"{BASE}/{proof['id']}/reject", json={"reason": "berubah pikiran"}
    )

    assert (again.status_code, reject.status_code) == (409, 409)
    assert "already approved" in again.json()["detail"]


async def test_simultaneous_approvals_pay_once(pg_client, guest, pg_session) -> None:
    workspace, created, token = await _ready(pg_client)
    await guest_uploads(guest, token)
    [proof] = await _queue(pg_client)

    responses = await asyncio.gather(
        *(pg_client.post(f"{BASE}/{proof['id']}/approve") for _ in range(4))
    )

    assert sorted(r.status_code for r in responses) == [200, 409, 409, 409]
    captured = (
        await pg_session.execute(
            text("SELECT count(*) FROM payment WHERE tenant_id = :t AND status = 'captured'"),
            {"t": workspace["tenant"]["id"]},
        )
    ).scalar_one()
    assert captured == 1
    assert (await _link_state(pg_client, created))["state"] == "paid"


# ---- the two-person rule ---------------------------------------------------------------


async def test_owner_approves_a_large_transfer_alone(pg_client, guest) -> None:
    _workspace, created, token = await _ready(pg_client, amount=7500000)
    await guest_uploads(guest, token)
    [proof] = await _queue(pg_client)
    assert proof["needs_second_approval"] is True

    response = await pg_client.post(f"{BASE}/{proof['id']}/approve")

    assert response.json()["state"] == "approved"
    assert (await _link_state(pg_client, created))["state"] == "paid"


async def test_large_transfer_needs_two_different_staff(
    pg_client, other_client, third_client, guest, pg_session
) -> None:
    workspace, created, token = await _ready(pg_client, amount=7500000)
    await add_staff_member(pg_session, other_client, workspace)
    await add_staff_member(pg_session, third_client, workspace)
    await guest_uploads(guest, token)
    [proof] = await _queue(other_client)
    url = f"{BASE}/{proof['id']}/approve"

    first = await other_client.post(url)

    assert first.status_code == 200
    assert first.json()["state"] == "awaiting_second"
    assert first.json()["first_approved_by_name"] is not None
    assert (await _link_state(pg_client, created))["state"] == "pending"
    assert [p["state"] for p in await _queue(pg_client)] == ["awaiting_second"]

    same_again = await other_client.post(url)
    assert same_again.status_code == 409
    assert "different staff member" in same_again.json()["detail"]
    assert (await _link_state(pg_client, created))["state"] == "pending"

    second = await third_client.post(url)
    assert second.json()["state"] == "approved"
    assert (await _link_state(pg_client, created))["state"] == "paid"


async def test_owner_can_complete_after_a_staff_first_approval(
    pg_client, other_client, guest, pg_session
) -> None:
    workspace, created, token = await _ready(pg_client, amount=7500000)
    await add_staff_member(pg_session, other_client, workspace)
    await guest_uploads(guest, token)
    [proof] = await _queue(other_client)
    await other_client.post(f"{BASE}/{proof['id']}/approve")

    response = await pg_client.post(f"{BASE}/{proof['id']}/approve")

    assert response.json()["state"] == "approved"
    assert (await _link_state(pg_client, created))["state"] == "paid"


async def test_exactly_the_threshold_needs_one_approval(
    pg_client, other_client, guest, pg_session
) -> None:
    workspace, created, token = await _ready(pg_client, amount=5000000)
    await add_staff_member(pg_session, other_client, workspace)
    await guest_uploads(guest, token)
    [proof] = await _queue(other_client)
    assert proof["needs_second_approval"] is False

    response = await other_client.post(f"{BASE}/{proof['id']}/approve")

    assert response.json()["state"] == "approved"
    assert (await _link_state(pg_client, created))["state"] == "paid"


async def test_threshold_is_a_property_setting(pg_client, other_client, guest, pg_session) -> None:
    workspace, _created, token = await _ready(pg_client, amount=850000)
    await add_staff_member(pg_session, other_client, workspace)
    await pg_session.execute(
        text(
            "UPDATE property SET settings = jsonb_set(settings, "
            "'{business,second_approver_threshold_idr}', '500000') WHERE id = :p"
        ),
        {"p": workspace["property"]["id"]},
    )
    await pg_session.commit()
    await guest_uploads(guest, token)
    [proof] = await _queue(other_client)

    response = await other_client.post(f"{BASE}/{proof['id']}/approve")

    assert response.json()["state"] == "awaiting_second"


# ---- reject ---------------------------------------------------------------------------


async def test_rejection_keeps_the_link_payable_and_tells_the_guest(pg_client, guest) -> None:
    _workspace, created, token = await _ready(pg_client)
    await guest_uploads(guest, token, image("blur"))
    [proof] = await _queue(pg_client)

    response = await pg_client.post(
        f"{BASE}/{proof['id']}/reject", json={"reason": "  Nominal tidak sesuai  "}
    )

    assert response.status_code == 200, response.text
    assert (response.json()["state"], response.json()["rejection_reason"]) == (
        "rejected",
        "Nominal tidak sesuai",
    )
    assert (await _link_state(pg_client, created))["state"] == "pending"
    page = (await guest.get(f"/api/pay/{token}")).json()
    assert page["proof"] == {"state": "rejected", "reason": "Nominal tidak sesuai"}
    again = await guest_uploads(guest, token, image("sharp"))
    assert again.status_code == 201
    assert again.json()["proof"] == {"state": "checking", "reason": None}


@pytest.mark.parametrize(
    "body", [{}, {"reason": ""}, {"reason": "x"}, {"reason": "r" * 201}, {"reason": "a\nb"}]
)
async def test_a_proper_reason_is_required(pg_client, guest, body) -> None:
    _workspace, _created, token = await _ready(pg_client)
    await guest_uploads(guest, token)
    [proof] = await _queue(pg_client)

    response = await pg_client.post(f"{BASE}/{proof['id']}/reject", json=body)

    assert response.status_code == 422
    assert (await pg_client.get(f"{BASE}/{proof['id']}")).json()["state"] == "awaiting"


async def test_rejection_is_sent_to_the_chat_when_possible(pg_client) -> None:
    await start_workspace(pg_client)
    await set_bank_account(pg_client)
    conversation_id = (await guest_says(pg_client, "Halo"))["conversation_id"]
    created = await make_link(pg_client, conversation_id=conversation_id)
    await staff_uploads(pg_client, payment_link_id=created["link"]["id"])
    [proof] = await _queue(pg_client)

    await pg_client.post(f"{BASE}/{proof['id']}/reject", json={"reason": "Gambar buram"})

    thread = (await pg_client.get(f"/api/conversations/{conversation_id}/messages")).json()
    assert "belum dapat kami terima: Gambar buram" in thread[-1]["body"]
    assert "DP Villa 2 malam" in thread[-1]["body"]


async def test_rejection_on_a_paid_link_does_not_ask_the_guest_to_upload_again(
    pg_client, guest
) -> None:
    """The gateway paid the link while a proof waited: rejecting is the only way out."""
    await start_workspace(pg_client)
    await set_bank_account(pg_client)
    conversation_id = (await guest_says(pg_client, "Halo"))["conversation_id"]
    created = await make_link(pg_client, conversation_id=conversation_id)
    await staff_uploads(pg_client, payment_link_id=created["link"]["id"])
    [proof] = await _queue(pg_client)
    await pay(guest, token_of(created))

    response = await pg_client.post(
        f"{BASE}/{proof['id']}/reject", json={"reason": "Sudah dibayar lewat QRIS"}
    )

    assert response.status_code == 200
    assert response.json()["state"] == "rejected"
    assert (await _link_state(pg_client, created))["state"] == "paid"
    thread = (await pg_client.get(f"/api/conversations/{conversation_id}/messages")).json()
    assert "belum dapat kami terima: Sudah dibayar lewat QRIS" in thread[-1]["body"]
    assert "kirim ulang" not in thread[-1]["body"]


async def test_rejected_proofs_do_not_use_up_gateway_attempts(
    pg_client, guest, monkeypatch
) -> None:
    monkeypatch.setattr("app.services.checkout.MAX_ATTEMPTS_PER_LINK", 2)
    _workspace, _created, token = await _ready(pg_client)
    for seed in ("satu", "dua", "tiga"):
        await guest_uploads(guest, token, image(seed))
        [proof] = await _queue(pg_client)
        await pg_client.post(f"{BASE}/{proof['id']}/reject", json={"reason": "tidak cocok"})

    response = await guest.post(f"/api/pay/{token}/payments", json={"method": "qris"})

    assert response.status_code == 201, response.text


async def test_a_failing_chat_notice_does_not_fail_the_rejection(pg_client, monkeypatch) -> None:
    await start_workspace(pg_client)
    await set_bank_account(pg_client)
    conversation_id = (await guest_says(pg_client, "Halo"))["conversation_id"]
    created = await make_link(pg_client, conversation_id=conversation_id)
    await staff_uploads(pg_client, payment_link_id=created["link"]["id"])
    [proof] = await _queue(pg_client)

    async def broken(*args, **kwargs):
        raise RuntimeError("chat is down")

    monkeypatch.setattr(inbox, "send_reply", broken)

    response = await pg_client.post(f"{BASE}/{proof['id']}/reject", json={"reason": "Gambar buram"})

    assert response.status_code == 200
    assert response.json()["state"] == "rejected"


@pytest.mark.parametrize(
    ("method", "suffix"),
    [("get", ""), ("get", "/image"), ("post", "/approve"), ("post", "/reject")],
)
async def test_unknown_proof_is_404_with_its_own_message(pg_client, method, suffix) -> None:
    await start_workspace(pg_client)
    kwargs = {"json": {"reason": "alasan"}} if suffix == "/reject" else {}

    response = await getattr(pg_client, method)(
        f"{BASE}/00000000-0000-4000-8000-000000000000{suffix}", **kwargs
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Transfer proof not found"}
