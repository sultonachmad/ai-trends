<!-- Prefab: crud-scaffold v0.2.0 -->

# CRUD Scaffold — Agent Instructions

This prefab adds a generic, reusable CRUD pattern: a SQLModel base class +
router factory on the backend, and `DataTable` / `EntityForm` / `DeleteConfirm`
components + a typed `api-client.ts` factory on the frontend.

Use this prefab as the **blueprint** every time a new domain entity needs
list/create/read/update/delete pages and endpoints — do not hand-roll a new
table component, form component, or set of route handlers per entity.

## Where Things Live

```
backend/
  app/crud/base_model.py       # TimestampMixin + BaseEntity
  app/crud/router_factory.py   # create_crud_router(...) — 5 CRUD endpoints
frontend/
  components/DataTable.tsx     # Generic list view with search + edit/delete
  components/EntityForm.tsx    # Generic data-driven create/edit form
  components/DeleteConfirm.tsx # Delete confirmation modal
  lib/api-client.ts            # createEntityApi<T>(basePath) — typed fetch client
```

## Creating a New Entity — Step by Step

Say you're adding a `Widget` entity with `name` (string), `quantity` (int), and
a `released_at` (datetime).

### Step 1: Define the model and schemas

Create `backend/app/models/widget.py`:

```python
from datetime import UTC, datetime

from app.crud.base_model import BaseEntity
from sqlmodel import SQLModel

def _utcnow() -> datetime:
    """Timezone-aware 'now'."""
    return datetime.now(UTC)

class Widget(BaseEntity, table=True):
    name: str
    quantity: int = 0
    # For datetime fields, use Field() with sa_type=DateTime(timezone=True)
    released_at: datetime | None = Field(
        default=None,
        nullable=True,
        sa_type=DateTime(timezone=True),
    )


class WidgetCreate(SQLModel):
    name: str
    quantity: int = 0
    released_at: datetime | None = None   # plain datetime — see note below


class WidgetUpdate(SQLModel):
    name: str | None = None
    quantity: int | None = None
    released_at: datetime | None = None
```

`BaseEntity` gives you `id`, `created_at`, `updated_at`, `created_by`, and
`updated_by` — do not redeclare them. `WidgetUpdate` fields are all optional —
the factory's PATCH only applies fields the caller sent (`exclude_unset=True`).



### Step 2: Create the router

```python
from app.crud.router_factory import create_crud_router
from app.models.widget import Widget, WidgetCreate, WidgetUpdate

widgets_router = create_crud_router(
    model_class=Widget,
    create_schema=WidgetCreate,
    update_schema=WidgetUpdate,
    prefix="/widgets",
    tag="widgets",
)
```

This gives you:

| Method | Path            | Behavior                     |
|--------|-----------------|-------------------------------|
| GET    | `/widgets`      | List all, optional `?q=`      |
| GET    | `/widgets/{id}` | Get one, 404 if missing       |
| POST   | `/widgets`      | Create, 201                   |
| PATCH  | `/widgets/{id}` | Partial update, 404 if missing |
| DELETE | `/widgets/{id}` | Delete, 204, 404 if missing   |

### Step 3: Register the router

```python
from app.routers.widgets import widgets_router

app.include_router(widgets_router)
```

### Step 4: Create an Alembic migration

```bash
cd backend && uv run alembic revision --autogenerate -m "add widget table"
uv run alembic upgrade head
```

Never create or alter tables by hand — the migration is the only source of
truth for schema changes.

### Step 5: Create frontend pages

```tsx
// app/widgets/page.tsx
"use client";

import { useEffect, useState } from "react";
import { DataTable, type Column } from "@/components/DataTable";
import { DeleteConfirm } from "@/components/DeleteConfirm";
import { createEntityApi } from "@/lib/api-client";

interface Widget {
  id: number;
  name: string;
  quantity: number;
}

const widgetsApi = createEntityApi<Widget>("/widgets");

const columns: Column<Widget>[] = [
  { key: "name", label: "Name" },
  { key: "quantity", label: "Quantity" },
];

export default function WidgetsPage() {
  const [widgets, setWidgets] = useState<Widget[]>([]);
  const [pendingDelete, setPendingDelete] = useState<Widget | null>(null);

  useEffect(() => {
    widgetsApi.list().then(setWidgets);
  }, []);

  const handleDelete = async () => {
    if (!pendingDelete) return;
    await widgetsApi.remove(pendingDelete.id);
    setWidgets((current) => current.filter((widget) => widget.id !== pendingDelete.id));
    setPendingDelete(null);
  };

  return (
    <>
      <DataTable columns={columns} data={widgets} searchable onDelete={setPendingDelete} />
      <DeleteConfirm
        open={pendingDelete !== null}
        itemName={pendingDelete?.name}
        onConfirm={handleDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </>
  );
}
```

