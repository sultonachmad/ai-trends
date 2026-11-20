"""The session cookie's Secure flag follows PREFAB_SESSION_COOKIE_SECURE."""

import uuid

import pytest

from app.config import settings

PASSWORD = "Sup3r-secret-pw"  # noqa: S105 — throwaway test account


async def _login_set_cookie(client) -> str:
    email = f"cookie-{uuid.uuid4().hex[:10]}@example.com"
    await client.post("/api/auth/signup", json={"email": email, "password": PASSWORD})
    response = await client.post("/session/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    return response.headers["set-cookie"].lower()


async def test_cookie_is_not_secure_by_default_for_local_http(client) -> None:
    assert settings.SESSION_COOKIE_SECURE is False

    cookie = await _login_set_cookie(client)

    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "secure" not in cookie


async def test_cookie_is_secure_when_configured(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SESSION_COOKIE_SECURE", True)

    cookie = await _login_set_cookie(client)

    assert "secure" in cookie
    assert "httponly" in cookie
