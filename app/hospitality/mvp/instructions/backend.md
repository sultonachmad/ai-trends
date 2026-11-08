<!-- Prefab: base-backend-fastapi v0.3.0 -->

# Backend Instructions — FastAPI + SQLModel + Alembic

You are building the **backend** of a full-stack project using FastAPI, SQLModel, and Alembic with async PostgreSQL.

## Project Structure

```
backend/
  app/
    main.py        # App factory, router registration
    config.py      # Pydantic Settings (env-driven)
    database.py    # Async SQLModel engine + session
    crud/
      base_model.py     # BaseEntity, TimestampMixin, utc_datetime_field
      router_factory.py # create_crud_router() — generic CRUD wiring
    models/        # Entity models and schemas
    routers/       # Feature routers
    auth/          # Auth module (if installed)
  migrations/
    env.py         # Alembic async runner
    script.py.mako # Migration template (do not edit)
    versions/      # Generated migration files
```

## Quick Start: Add a New Entity

> **Working reference:** `app/models/sample_item.py` + `app/routers/sample_items.py`.
> Copy those two files, rename every occurrence of `SampleItem`, then follow the steps below.

### Pre-flight: Discover Reserved Table Names

Before defining any entity, check which table names are already claimed by installed prefabs:

```bash
grep -r "table=True" backend/app/auth/ 2>/dev/null
```

**Never create a class whose lowercased name matches an existing table.** Common reserved names from auth prefabs: `user`, `authcredential`.

If your domain dictionary includes an entity whose name conflicts with a reserved table name, **decide the replacement class name right now, before writing any file**. Use the replacement name consistently everywhere — in the model file, `__init__.py`, the router, the migration, and any `Relationship()` references. Do **not** create the conflicting class name "temporarily" and rename it later — renaming cascades across every file that referenced it and multiplies the error surface.

Example: if the spec says `User` but `user` is reserved by auth, choose `StaffMember` (or another domain-appropriate name) and write `StaffMember` in every file from the start.

### Step 1: Define the Model and Schemas

Copy `app/models/sample_item.py` → `app/models/my_entity.py` and rename `SampleItem` throughout.

Rules:
- Extend `BaseEntity` — gives you `id`, `created_at`, `updated_at`, `created_by`, `updated_by` for free
- `*Create` — no `id`, no audit fields (server-side only)
- `*Update` — every field optional (PATCH semantics)
- `*Read` — `id: int` not `int | None` (responses always have an id)
- Do **not** override `__tablename__` — the default (lowercased class name) keeps FK strings predictable across prefabs

### Step 2: Register the Model

Add one import to `app/models/__init__.py`:

```python
from app.models.my_entity import MyEntity, MyEntityCreate, MyEntityRead, MyEntityUpdate
```

`main.py` and `migrations/env.py` both already do `import app.models`, so Alembic detects the new table automatically — no other file needs changing.

**MUST: After writing each model file and updating `__init__.py`, run this before continuing:**

```bash
cd backend && uv run python -c "from app.models import *; print('OK')"
```

Fix any error immediately. Do not write multiple model files and verify at the end — a single bad import cascades into a multi-file fix cycle.

### Step 3: Wire the Router

Copy `app/routers/sample_items.py` → `app/routers/my_entities.py`, swap in the three class names, and include the router in `main.py`:

```python
from app.routers.my_entities import my_entities_router
app.include_router(my_entities_router)
```

### Step 4: Generate and Apply Migration

**Always check DB state before generating:**

```bash
cd backend
uv run alembic current          # shows current applied revision; must say "(head)" before autogenerate
uv run alembic upgrade head     # apply any pending migrations first
```

If `alembic upgrade head` fails with `table "X" already exists`, the table exists in the DB but the migration isn't tracked. Stamp it as applied, then autogenerate the new migration on top:

```bash
uv run alembic stamp head       # mark DB as at current head without running SQL
```

Then generate and apply the new migration normally:

```bash
uv run alembic revision --autogenerate -m "add my_entity table"
uv run alembic upgrade head
```

Before applying, open the generated file and verify:
- Table name is the lowercased class name
- All columns are present with correct types
- `created_at`/`updated_at` use `TIMESTAMP WITH TIME ZONE`
- Indexes and foreign keys are correct

Generated migrations reference `sqlmodel.sql.sqltypes.AutoString` for `str` columns — do not delete the `import sqlmodel` line when hand-editing.

### Rollback

