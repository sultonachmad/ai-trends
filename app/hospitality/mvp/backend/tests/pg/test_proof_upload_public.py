"""A guest uploads a transfer screenshot on the public pay page."""

import datetime as dt

import pytest
from sqlalchemy import text
from sqlmodel import select

from app.models.tenant import Document, Payment, TransferProof
from tests.pg.conftest import (
    PNG_BYTES,
    guest_uploads,
    image,
    make_link,
    pay,
    set_bank_account,
    start_workspace,
    token_of,
)

pytestmark = pytest.mark.integration

NOT_FOUND = {"detail": "Payment link not found"}


async def _ready(pg_client) -> tuple[dict, dict, str]:
    workspace = await start_workspace(pg_client)
    await set_bank_account(pg_client)
    created = await make_link(pg_client)
    return workspace, created, token_of(created)


async def test_guest_uploads_without_signing_in(
    pg_client, guest, pg_session, _document_storage
) -> None:
    workspace, created, token = await _ready(pg_client)

    response = await guest_uploads(guest, token, image("bukti-1"))

    assert response.status_code == 201, response.text
    page = response.json()
    assert page["state"] == "pending"
    assert page["proof"] == {"state": "checking", "reason": None}
    tenant_id = workspace["tenant"]["id"]
    [proof] = (
        await pg_session.exec(select(TransferProof).where(TransferProof.tenant_id == tenant_id))
    ).all()
    [document] = (
        await pg_session.exec(select(Document).where(Document.tenant_id == tenant_id))
    ).all()
    [payment] = (await pg_session.exec(select(Payment).where(Payment.tenant_id == tenant_id))).all()
    assert (proof.submitted_via, proof.match_status, proof.amount) == ("portal", "pending", 850000)
    assert str(proof.payment_link_id) == created["link"]["id"]
    assert proof.consent_at is not None
    assert proof.description == "DP Villa 2 malam"
    assert (document.kind, document.classification, document.content_type) == (
        "transfer_proof",
        "financial",
        "image/jpeg",
    )
    assert document.original_name is None  # the client's file name is not kept
    assert document.sha256 is not None
    # deleted on time even if nobody reviews it
    assert document.retention_until == dt.datetime.now(dt.UTC).date() + dt.timedelta(days=90)
    assert (payment.method, payment.status, payment.amount) == (
        "bank_transfer",
        "awaiting_verification",
        850000,
    )
    stored = _document_storage / document.storage_key
    assert stored.is_file() and stored.read_bytes() == image("bukti-1")
    assert stored.parent.name == tenant_id


async def test_png_is_accepted_whatever_the_file_is_called(pg_client, guest, pg_session) -> None:
    workspace, _created, token = await _ready(pg_client)

    response = await guest.post(
        f"/api/pay/{token}/proofs",
        files={"file": ("../../evil.html", image("x", PNG_BYTES), "text/html")},
        data={"consent": "true"},
    )

    assert response.status_code == 201
    [document] = (
        await pg_session.exec(
            select(Document).where(Document.tenant_id == workspace["tenant"]["id"])
        )
    ).all()
    assert document.content_type == "image/png"  # from the content, not the declared type
    assert document.storage_key.endswith(".png") and "evil" not in document.storage_key


@pytest.mark.parametrize("consent", ["false", "0", "no"])
async def test_consent_is_required(pg_client, guest, consent) -> None:
    _workspace, _created, token = await _ready(pg_client)

    response = await guest_uploads(guest, token, consent=consent)

    assert response.status_code == 422
    assert (await guest.get(f"/api/pay/{token}")).json()["proof"] is None


async def test_missing_consent_field_or_file_is_rejected(pg_client, guest) -> None:
    _workspace, _created, token = await _ready(pg_client)

    no_consent = await guest.post(
        f"/api/pay/{token}/proofs", files={"file": ("a.jpg", image(), "image/jpeg")}
    )
    no_file = await guest.post(f"/api/pay/{token}/proofs", data={"consent": "true"})

    assert (no_consent.status_code, no_file.status_code) == (422, 422)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"", "empty"),
        (b"<html><script>alert(1)</script></html>", "JPEG, PNG or WebP"),
        (b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>', "JPEG, PNG or WebP"),
        (b"%PDF-1.7 not an image", "JPEG, PNG or WebP"),
        (b"GIF89a" + b"\x00" * 20, "JPEG, PNG or WebP"),
    ],
)
async def test_non_images_are_rejected_and_nothing_is_stored(
    pg_client, guest, pg_session, _document_storage, content, message
) -> None:
    workspace, _created, token = await _ready(pg_client)

    response = await guest_uploads(guest, token, content)

    assert response.status_code == 422
    assert message in response.json()["detail"]
    count = (
        await pg_session.execute(
            text("SELECT count(*) FROM transferproof WHERE tenant_id = :t"),
            {"t": workspace["tenant"]["id"]},
        )
    ).scalar_one()
    assert count == 0
    assert not list(_document_storage.rglob("*.*"))


async def test_oversize_image_is_rejected(pg_client, guest, pg_session) -> None:
    workspace, _created, token = await _ready(pg_client)
    await pg_session.execute(
        text(
            "UPDATE property SET settings = "
            "jsonb_set(settings, '{business,proof_max_upload_mb}', '1') WHERE id = :p"
        ),
        {"p": workspace["property"]["id"]},
    )
    await pg_session.commit()

    too_big = await guest_uploads(guest, token, image("big") + b"\x00" * (1024 * 1024))
    fits = await guest_uploads(guest, token, image("small"))

    assert too_big.status_code == 422
    assert "at most 1 MB" in too_big.json()["detail"]
    assert fits.status_code == 201


async def test_awaiting_proofs_are_capped_per_link(pg_client, guest) -> None:
    _workspace, _created, token = await _ready(pg_client)

    statuses = [
        (await guest_uploads(guest, token, image(f"n{index}"))).status_code for index in range(4)
    ]

    assert statuses == [201, 201, 201, 429]


async def test_upload_needs_bank_details_on_the_property(pg_client, guest) -> None:
    await start_workspace(pg_client)
    token = token_of(await make_link(pg_client))

    response = await guest_uploads(guest, token)

    assert response.status_code == 409
    assert "manual transfers" in response.json()["detail"]


@pytest.mark.parametrize("final", ["paid", "expired", "cancelled"])
async def test_a_finished_link_takes_no_proof(pg_client, guest, pg_session, final) -> None:
    _workspace, created, token = await _ready(pg_client)
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

    response = await guest_uploads(guest, token)

    assert response.status_code == 409


@pytest.mark.parametrize("token", ["short", "a" * 43])
async def test_bad_tokens_get_the_same_404(guest, token) -> None:
    response = await guest_uploads(guest, token)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


async def test_response_reveals_nothing_internal_and_sends_privacy_headers(
    pg_client, guest
) -> None:
    workspace, created, token = await _ready(pg_client)

    response = await guest_uploads(guest, token)

    for secret in (
        workspace["tenant"]["id"],
        created["link"]["id"],
        "storage",
        "sha256",
        "document",
    ):
        assert secret not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"


async def test_failed_save_leaves_no_file_behind(
    pg_client, guest, _document_storage, monkeypatch
) -> None:
    from app.models.tenant import TransferProof as Proof

    _workspace, _created, token = await _ready(pg_client)

    def broken(*args, **kwargs):
        raise RuntimeError("database refused the proof")

    monkeypatch.setattr(Proof, "__init__", broken)

    with pytest.raises(RuntimeError):
        await guest_uploads(guest, token)

    assert not list(_document_storage.rglob("*.*"))
