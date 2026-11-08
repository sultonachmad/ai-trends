from collections.abc import AsyncGenerator

from sqlalchemy import Table
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import settings

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args=connect_args,
)

# AsyncSession comes from sqlmodel (not sqlalchemy.ext.asyncio) so both
# `session.exec(select(...))` (SQLModel idiom, returns entities directly) and
# `session.execute(select(...))` (SQLAlchemy Core idiom) work — see AGENTS.md.
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


def startup_tables() -> list[Table]:
    """Tables `create_db_and_tables()` may create: all except migration-only ones.

    Tables tagged `info={"migration_only": True}` (see `MIGRATION_ONLY` in
    app/crud/base_model.py) are created by `alembic upgrade head` only.
    """
    return [t for t in SQLModel.metadata.tables.values() if not t.info.get("migration_only")]


async def create_db_and_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all, tables=startup_tables())