```bash
uv run alembic downgrade -1     # one step back
uv run alembic downgrade base   # full rollback
```

---

## DateTime Fields

Use `utc_datetime_field()` from `app.crud.base_model` for **every** datetime column on a table model. See `app/models/sample_item.py` (`due_at`) for the nullable pattern and `app/crud/base_model.py` (`TimestampMixin`) for the `onupdate` pattern.

```python
from app.crud.base_model import BaseEntity, utc_datetime_field

class Event(BaseEntity, table=True):
    starts_at: datetime = utc_datetime_field(default_now=True)    # stamped at INSERT
    ends_at: datetime | None = utc_datetime_field(nullable=True)  # optional, no default
    touched_at: datetime | None = utc_datetime_field(             # refreshed on UPDATE
        nullable=True, onupdate_now=True
    )
```

On **Create/Update schemas** use plain `datetime` — the CRUD router normalizes offset-naive client values to UTC before the INSERT/UPDATE, so no per-entity validator is needed.

**Never** use bare `Field(..., sa_type=DateTime(timezone=True))` directly — always call `utc_datetime_field()` to avoid timezone-naive/aware mismatch errors at runtime.

## Schema Hierarchy — Create / Update / Read

Three separate classes per entity — never collapse them. See `app/models/sample_item.py` for the full pattern.

| Schema | Purpose | Key rule |
|---|---|---|
| `*Create` | POST body | no `id`; caller cannot set audit fields |
| `*Update` | PATCH body | every field `T \| None = None` |
| `*Read` | response | `id: int` (not `int \| None`) |

- Relationship fields go on `*Read` only — never `*Create`/`*Update`
- If `*Read` extends `pydantic.BaseModel` (not `SQLModel`), add `model_config = ConfigDict(from_attributes=True)`
- Always serialize via `model_validate`: `MyEntityRead.model_validate(obj)` — never return a table model directly (carries `_sa_instance_state`)

---

## Relationships

### One-to-Many (Most Common)

Use `Relationship()` on each side and a foreign key on the "many" side:

```python
from typing import Optional
from app.crud.base_model import BaseEntity
from sqlmodel import Field, Relationship


class Widget(BaseEntity, table=True):
    name: str
    notes: list["WidgetNote"] = Relationship(back_populates="widget", cascade_delete=True)


class WidgetNote(BaseEntity, table=True):
    body: str
    widget_id: int | None = Field(default=None, foreign_key="widget.id")
    widget: Optional["Widget"] = Relationship(back_populates="notes")
```

**Critical rules:**
- Foreign key string (`"widget.id"`) must match the table name (lowercased class name by default)
- **NEVER** add `from __future__ import annotations` to files with `Relationship()` — it breaks SQLModel's class resolution
- Singular back-references (nullable): use `Optional["Widget"]` — **never** `"Widget" | None` or `"Widget | None"` (both forms fail because `|` does not evaluate inside quoted strings)
- Collection forward references: use `list["WidgetNote"]` (this form is fine)
- `Relationship()` accepts **only** these kwargs: `back_populates=`, `cascade_delete=`, `link_model=`. Do **not** pass `description=`, `nullable=`, or any other kwarg — SQLModel raises `TypeError: unexpected keyword argument` at startup

### Many-to-Many (Advanced)

Requires a link table with composite primary key:

```python
from sqlmodel import SQLModel, Field, Relationship


class InterviewUser(SQLModel, table=True):
    """Link table for many-to-many relationship."""

    interview_id: int = Field(foreign_key="interview.id", primary_key=True)
    user_id: int = Field(foreign_key="user.id", primary_key=True)


class Interview(BaseEntity, table=True):
    scheduled_at: datetime = utc_datetime_field(nullable=False)
    # Note: link_model must be the CLASS object, NOT a string
    interviewers: list["User"] = Relationship(link_model=InterviewUser)
```

**Important**:
- `link_model` takes the **class object**, not a string like `"InterviewUser"`
- You can define the relationship on one side only (no `back_populates` needed)
- If defining bidirectionally, both sides use `link_model=InterviewUser` (same class object)

### Loading Relationships (selectinload)

Lazy loading does **not** work on `AsyncSession`. Reading an unloaded relationship raises `MissingGreenlet` — and this fails late (after the query and commit both succeed, when the serializer reads the attribute).

Always eager-load with `selectinload`:

