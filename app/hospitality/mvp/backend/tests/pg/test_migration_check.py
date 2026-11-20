"""Startup guard: the app must not serve a database that is missing migrations."""

import pytest

from app import db_migrations
from app.database import engine as sqlite_engine
from app.db_migrations import DatabaseNotMigratedError, assert_database_migrated, expected_head

pytestmark = pytest.mark.integration


def test_expected_head_is_the_newest_migration() -> None:
    assert expected_head() >= "0004"


async def test_migrated_database_passes(pg_engine) -> None:
    await assert_database_migrated(pg_engine)


async def test_database_behind_head_is_refused(pg_engine, monkeypatch) -> None:
    monkeypatch.setattr(db_migrations, "expected_head", lambda: "9999")

    with pytest.raises(DatabaseNotMigratedError) as error:
        await assert_database_migrated(pg_engine)

    assert "alembic upgrade head" in str(error.value)
    assert "9999" in str(error.value)


async def test_database_never_migrated_is_refused(pg_engine) -> None:
    async with pg_engine.begin() as conn:
        await conn.exec_driver_sql("ALTER TABLE alembic_version RENAME TO alembic_version_hidden")
    try:
        with pytest.raises(DatabaseNotMigratedError) as error:
            await assert_database_migrated(pg_engine)
        assert "never been migrated" in str(error.value)
    finally:
        async with pg_engine.begin() as conn:
            await conn.exec_driver_sql(
                "ALTER TABLE alembic_version_hidden RENAME TO alembic_version"
            )


async def test_sqlite_is_exempt() -> None:
    """The SQLite test database has no migration-only tables and no alembic_version."""
    await assert_database_migrated(sqlite_engine)
