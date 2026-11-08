<!-- Prefab: rbac v0.2.0 -->

# RBAC Prefab — Agent Instructions

This prefab adds a unified "menu-permission binding" RBAC system to the Next.js + FastAPI base. A single canonical `permission_code` string (`module:action`) acts as the shared key between backend endpoints, frontend route guards, and navigation menus.

## Architecture & File Structure

```text
backend/
  app/rbac/
    models.py        # SQLModel tables: Role, UserRole, Permission, RolePermission
    dependencies.py  # require_permission() factory + registry
    seed.py          # Startup seed: admin user, admin role, permissions
    router.py        # CRUD routers for roles, permissions, users
    me.py            # GET /api/me — source of truth for FE RBAC context
                     #   reads menus from backend/docs/rbac-spec.yaml (no menu table)

backend/docs/
  rbac-spec.yaml     # Single source of truth for roles, permissions, AND menus

frontend/
  lib/rbac-store.tsx             # RbacProvider + useRbac() + useCan()
  components/RbacGuard.tsx       # Component to hide children without permission
  components/DynamicNav.tsx      # Whole app nav frame (aside or top bar); never mount it beside the layout's Sidebar/Nav
  components/Sidebar.tsx         # Dynamic sidebar reading from useRbac() menus
  app/(authenticated)/admin/     # Admin UIs for users, roles, and permissions
```

## System Bootstrapping & The Lifecycle Rule

The system relies on a specific sequence for registering and applying permissions. Understanding this lifecycle is critical for adding new features without hitting constraint errors.

1. **Registration via Code:** Permissions are *only* registered into the system when a backend route explicitly uses `require_permission("module:action", "Description")` as a dependency. Import all routers in `main.py` BEFORE `lifespan()` is defined, so `require_permission()` calls execute at module-load time.
2. **Database Persistence:** On application startup, `seed.py` scans all registered permissions and upserts them into the database.
3. **Role Assignment:** During that same startup, `seed.py` assigns all permissions to the admin role.

**The lifecycle order is critical**
  ```
  main.py imports routers
    ↓ (permissions registered in _PERMISSION_REGISTRY)
  create_app() completes
    ↓
  lifespan() runs
    ↓
  seed_rbac() upserts permissions from registry
  ```

### First-admin bootstrap
No admin user ships by default. On first boot, set `RBAC_SEED_ADMIN=true` and
`RBAC_ADMIN_PASSWORD=<chosen password>` (optionally `RBAC_ADMIN_EMAIL`, default
`admin@example.com`) to seed the first admin user. Seeding is email-idempotent —
rotating the password later requires a manual database change, not an env flip.
The seed rejects an `RBAC_ADMIN_PASSWORD` that is empty, non-printable,
contains `$ ` `` ` `` `"` `\`, or exceeds 72 UTF-8 bytes (the bcrypt limit).
A rejected value is treated as absent and no admin is seeded.
* **Admin Role:** `admin` *(Note: The system checks for the exact string `"admin"` to grant super-user bypass privileges. Do not rename this role).*

---

## Navigation Menus — YAML-driven

Menus are defined in `backend/docs/rbac-spec.yaml`. The backend reads this file at startup and caches it in memory.
The file must ship with the backend: a Dockerfile for `backend/` must copy `docs/` into the image (and `.dockerignore` must not exclude it), or `/api/me` returns no menus.

### How it works
1. `GET /api/me` reads the `menus:` section from `backend/docs/rbac-spec.yaml`
2. Filters by `active: true` AND the user's permission codes
3. Admin users see all active menus regardless of permission
4. The frontend renders whatever `/api/me` returns — no client-side filtering

### Menu entry format
```yaml
menus:
  - name: Orders           # display label
    path: /orders          # frontend route
    icon: cart             # key in ICON_MAP (Sidebar.tsx)
    order: 20              # sort position (ascending)
    active: true           # true = visible, false = hidden
    permission: orders:view # (optional) gates visibility by permission code

  - name: Reports
    path: /reports
    icon: chart
    order: 30
    active: true
    children:              # collapsible group with nested items
      - name: Sales
        path: /reports/sales
        icon: chart
        order: 1
        active: true
        permission: reports:view
      - name: Audit Log
        path: /reports/audit
        icon: archive
        order: 2
        active: false      # ← hidden until the page is built
```

### `active` flag
- `active: true` — menu item is shown in the sidebar (subject to permission check)
- `active: false` — menu item is hidden from the sidebar; use this for features under development
- The route and page can exist while the menu is inactive — users just can't navigate to it from the sidebar
- When ready to ship, flip to `active: true` and restart (or call `POST /api/me/reload-menus` as a user with the `menus:reload` permission; admins have it)

### To add a new menu item
1. Edit `backend/docs/rbac-spec.yaml` — add the entry under `menus:`
2. Restart the backend (or call `POST /api/me/reload-menus` to hot-reload; needs a logged-in session with the `menus:reload` permission, which admins have, otherwise it returns 401/403)
3. Make sure the `icon` key exists in `ICON_MAP` in `Sidebar.tsx`
4. No seed.py changes needed — menus are not in the database

---

## Workflow: Adding a New Feature

When building a new permission-gated feature, follow these steps to keep the design, backend, and frontend in sync:

### 1. Update the Spec (`backend/docs/rbac-spec.yaml`)
This file is the architectural source of truth. Define your actors, capabilities, and menus here first.
```yaml
roles:
  editor:
    description: Can create and edit content.
    permissions: [content:view, content:edit]

permissions:
  "content:view": "Browse published content"
  "content:edit": "Create and edit content"

menus:
  - name: Content
    path: /content
    icon: file
    order: 20
    active: true
    permission: content:view
```

### 2. Guard the Backend Routes
Use `require_permission` as a FastAPI dependency. This simultaneously secures the route and registers the permission code.

```python
from app.rbac.dependencies import require_permission

@router.get("/content")
async def list_content(
    user: dict = require_permission("content:view", "Browse published content"),
    db: AsyncSession = Depends(get_session),
):
    ...
```

### 3. Guard the Frontend UI
The frontend relies entirely on `/api/me` for its permission context. There is no static menu configuration on the frontend.

**Page & Component Guards:**
```tsx
// 1. Hook-based check (for logic or page-level guards)
const { can } = useRbac();
if (!can("content:edit")) return null;

// 2. Component wrapper (for UI elements like buttons)
<RbacGuard permission="content:edit" fallback={<span>View Only</span>}>
  <EditButton />
</RbacGuard>
```

**Navigation:**
The `<Sidebar/>` component automatically updates based on the menus returned by `/api/me`. Ensure your `icon` key exists in `ICON_MAP` within `Sidebar.tsx`.

---

## Core Guidelines

* **DO** use the `module:action` naming convention for permissions (e.g., `orders:view`, `orders:edit`).
* **DO** rely on the idempotent `seed_rbac` function in the FastAPI `lifespan()` to apply changes.
* **DO** add menus to `backend/docs/rbac-spec.yaml`
* **DO** set `active: false` on menu entries for features under development.
* **DON'T** manually insert permissions into the database. Let the route dependencies generate them.
* **DON'T** use `from __future__ import annotations` in `models.py`. SQLModel relationships require classes to be resolved at import time, and the future import breaks this behavior.
* **DON'T** hardcode navigation logic on the frontend. The sidebar and dynamic navs must always render what `/api/me` returns.
