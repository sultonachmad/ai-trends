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

import json
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
    # The app's lifespan creates the prefab tables and seeds RBAC on startup; tests
    # bypass the lifespan, so do both here (create_all skips what migrations built).
    from sqlmodel import SQLModel

    import app.models  # noqa: F401 — registers all table metadata
    import app.rbac.models  # noqa: F401

    from app.rbac.seed import seed_rbac
    from app.services.workspace_access import ensure_manager_role

    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)
    seed_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with seed_factory() as seed_session:
        await seed_rbac(seed_session)
        await ensure_manager_role(seed_session)
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
    monkeypatch.setattr(settings, "PAYMENT_SIMULATOR_ENABLED", True)
    monkeypatch.setattr(settings, "CHANNEL_SIMULATOR_ENABLED", True)
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://app.test")


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


@pytest.fixture
async def third_client(_pg_override: None) -> AsyncIterator[httpx.AsyncClient]:
    """A third independent browser session (e.g. a second staff member)."""
    async for http in _new_client():
        yield http


@pytest.fixture
async def guest(_pg_override: None) -> AsyncIterator[httpx.AsyncClient]:
    """A browser with no session at all — the guest opening a pay link."""
    async for http in _new_client():
        yield http


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


async def make_link(client: httpx.AsyncClient, **overrides: object) -> dict:
    """Create a payment link on the client's property; returns the creation answer."""
    payload = {"amount": 850000, "description": "DP Villa 2 malam", **overrides}
    response = await client.post("/api/payment-links", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def token_of(created: dict) -> str:
    """The secret token from a creation answer's url."""
    return created["url"].rsplit("/", 1)[1]


async def pay(client: httpx.AsyncClient, token: str, method: str = "qris", bank: str | None = None):
    """Choose a method on the public page and simulate the guest paying."""
    body = {"method": method} if bank is None else {"method": method, "bank": bank}
    started = await client.post(f"/api/pay/{token}/payments", json=body)
    assert started.status_code == 201, started.text
    return await client.post(f"/api/simulator/payments/{token}/pay")


JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 64
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
BANK = {"bank_name": "BCA", "account_number": "1234567890", "account_holder": "PT Villa Senja"}


@pytest.fixture(autouse=True)
def _document_storage(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Each test stores uploaded files in its own temporary folder."""
    folder = tmp_path / "documents"
    monkeypatch.setattr(settings, "DOCUMENT_STORAGE_DIR", str(folder))
    return folder


def image(seed: str = "a", kind: bytes = JPEG_BYTES) -> bytes:
    """A small valid image whose content (and so its hash) depends on `seed`."""
    return kind + seed.encode()


async def set_bank_account(client: httpx.AsyncClient) -> None:
    response = await client.put("/api/settings/bank-account", json=BANK)
    assert response.status_code == 200, response.text


async def guest_uploads(
    client: httpx.AsyncClient, token: str, content: bytes | None = None, consent: str = "true"
) -> httpx.Response:
    """A guest uploads a transfer screenshot on the public pay page."""
    return await client.post(
        f"/api/pay/{token}/proofs",
        files={"file": ("bukti.jpg", content if content is not None else image(), "image/jpeg")},
        data={"consent": consent},
    )


async def staff_uploads(
    client: httpx.AsyncClient, content: bytes | None = None, **fields: object
) -> httpx.Response:
    """Staff upload a transfer screenshot (for a link, or with amount + description)."""
    return await client.post(
        "/api/transfer-proofs",
        files={"file": ("bukti.jpg", content if content is not None else image(), "image/jpeg")},
        data={key: str(value) for key, value in fields.items()},
    )


async def add_staff_member(
    session: AsyncSession,
    client: httpx.AsyncClient,
    workspace: dict,
    role: str = "manager",
) -> dict:
    """Sign `client` up as a second, non-owner staff member of `workspace`.

    There is no invite flow yet, so the membership is written directly. Access is
    configured as in production: the `role` ("manager" by default, or a role name
    created by the test, or None for a member with no access at all).
    """
    from sqlmodel import select

    from app.auth.models import User
    from app.models.control_plane import TenantMembership
    from app.models.tenant import StaffMember

    email = await sign_up_and_in(client)
    user = (await session.exec(select(User).where(User.email == email))).one()
    staff = StaffMember(
        tenant_id=workspace["tenant"]["id"],
        user_id=user.id,
        display_name=email.split("@")[0],
        email=email,
        department="front_office",
    )
    session.add(staff)
    await session.flush()
    session.add(
        TenantMembership(
            tenant_id=workspace["tenant"]["id"],
            user_id=user.id,
            status="active",
            is_tenant_owner=False,
            staff_member_id=staff.id,
            last_property_id=workspace["property"]["id"],
        )
    )
    await session.commit()
    if role is not None:
        from app.rbac.models import Role

        role_row = (await session.exec(select(Role).where(Role.name == role))).first()
        assert role_row is not None, f"role {role!r} does not exist (create it in the test)"
        await session.execute(
            text(
                "INSERT INTO user_roles (user_id, role_id) VALUES (:u, :r) ON CONFLICT DO NOTHING"
            ),
            {"u": user.id, "r": role_row.id},
        )
        await session.commit()
    return {"user_id": user.id}


async def set_link_limit(session, tenant_id: str, limits: dict[str, object] | None) -> None:
    """Set the tenant's payments limits (e.g. {"payment_links_per_month": 3}); None = no module."""
    if limits is None:
        await session.execute(
            text("UPDATE tenantentitlement SET enabled = false WHERE tenant_id = :t"),
            {"t": tenant_id},
        )
    else:
        await session.execute(
            text(
                "UPDATE tenantentitlement SET limits = CAST(:limits AS jsonb) "
                "WHERE tenant_id = :t AND module_code = 'payments'"
            ),
            {"t": tenant_id, "limits": json.dumps(limits)},
        )
    await session.commit()


async def make_room_type(client: httpx.AsyncClient, **overrides: object) -> dict:
    """Create a room type on the client's property; returns it."""
    payload = {"name": "Deluxe", "kind": "room", "units": 3, "max_guests": 2, **overrides}
    response = await client.post("/api/room-types", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def set_business_settings(session, property_id: str, **values: object) -> None:
    """Override business settings of a property (e.g. max_room_types=1)."""
    await session.execute(
        text(
            "UPDATE property SET settings = settings || jsonb_build_object('business', "
            "COALESCE(settings->'business', '{}'::jsonb) || CAST(:values AS jsonb)) "
            "WHERE id = :p"
        ),
        {"values": json.dumps(values), "p": property_id},
    )
    await session.commit()


async def make_rate_plan(
    client: httpx.AsyncClient, rooms: list[dict], amount: int = 500000, **overrides: object
) -> dict:
    """Create a rate plan selling `rooms` at `amount` a night; returns it."""
    payload = {
        "name": "Harga Normal",
        "prices": [{"room_type_id": room["id"], "amount": amount} for room in rooms],
        **overrides,
    }
    response = await client.post("/api/rate-plans", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def make_booking(
    client: httpx.AsyncClient, room: dict, plan: dict, arrival: str, departure: str, **overrides
) -> dict:
    """Enter a booking for `room` on `plan`; returns its detail."""
    payload = {
        "arrival": arrival,
        "departure": departure,
        "room_type_id": room["id"],
        "rate_plan_id": plan["id"],
        "guest_name": "Budi Santoso",
        **overrides,
    }
    response = await client.post("/api/bookings", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def sold_matches_bookings(session, tenant_id: str) -> bool:
    """True when units sold per night equal what the confirmed bookings hold."""
    result = await session.execute(
        text(
            """
            WITH held AS (
              SELECT u.unit_type_id, night::date AS stay_date, count(*) AS units
              FROM reservationunit u
              CROSS JOIN LATERAL generate_series(
                u.arrival_date, u.departure_date - 1, interval '1 day') AS night
              WHERE u.tenant_id = :t AND u.status = 'confirmed'
              GROUP BY 1, 2
            ),
            sold AS (
              SELECT unit_type_id, stay_date, sold AS units
              FROM inventoryday WHERE tenant_id = :t AND sold > 0
            )
            SELECT count(*) FROM (
              (SELECT * FROM held EXCEPT SELECT * FROM sold)
              UNION ALL
              (SELECT * FROM sold EXCEPT SELECT * FROM held)
            ) AS difference
            """
        ),
        {"t": tenant_id},
    )
    return int(result.scalar_one()) == 0


async def make_test_listing(client: httpx.AsyncClient) -> dict:
    """List the client's property on the simulated agency; returns the listing."""
    response = await client.post("/api/simulator/channels/listings")
    assert response.status_code == 201, response.text
    return response.json()


async def connect_channel(client: httpx.AsyncClient, *, tested: bool = True) -> dict:
    """A connection to the simulated agency for a fresh test listing (tested by default)."""
    listing = await make_test_listing(client)
    created = await client.post(
        "/api/channel-connections",
        json={"channel_code": "simulator", "external_property_id": listing["hotel_id"]},
    )
    assert created.status_code == 201, created.text
    connection = created.json()
    if tested:
        response = await client.post(f"/api/channel-connections/{connection['id']}/test")
        assert response.status_code == 200, response.text
        connection = response.json()
    return connection
