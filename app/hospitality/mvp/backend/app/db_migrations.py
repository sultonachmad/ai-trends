"""Startup guard: refuse to run on a PostgreSQL database that is missing migrations.

The hospitality tables (row-level security, triggers, seeds) are created only by
Alembic — `create_db_and_tables()` skips them on purpose. Pointing the app at a
database that was never migrated used to surface much later, as a 500 on the first
tenant request ("relation … does not exist"). This check turns that into one clear
message at startup.
"""

import logging
from pathlib import Path

from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

log = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"
FIX_HINT = "Run `cd backend && alembic upgrade head` (or `make migrate`), then start again."


class DatabaseNotMigratedError(RuntimeError):
    """The database schema is not at the newest migration."""


def expected_head() -> str:
    """Revision id of the newest migration shipped with this code."""
    head = ScriptDirectory(str(MIGRATIONS_DIR)).get_current_head()
    if head is None:
        raise DatabaseNotMigratedError(f"No migrations found in {MIGRATIONS_DIR}")
    return head


async def _applied_revision(engine: AsyncEngine) -> str | None:
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            return result.scalar_one_or_none()
    except DBAPIError:
        return None  # no alembic_version table: never migrated


async def assert_database_migrated(engine: AsyncEngine) -> None:
    """Raise `DatabaseNotMigratedError` unless `engine`'s database is at head.

    Only PostgreSQL is checked; other dialects (the SQLite unit-test database) cannot
    hold the migration-only tables at all.
    """
    if engine.dialect.name != "postgresql":
        return
    head = expected_head()
    applied = await _applied_revision(engine)
    if applied == head:
        return
    database = engine.url.database
    if applied is None:
        problem = f"Database '{database}' has never been migrated (expected revision {head})."
    else:
        problem = f"Database '{database}' is at revision {applied}, but the code needs {head}."
    log.error("%s %s", problem, FIX_HINT)
    raise DatabaseNotMigratedError(f"{problem} {FIX_HINT}")
