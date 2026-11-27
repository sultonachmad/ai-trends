"""Upload routes refuse an oversized body before it is parsed or spooled to disk."""

from collections.abc import AsyncIterator

import pytest

from app.security.upload_limit import (
    MAX_UPLOAD_BODY_BYTES,
    TOO_LARGE_DETAIL,
    is_upload_path,
)

PUBLIC_UPLOAD = "/api/pay/not-a-real-token/proofs"
STAFF_UPLOAD = "/api/transfer-proofs"
ID_SCAN = "/api/bookings/5b0c7a0e-0000-0000-0000-000000000000/guests/scan"
REPAIR = "/api/maintenance"


@pytest.mark.parametrize(
    "path",
    [PUBLIC_UPLOAD, PUBLIC_UPLOAD + "/", STAFF_UPLOAD, STAFF_UPLOAD + "/", ID_SCAN, REPAIR],
)
def test_upload_paths_are_limited(path: str) -> None:
    assert is_upload_path(path)


@pytest.mark.parametrize(
    "path",
    [
        "/api/pay/some-token",
        "/api/pay/some-token/payments",
        "/api/pay/a/b/proofs",
        "/api/transfer-proofs/5b0c7a0e-0000-0000-0000-000000000000/approve",
        "/api/payment-links",
        "/api/bookings/a/b/guests/scan",
        "/api/maintenance/5b0c7a0e-0000-0000-0000-000000000000/fix",
    ],
)
def test_other_paths_are_not_limited(path: str) -> None:
    assert not is_upload_path(path)


@pytest.mark.parametrize("path", [PUBLIC_UPLOAD, STAFF_UPLOAD])
async def test_declared_oversize_is_refused_without_reading(client, path) -> None:
    response = await client.post(
        path,
        content=b"x",
        headers={
            "Content-Type": "multipart/form-data; boundary=b",
            "Content-Length": str(MAX_UPLOAD_BODY_BYTES + 1),
        },
    )

    assert response.status_code == 413
    assert response.json() == {"detail": TOO_LARGE_DETAIL}


async def test_malformed_content_length_is_refused(client) -> None:
    response = await client.post(
        PUBLIC_UPLOAD,
        content=b"x",
        headers={"Content-Type": "multipart/form-data; boundary=b", "Content-Length": "lots"},
    )

    assert response.status_code == 400


async def test_streamed_oversize_is_cut_off(client) -> None:
    """A chunked upload declares no length: the bytes are counted as they arrive."""
    chunk = b"x" * (1024 * 1024)
    sent = 0

    async def body() -> AsyncIterator[bytes]:
        nonlocal sent
        yield b'--b\r\nContent-Disposition: form-data; name="file"; filename="a.png"\r\n\r\n'
        for _ in range(MAX_UPLOAD_BODY_BYTES // len(chunk) + 5):
            sent += len(chunk)
            yield chunk

    response = await client.post(
        PUBLIC_UPLOAD,
        content=body(),
        headers={"Content-Type": "multipart/form-data; boundary=b"},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": TOO_LARGE_DETAIL}


async def test_body_within_the_limit_reaches_the_route(client) -> None:
    response = await client.post(
        PUBLIC_UPLOAD,
        files={"file": ("a.png", b"not really an image", "image/png")},
        data={"consent": "true"},
    )

    assert response.status_code != 413


async def test_other_routes_are_untouched(client) -> None:
    response = await client.post(
        "/api/auth/signup",
        content=b"{}",
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(MAX_UPLOAD_BODY_BYTES + 1),
        },
    )

    assert response.status_code != 413