```tsx
// app/widgets/new/page.tsx
"use client";

import { EntityForm, type FieldConfig } from "@/components/EntityForm";
import { createEntityApi } from "@/lib/api-client";

const widgetsApi = createEntityApi("/widgets");

const fields: FieldConfig[] = [
  { name: "name", label: "Name", type: "text", required: true },
  { name: "quantity", label: "Quantity", type: "number", required: true },
];

export default function NewWidgetPage() {
  return <EntityForm fields={fields} onSubmit={(data) => widgetsApi.create(data)} />;
}
```

### Step 6: Add Navigation Link (if creating a new feature)

After creating CRUD pages, update the navigation on frontend



## Extending the CRUD Router

### Custom action endpoints

Add non-CRUD actions (e.g. `POST /widgets/import`, `POST /jd-folders/standardize`)
to the **same router object** `create_crud_router` returned, and register them
**before** that router is mounted with `app.include_router(...)`. Two rules keep
them reachable — getting either wrong produces a `404` on the custom path:

- **Decorate the returned router — don't make a second one.** Use
  `@widgets_router.post("/standardize")`. Creating a *separate* `APIRouter` with
  the same prefix and including only one of them is the most common cause of a
  custom action 404.
- **Watch path collisions with `/{id}`.** The factory already owns
  `GET/PATCH/DELETE /{id}`. A collection-level literal like `/standardize` is
  fine; a segment that overlaps the dynamic `/{id}` route can shadow it. FastAPI
  matches in declaration order, so declare literal paths before dynamic ones.

```python
from fastapi import Depends, HTTPException
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session


# Collection-level custom action — reachable at POST /widgets/standardize.
@widgets_router.post("/standardize", response_model=WidgetRead)
async def standardize_widget(
    payload: WidgetStandardizeIn,
    session: AsyncSession = Depends(get_session),
) -> WidgetRead:
    ...  # custom logic here; this router is then mounted once in main.py


@widgets_router.get("/{widget_id}/notes", response_model=list[WidgetNoteRead])
async def list_widget_notes(
    widget_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[WidgetNoteRead]:
    statement = (
        select(Widget)
        .where(Widget.id == widget_id)
        .options(selectinload(Widget.notes))
    )
    widget = (await session.exec(statement)).first()
    if widget is None:
        raise HTTPException(status_code=404, detail="Widget not found")
    return [WidgetNoteRead.model_validate(note) for note in widget.notes]
```

### Relationships

Add `Relationship()` on each side and a foreign key on the "many" side:

```python
from app.crud.base_model import BaseEntity
from sqlmodel import Field, Relationship


class Widget(BaseEntity, table=True):
    name: str
    quantity: int = 0
    notes: list["WidgetNote"] = Relationship(back_populates="widget", cascade_delete=True)


class WidgetNote(BaseEntity, table=True):
    body: str
    widget_id: int | None = Field(default=None, foreign_key="widget.id")
    widget: Widget | None = Relationship(back_populates="notes")
```

The `foreign_key=` string must match the model's `__tablename__` (lowercased
class name by default). When referencing a model from another prefab, import it
directly in the file that declares the FK.

#### Primary-key types across prefabs (avoid FK type mismatches)

A foreign-key column's type **must match the primary-key type of the table it
references**, or the migration fails at `alembic upgrade` with
`Key columns ... are of incompatible types`. The prefabs use two PK conventions
on purpose — match the one the target table actually uses:

| Entity source | PK type | FK column you declare |
|---|---|---|
| Anything extending `BaseEntity` (this prefab) | `int` | `<name>_id: int \| None = Field(default=None, foreign_key="<table>.id")` |
| `UploadedFile` (file-upload prefab) | `str` (uuid hex) | `upload_id: str \| None = Field(default=None, foreign_key="uploadedfile.id")` |

Example — linking a CRUD entity to an uploaded file (note `str`, and the table
name is `uploadedfile`, not `upload`):

```python
from app.crud.base_model import BaseEntity
from sqlmodel import Field


class JobPosting(BaseEntity, table=True):          # id is int (from BaseEntity)
    title: str
    upload_id: str | None = Field(               # str — UploadedFile.id is a uuid string
        default=None, foreign_key="uploadedfile.id"
    )
```

For relationship loading (`selectinload`), the `__future__ import annotations`
restriction, and cascade patterns, see `instructions/backend.md` →
**Relationships**.

### Audit fields (`created_by` / `updated_by`)

`BaseEntity` always has `created_by` and `updated_by` columns. They stay NULL
unless the router is built with `current_user_dep`. They are **server-side
only** — never declare them on `Create` or `Update` schemas.

`updated_by` is stamped on both POST and PATCH (mirroring `updated_at`).
`created_by` is set only on POST.

