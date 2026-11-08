"""Unit-test setup for this app.

Every test runs against a throwaway SQLite database in a temporary working directory,
never against the database named in backend/.env or the app's own folders.

The database is created once per test session and shared: rows one test writes stay for the
next, and startup tasks may have seeded rows. Write tests that create the data they need and
do not assume an empty table.

Tests run from that temporary directory, so give pytest absolute paths for any report
file (for example --junitxml): a relative one lands there and is deleted at exit.
"""

import atexit
import os
import shutil
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

# Set BEFORE `app` is first imported: app/database.py builds its engine at import time,
# and a process value wins over backend/.env (app/config.py).
_TMP = Path(tempfile.mkdtemp(prefix="app-tests-"))


@atexit.register
def _remove_tmp() -> None:
    os.chdir(tempfile.gettempdir())  # Windows cannot delete the current directory
    shutil.rmtree(_TMP, ignore_errors=True)


os.environ["PREFAB_DATABASE_URL"] = f"sqlite+aiosqlite:///{(_TMP / 'test.db').as_posix()}"
# Relative paths (e.g. the file-upload folder, created at import time) land here.
os.chdir(_TMP)

from app.database import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
async def _app_lifespan() -> AsyncIterator[None]:
    """Create the tables and run every startup task once, against the test database."""
    async with app.router.lifespan_context(app):
        yield
    await engine.dispose()


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """An HTTP client that calls the app in-process."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
