"""CSRF defence: state-changing requests from a foreign web origin are refused."""

import pytest

from app.config import settings
from app.security.origin_check import is_trusted_source

ALLOWED = settings.CORS_ORIGINS[0]
SIGNUP = {"email": "not-an-email", "password": "x"}  # fails validation (422) once past the check


async def test_post_from_foreign_origin_is_blocked(client) -> None:
    response = await client.post(
        "/api/auth/signup", json=SIGNUP, headers={"Origin": "https://evil.example"}
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Cross-site request blocked"}


@pytest.mark.parametrize("method", ["put", "patch", "delete"])
async def test_other_unsafe_methods_are_blocked_too(client, method) -> None:
    response = await getattr(client, method)(
        "/api/sample-items/1", headers={"Origin": "https://evil.example"}
    )

    assert response.status_code == 403


async def test_post_from_allowed_origin_passes(client) -> None:
    response = await client.post("/api/auth/signup", json=SIGNUP, headers={"Origin": ALLOWED})

    assert response.status_code == 422


async def test_post_from_the_api_own_origin_passes(client) -> None:
    response = await client.post("/api/auth/signup", json=SIGNUP, headers={"Origin": "http://test"})

    assert response.status_code == 422


async def test_post_without_origin_or_referer_passes(client) -> None:
    """Non-browser clients send neither header and carry no victim cookies."""
    response = await client.post("/api/auth/signup", json=SIGNUP)

    assert response.status_code == 422


async def test_referer_is_used_when_origin_is_missing(client) -> None:
    blocked = await client.post(
        "/api/auth/signup", json=SIGNUP, headers={"Referer": "https://evil.example/page?x=1"}
    )
    allowed = await client.post(
        "/api/auth/signup", json=SIGNUP, headers={"Referer": f"{ALLOWED}/login"}
    )

    assert blocked.status_code == 403
    assert allowed.status_code == 422


async def test_opaque_null_origin_is_blocked(client) -> None:
    response = await client.post("/api/auth/signup", json=SIGNUP, headers={"Origin": "null"})

    assert response.status_code == 403


async def test_safe_methods_are_never_blocked(client) -> None:
    response = await client.get("/api/health", headers={"Origin": "https://evil.example"})

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("http://localhost:3000", True),
        ("http://LOCALHOST:3000/", True),
        ("http://localhost:3000.evil.example", False),
        ("http://evil.example/http://localhost:3000", False),
        ("https://localhost:3000", False),
        ("http://api.internal:8000", True),  # same host as the request
        ("", False),
        ("not a url", False),
    ],
)
def test_is_trusted_source(source: str, expected: bool) -> None:
    allowed = frozenset({"http://localhost:3000"})

    assert is_trusted_source(source, allowed, request_host="api.internal:8000") is expected