**With auth-oauth2 / auth-credentials** — pass `get_current_user` directly:

```python
from app.auth.dependencies import get_current_user

widgets_router = create_crud_router(
    model_class=Widget,
    create_schema=WidgetCreate,
    update_schema=WidgetUpdate,
    prefix="/widgets",
    tag="widgets",
    current_user_dep=get_current_user,
)
```

**With auth-session** — wrap `request.state.user` in a dep:

```python
from fastapi import Request

async def get_session_user(request: Request):
    return getattr(request.state, "user", None)

widgets_router = create_crud_router(
    model_class=Widget,
    create_schema=WidgetCreate,
    update_schema=WidgetUpdate,
    prefix="/widgets",
    tag="widgets",
    current_user_dep=get_session_user,
)
```

**Custom actor extraction** — if the default probe order (`sub` → `user_id` →
`id` → `email` → `username`) doesn't match your user shape:

```python
widgets_router = create_crud_router(
    ...,
    current_user_dep=get_current_user,
    actor_from_user=lambda u: u.username,
)
```

Note: `current_user_dep` applies to **all five routes**. Passing
`get_current_user` makes the whole router require auth (401 on missing token).
To keep reads public while stamping writes, omit `current_user_dep` and override
only POST/PATCH with custom handlers that inject the auth dep — see
`router_factory.py` source for the pattern.

## Component Reference

### `DataTable<T>` (`components/DataTable.tsx`)

| Prop         | Type                | Notes                                    |
|--------------|----------------------|-------------------------------------------|
| `columns`    | `Column<T>[]`        | `{ key, label, render?: (value, item) => ReactNode }` |
| `data`       | `T[]`                | Rows to render                            |
| `onEdit`     | `(item: T) => void`  | Omit to hide the Edit action              |
| `onDelete`   | `(item: T) => void`  | Omit to hide the Delete action            |
| `searchable` | `boolean`            | Enables a built-in text filter            |

### `EntityForm` (`components/EntityForm.tsx`)

| Prop          | Type                                              | Notes                      |
|---------------|-----------------------------------------------------|-------------------------------|
| `fields`      | `FieldConfig[]`                                    | `{ name, label, type, required?, options?, placeholder? }` |
| `onSubmit`    | `(data: Record<string, any>) => void \| Promise<void>` | Receives form values on submit |
| `initialData` | `Record<string, any>`                              | Pre-fills for edit forms    |
| `submitLabel` | `string`                                            | Defaults to `"Save"`       |

`type` is one of `text \| email \| number \| date \| select \| textarea \| checkbox`.
`options` is required (and only used) when `type` is `"select"`.

### `DeleteConfirm` (`components/DeleteConfirm.tsx`)

| Prop        | Type         | Notes                                   |
|-------------|--------------|-------------------------------------------|
| `open`      | `boolean`    | Controls visibility                       |
| `onConfirm` | `() => void` | Called when the user confirms              |
| `onCancel`  | `() => void` | Called on cancel or backdrop click        |
| `itemName`  | `string`     | Optional label in the confirmation copy   |

### `createEntityApi<T>(basePath)` (`lib/api-client.ts`)

```ts
const widgetsApi = createEntityApi<Widget>("/widgets");

await widgetsApi.list();          // GET /widgets           -> Widget[]
await widgetsApi.list("acme");    // GET /widgets?q=acme     -> Widget[]
await widgetsApi.get(1);          // GET /widgets/1          -> Widget
await widgetsApi.create(data);    // POST /widgets           -> Widget
await widgetsApi.update(1, data); // PATCH /widgets/1        -> Widget
await widgetsApi.remove(1);       // DELETE /widgets/1       -> void
```

`basePath` must match the `prefix` passed to `create_crud_router`.

## Quick Reference

### DO
- `create_crud_router(...)` for every entity — no hand-written CRUD handlers
- `BaseEntity` (or `TimestampMixin`) for every new entity
- Plain `datetime` on `Create`/`Update` schemas — the router normalizes to UTC
- `DataTable` + `EntityForm` + `DeleteConfirm` for frontend — no one-off components
- `createEntityApi<T>(basePath)` for all entity API calls — no raw `fetch()`
- Alembic migration for every schema change
- `current_user_dep` to enable audit field stamping

### DO NOT
- Bare `datetime` column on a table model — always `Field(..., sa_type=DateTime(timezone=True))`
- `created_by` / `updated_by` on `Create` or `Update` schemas — server-side only
- Non-nullable `created_by` / `updated_by` — must stay NULL for anonymous writes
- Custom table/form components per entity — extend the generic ones
- Business logic in `router_factory.py` — add it as a custom route instead
- Skip the migration step, even for "quick" schema tweaks