```python
from sqlalchemy.orm import selectinload
from sqlmodel import select

statement = select(Widget).options(selectinload(Widget.notes))
widgets = (await session.exec(statement)).all()

statement = (
    select(Widget)
    .where(Widget.id == widget_id)
    .options(selectinload(Widget.notes))
)
widget = (await session.exec(statement)).first()
```

To pull a relationship after a create (where `session.refresh` normally only reloads columns):

```python
await session.refresh(widget, attribute_names=["notes"])
```

The session factory sets `expire_on_commit=False`, so column attributes stay readable after `commit()`. That guarantee does **not** extend to unloaded relationships.

---

## Standard CRUD vs Custom Endpoints

For standard list / get / create / patch / delete: call `create_crud_router()` — see `app/routers/sample_items.py`. You get all five endpoints without writing handlers.

Write custom handlers only for non-CRUD logic (search with joins, bulk actions, file uploads, etc.):

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from app.database import get_session

router = APIRouter(prefix="/api/widgets", tags=["widgets"])

@router.post("/{widget_id}/publish", response_model=WidgetRead)
async def publish_widget(
    widget_id: int, session: AsyncSession = Depends(get_session)
) -> WidgetRead:
    widget = await session.get(Widget, widget_id)
    if widget is None:
        raise HTTPException(status_code=404, detail="Widget not found")
    widget.status = "published"
    session.add(widget)
    await session.commit()
    await session.refresh(widget)
    return WidgetRead.model_validate(widget)
```

**Custom action endpoints must be attached to the router object BEFORE `app.include_router()`** — attaching after means FastAPI already resolved `/{id}` and your action route may shadow it.

### AsyncSession — what needs `await`

| Operation | Correct |
|---|---|
| Select many | `(await session.exec(select(Entity))).all()` |
| Select by PK | `await session.get(Entity, entity_id)` |
| Insert | `session.add(obj)` → `await session.commit()` |
| Reload columns | `await session.refresh(obj)` |
| Delete | `await session.delete(obj)` → `await session.commit()` |

`session.add()` is the **one** call that is NOT awaited — it only stages the object in the identity map.

`session.delete()` IS awaited — `cascade_delete=True` makes SQLAlchemy load child rows before flush; skipping `await` leaves a dangling coroutine and the delete silently never happens.

## Quick Reference

### DO
- Copy `sample_item.py` / `sample_items.py` as the starting point for every new entity
- Use `BaseEntity` for every new entity (gets `id`, timestamps, audit fields)
- Use `utc_datetime_field()` for all datetime columns on table models
- Add new models to `app/models/__init__.py` — `main.py` and `migrations/env.py` pick them up automatically
- Separate `Create` / `Update` / `Read` schemas per entity
- `EntityRead.model_validate(obj)` to serialize responses
- `selectinload()` before reading any relationship attribute
- `async def` for all FastAPI endpoints
- `await` every database call (except `session.add()`)
- Review generated migrations before applying them

### DO NOT
- Override `__tablename__` — breaks cross-prefab foreign-key strings
- Add `from __future__ import annotations` to files with `Relationship()` fields — breaks SQLModel class resolution
- Use bare `Field(..., sa_type=DateTime(timezone=True))` directly — use `utc_datetime_field()` instead
- Pass `link_model` as a string in many-to-many — pass the class object
- Return table models directly — use `model_validate()`
- Raise a 404 without its own `detail` — `HTTPException(status_code=404, detail="Account not found")`, never a bare `HTTPException(status_code=404)`. The browser check treats an API 404 with FastAPI's default `"Not Found"` as a missing route to fix; the app's own message tells it the record does not exist yet
- Read relationships without `selectinload` — raises `MissingGreenlet`
- Import `Session` from sqlmodel — only `AsyncSession` exists
- Skip `await` on `session.exec()`, `.get()`, `.commit()`, `.delete()`
- Hardcode config — use `app/config.py` (Pydantic Settings)
- Email a link with its token in the query string: put the token in the path, `{frontend_url}/invite/{token}`, never `?token=`. A static landing page opens with no token whenever someone visits it directly
- Add a model file without importing it in `app/models/__init__.py`
- Create `.md`, `.txt`, or any documentation files — the task is complete when models import and the migration applies
- Call `Edit()` on a file you have not `Read()` in this session — always Read before Edit
- Use `"ClassName" | None` or `"ClassName | None"` for a relationship back-reference type — both forms fail; use `Optional["ClassName"]` from `typing`

## Component Registry

Read `components-be.yaml` before adding any new entity, router, service, or middleware.
After adding, append the artifact to the matching section in `components-be.yaml`.
