"""Generic CRUD router factory for SQLModel entities.

Call `create_crud_router(...)` once per entity to get a fully wired
`APIRouter` with list / get / create / update / delete endpoints, instead of
hand-writing the same five handlers for every table. See `AGENTS-be.md` in
this prefab for the step-by-step guide to adding a new entity.

No `from __future__ import annotations` here: the route closures below
annotate parameters with `create_schema`/`update_schema`, which are local
variables of `create_crud_router`, not module globals. FastAPI resolves
string annotations via the function's `__globals__` only, so stringifying
them (which the future import does) makes those names unresolvable at
router-build time.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import or_
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session

ModelType = TypeVar("ModelType", bound=SQLModel)
CreateSchemaType = TypeVar("CreateSchemaType", bound=SQLModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=SQLModel)

# Columns owned by TimestampMixin's audit tracking. Excluded from `?q=` search
# and stripped from every request body so a client can never claim authorship.
AUDIT_COLUMNS: frozenset[str] = frozenset({"created_by", "updated_by"})

# Probed in order against whatever `current_user_dep` returns.
_ACTOR_CLAIMS = ("sub", "user_id", "id", "email", "username")


def _normalize_datetimes(data: dict[str, Any]) -> None:
    """Coerce any offset-naive datetime in a request body to UTC-aware, in place."""
    for key, value in data.items():
        if isinstance(value, datetime) and value.tzinfo is None:
            data[key] = value.replace(tzinfo=UTC)


def default_actor_id(user: Any) -> str | None:
    """Extract a stable actor identifier from whatever `current_user_dep` returned."""
    if user is None:
        return None
    if isinstance(user, str):
        return user or None
    for claim in _ACTOR_CLAIMS:
        value = user.get(claim) if isinstance(user, dict) else getattr(user, claim, None)
        if value is not None:
            return str(value)
    return None


def _string_columns(model_class: type[SQLModel]) -> list[object]:
    """Return the mapped columns of `model_class` whose Python type is `str`."""
    columns = []
    for column in sa_inspect(model_class).columns:
        if column.key in AUDIT_COLUMNS:
            continue
        try:
            is_str = column.type.python_type is str
        except NotImplementedError:
            continue
        if is_str:
            columns.append(column)
    return columns


def create_crud_router(
    model_class: type[ModelType],
    create_schema: type[CreateSchemaType],
    update_schema: type[UpdateSchemaType],
    prefix: str,
    tag: str,
    current_user_dep: Callable[..., Any] | None = None,
    actor_from_user: Callable[[Any], str | None] = default_actor_id,
) -> APIRouter:
    """Build a CRUD `APIRouter` for `model_class`.

    Args:
        model_class: The SQLModel table class (`table=True`, with an `id`
            primary key — see `app.crud.base_model.BaseEntity`).
        create_schema: Pydantic/SQLModel schema accepted by `POST`.
        update_schema: Pydantic/SQLModel schema accepted by `PATCH`. Fields
            left unset are not touched (partial update).
        prefix: URL prefix for the router, e.g. `"/api/items"`.
        tag: OpenAPI tag used to group these endpoints in the docs.
        current_user_dep: Optional FastAPI dependency resolving the current
            user. When omitted, `created_by`/`updated_by` stay NULL and no
            auth is enforced on any route.
        actor_from_user: Maps `current_user_dep`'s return value to the string
            stored in `created_by`/`updated_by`.

    Returns:
        An `APIRouter` ready to be mounted with `app.include_router(...)`.
    """
    router = APIRouter(prefix=prefix, tags=[tag])
    entity_name = model_class.__name__

    _mapped_columns = {col.key for col in sa_inspect(model_class).columns}
    has_created_by = "created_by" in _mapped_columns
    has_updated_by = "updated_by" in _mapped_columns

    if current_user_dep is None:
        async def resolve_actor() -> str | None:
            return None
    else:
        async def resolve_actor(current_user: Any = Depends(current_user_dep)) -> str | None:
            return actor_from_user(current_user)

    async def _get_or_404(session: AsyncSession, entity_id: int) -> ModelType:
        entity = await session.get(model_class, entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail=f"{entity_name} not found")
        return entity

    @router.get("", response_model=list[model_class], operation_id=f"{tag}_list")
    async def list_entities(
        q: str | None = Query(default=None, description="Optional search term"),
        session: AsyncSession = Depends(get_session),
    ) -> list[ModelType]:
        statement = select(model_class)
        if q:
            searchable = _string_columns(model_class)
            if searchable:
                pattern = f"%{q}%"
                statement = statement.where(or_(*(column.ilike(pattern) for column in searchable)))
        result = await session.execute(statement)
        return list(result.scalars().all())

    @router.get("/{entity_id}", response_model=model_class, operation_id=f"{tag}_get")
    async def get_entity(
        entity_id: int,
        session: AsyncSession = Depends(get_session),
    ) -> ModelType:
        return await _get_or_404(session, entity_id)

    @router.post("", response_model=model_class, status_code=201, operation_id=f"{tag}_create")
    async def create_entity(
        body: create_schema,
        session: AsyncSession = Depends(get_session),
        actor: str | None = Depends(resolve_actor),
    ) -> ModelType:
        data = body.model_dump()
        for col in AUDIT_COLUMNS:
            data.pop(col, None)
        _normalize_datetimes(data)
        entity = model_class(**data)
        if has_created_by:
            entity.created_by = actor
        if has_updated_by:
            entity.updated_by = actor
        session.add(entity)
        await session.commit()
        await session.refresh(entity)
        return entity

    @router.patch("/{entity_id}", response_model=model_class, operation_id=f"{tag}_update")
    async def update_entity(
        entity_id: int,
        body: update_schema,
        session: AsyncSession = Depends(get_session),
        actor: str | None = Depends(resolve_actor),
    ) -> ModelType:
        entity = await _get_or_404(session, entity_id)
        updates = body.model_dump(exclude_unset=True)
        for col in AUDIT_COLUMNS:
            updates.pop(col, None)
        _normalize_datetimes(updates)
        for field_name, value in updates.items():
            setattr(entity, field_name, value)
        if has_updated_by:
            entity.updated_by = actor
        session.add(entity)
        await session.commit()
        await session.refresh(entity)
        return entity

    @router.delete("/{entity_id}", status_code=204, operation_id=f"{tag}_delete")
    async def delete_entity(
        entity_id: int,
        session: AsyncSession = Depends(get_session),
    ) -> None:
        entity = await _get_or_404(session, entity_id)
        await session.delete(entity)
        await session.commit()

    return router
