"""PostgreSQL integration-test setup.

The hospitality tables (RLS, triggers, EXCLUDE constraints) exist only in PostgreSQL,
so tests under tests/pg/ run against a throwaway database, never the SQLite file the
rest of the suite uses and never the app's own database.

How it works:
* The server comes from PREFAB_TEST_DATABASE_URL, or from backend/.env's
  PREFAB_DATABASE_URL with the database name replaced by ``<name>_test``.
* The database is dropped, recreated and migrated to head once per test session.
* `get_session` is overridden so the app under test talks to it.
* If no PostgreSQL server answers, every test here is skipped with the reason —
  unless REQUIRE_PG_TESTS=1, which turns the skip into a failure (set it in CI).
"""

import os
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest
from dotenv import dotenv_values
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import settings
from app.database import get_session
from app.main import app

BACKEND_DIR = Path(__file__).resolve().parents[2]
PASSWORD = "Sup3r-secret-pw"  # noqa: S105 — test accounts in a throwaway database


def _test_database_url() -> str | None:
    explicit = os.environ.get("PREFAB_TEST_DATABASE_URL")
    if explicit:
        return explicit
    configured = dotenv_values(BACKEND_DIR / ".env").get("PREFAB_DATABASE_URL")
    if not configured or not configured.startswith("postgresql"):
        return None
    url = make_url(configured)
    return url.set(database=f"{url.database}_test").render_as_string(hide_password=False)


def _skip_or_fail(reason: str) -> None:
    """Skip locally; fail where REQUIRE_PG_TESTS=1 (CI), so isolation tests cannot vanish."""
    if os.environ.get("REQUIRE_PG_TESTS", "").lower() in {"1", "true"}:
        pytest.fail(f"REQUIRE_PG_TESTS is set but: {reason}")
    pytest.skip(reason)


async def _recreate_database(url: str) -> None:
    target = make_url(url)
    admin = create_async_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{target.database}" WITH (FORCE)'))
            await conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    finally:
        await admin.dispose()


def _migrate(url: str) -> None:
    subprocess.run(  # noqa: S603 — fixed argv, no shell
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env={**os.environ, "PREFAB_DATABASE_URL": url},
        check=True,
        capture_output=True,
    )


@pytest.fixture(scope="session")
async def pg_engine() -> AsyncIterator[AsyncEngine]:
    url = _test_database_url()
    if url is None:
        _skip_or_fail("no PostgreSQL URL configured (PREFAB_TEST_DATABASE_URL or backend/.env)")
    try:
        await _recreate_database(url)
    except Exception as exc:  # noqa: BLE001 — any connection failure means "skip"
        _skip_or_fail(f"PostgreSQL not reachable for integration tests: {exc}")
    _migrate(url)
    engine = create_async_engine(url)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
def pg_session_factory(pg_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(pg_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def pg_session(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """A plain (unscoped, superuser) session for arranging and asserting."""
    async with pg_session_factory() as session:
        yield session


@pytest.fixture
def _pg_override(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> Iterator[None]:
    """Point the app's `get_session` at the PostgreSQL test database for one test."""

    async def _get_session() -> AsyncIterator[AsyncSession]:
        async with pg_session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _get_session
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_session, None)


async def _new_client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


@pytest.fixture
async def pg_client(_pg_override: None) -> AsyncIterator[httpx.AsyncClient]:
    """In-process client (own cookie jar) using the PostgreSQL test database."""
    async for http in _new_client():
        yield http


@pytest.fixture
async def other_client(_pg_override: None) -> AsyncIterator[httpx.AsyncClient]:
    """A second, independent browser session — for cross-tenant tests."""
    async for http in _new_client():
        yield http


@pytest.fixture(autouse=True)
def _simulator_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Integration tests play the guest through the simulator endpoint."""
    monkeypatch.setattr(settings, "MESSAGING_SIMULATOR_ENABLED", True)


async def start_workspace(client: httpx.AsyncClient, **overrides: object) -> dict:
    """Sign up a fresh owner on `client` and return their new workspace."""
    await sign_up_and_in(client)
    created = await client.post("/api/onboarding", json=onboarding_payload(**overrides))
    assert created.status_code == 201, created.text
    return created.json()


async def guest_says(
    client: httpx.AsyncClient, text: str, phone: str = "+6281234567890", name: str | None = "Budi"
) -> dict:
    """Send a simulated inbound WhatsApp message to the client's own property."""
    payload = {"from_phone": phone, "body": text}
    if name is not None:
        payload["guest_name"] = name
    response = await client.post("/api/simulator/whatsapp/inbound", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def sign_up_and_in(client: httpx.AsyncClient) -> str:
    """Create a fresh account, open a session on `client`, return the email."""
    email = f"owner-{uuid.uuid4().hex[:10]}@example.com"
    created = await client.post("/api/auth/signup", json={"email": email, "password": PASSWORD})
    assert created.status_code == 201, created.text
    logged_in = await client.post("/session/login", json={"email": email, "password": PASSWORD})
    assert logged_in.status_code == 200, logged_in.text
    return email


def onboarding_payload(**overrides: object) -> dict[str, object]:
    return {
        "property_name": "Villa Senja Ubud",
        "property_type": "villa_portfolio",
        "city": "Ubud",
        **overrides,
    }
