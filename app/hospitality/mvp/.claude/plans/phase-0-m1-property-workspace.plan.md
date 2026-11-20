# Plan: Phase 0 — Milestone 1: Property Workspace

**Source PRD**: `.claude/prds/phase-0-whatsapp-wedge.prd.md`
**Selected Milestone**: 1 — Property workspace
**Complexity**: Large

## Summary

An operator signs up with the existing email sign-in, completes a one-screen onboarding (property name, type, city), and lands in a workspace that shows their property on the Free plan and nothing belonging to anyone else. This milestone also lays the three foundations every later milestone depends on: a dedicated database, a tenant-scoped database session that makes row-level security actually apply, and the configurable business values with their agreed defaults.

No new packages are needed.

## Decisions needed before coding

| # | Decision | Recommendation | Why it matters |
|---|---|---|---|
| D1 | Which database does this app use? | **A dedicated database `hospitality_mvp`** on the same local server; point `backend/.env` at it and run `alembic upgrade head` | `prefab_db` is shared with an older app. Its `user`, `permission` and `role` tables have a different shape (`permission` has no `code` column; `user.language_preference` is required), so RBAC seeding at startup and sign-up cannot work against it. A fresh database avoids altering or dropping another app's tables. Requires one backend restart |
| D2 | What happens to the 143 tables already migrated into `prefab_db`? | Leave them for now; remove later with `alembic downgrade 0001` against `prefab_db` if you want it clean | Removing is optional and reversible; nothing in this plan depends on it |
| D3 | How is tenant isolation enforced while the API connects as the `postgres` superuser? | Each tenant-scoped transaction switches to a no-login role `app_rw` (`SET LOCAL ROLE`) and sets `app.tenant_id` | Superusers bypass row-level security. Switching role inside the transaction makes the existing policies apply with no password or connection-string change |
| D4 | One property per sign-up, or several? | One property at onboarding; a user with several memberships uses the first active one | Multi-property switching is not in the PRD's MVP |

## Requirements restated

- Sign-up and sign-in reuse the existing email + password flow; no second user table, login page or auth guard.
- A signed-in user with no property is sent to onboarding; a user with a property is sent to the workspace.
- Onboarding creates, in one all-or-nothing operation: the tenant, its Free plan subscription and entitlements, the owner membership, and inside the tenant data the tenant profile, legal entity, property, owner staff profile and owner role.
- The workspace shows the property name, type, the Free plan and payment links used this month against the limit (0 of 30), with empty states for inbox and payment links.
- A user can never read or change another tenant's rows, including by guessing ids.
- Business values are stored as configuration with the PRD defaults, readable through one function, and changeable without a code change.
- Staff screens are usable in Bahasa Indonesia and English.

## Patterns to Mirror

| Category | Source | Pattern |
|---|---|---|
| Naming | `backend/app/routers/sample_items.py:1`, `backend/app/models/tenant/organisation/property.py` | Feature routers in `app/routers/<feature>.py` exporting `<feature>_router`; entities imported from `app.models.tenant` / `app.models.control_plane` |
| Errors | `backend/app/rbac/router.py:95`, `:116` | `raise HTTPException(status_code=..., detail="<own message>")`; never a bare 404 |
| Logging | `backend/app/rbac/me.py:34`, `:82` | `log = logging.getLogger(__name__)`; `log.info("... %s", value)` |
| Auth | `backend/app/session/dependencies.py:22`, `backend/app/rbac/dependencies.py:97` | `Depends(get_current_user)` from the session prefab; `int(user["user_id"])`; `require_permission(code, desc)` for gated routes |
| Data access | `backend/app/database.py` (`get_session`), `backend/app/rbac/router.py:78` | `AsyncSession` via `Depends`, `await session.exec(select(...))`, response via `Read.model_validate(obj)` |
| Response shape | `backend/app/rbac/router.py:47`, `:78` | Plain typed response models (`response_model=...`); the prefab does not use a success/data/error envelope, so new routes follow the prefab |
| Frontend API | `frontend/lib/api-client.ts:57` | Calls go through the shared request helper with `credentials: "include"`; errors as `ApiError` |
| Frontend pages | `frontend/app/(authenticated)/dashboard/page.tsx:22` | `"use client"` pages under `(authenticated)/`, session from `useSessionState()` |
| Menus | `backend/docs/rbac-spec.yaml` (`menus:`) | Menu entries live only in the spec; one entry per top-level page |
| Tests (backend) | `backend/tests/test_health.py:1`, `backend/tests/conftest.py:52` | `async def test_...(client)` with the in-process `httpx` client; no test classes |
| Tests (frontend) | `frontend/lib/auth-token.test.ts:1` | `vitest` with `describe` / `it` beside the module under test |

No existing pattern covers tenant-scoped sessions, PostgreSQL-backed tests, or UI translation; those are new in this plan.

## Files to Change

| File | Action | Why |
|---|---|---|
| `backend/.env` | UPDATE | Point `PREFAB_DATABASE_URL` at `hospitality_mvp` (D1) |
| `backend/migrations/versions/0004_app_role_and_free_plan.py` | CREATE | `app_rw` role and grants; seed one pooled cluster row and the Free plan with its limit |
| `backend/app/tenancy/__init__.py` | CREATE | New module: tenant context and scoped session |
| `backend/app/tenancy/context.py` | CREATE | `TenantContext` and the dependency that resolves the signed-in user's active membership |
| `backend/app/tenancy/session.py` | CREATE | `get_tenant_session`: applies role and tenant id at the start of every transaction |
| `backend/app/tenancy/settings.py` | CREATE | Typed business values, defaults, and the read function (plan / property / platform level) |
| `backend/app/services/__init__.py` | CREATE | Service package |
| `backend/app/services/onboarding.py` | CREATE | All-or-nothing workspace creation |
| `backend/app/services/workspace.py` | CREATE | Workspace summary: property, plan, usage |
| `backend/app/routers/onboarding.py` | CREATE | `POST /api/onboarding`, `GET /api/onboarding/status` |
| `backend/app/routers/workspace.py` | CREATE | `GET /api/workspace` |
| `backend/app/schemas/workspace.py` | CREATE | Request and response shapes with validation |
| `backend/app/main.py` | UPDATE | Register the two routers |
| `backend/app/config.py` | UPDATE | `TEST_DATABASE_URL` setting for PostgreSQL tests |
| `backend/docs/rbac-spec.yaml` | UPDATE | Dashboard menu entry |
| `backend/tests/pg/conftest.py` | CREATE | PostgreSQL test database: create, migrate, tenant fixtures, teardown |
| `backend/tests/pg/test_tenant_session.py` | CREATE | Isolation and fail-closed tests |
| `backend/tests/pg/test_onboarding.py` | CREATE | Onboarding flow, validation, rollback, duplicates |
| `backend/tests/pg/test_workspace.py` | CREATE | Workspace summary and cross-tenant access |
| `backend/tests/test_business_settings.py` | CREATE | Defaults and overrides (no database) |
| `backend/pyproject.toml` | UPDATE | Register `unit` and `integration` markers |
| `frontend/lib/i18n.ts` + `frontend/lib/i18n.test.ts` | CREATE | Two-language dictionary and lookup, no new package |
| `frontend/lib/workspace-api.ts` | CREATE | Typed calls for onboarding and workspace |
| `frontend/app/(authenticated)/onboarding/page.tsx` | CREATE | Onboarding form |
| `frontend/app/(authenticated)/dashboard/page.tsx` | UPDATE | Replace the sample content with the workspace home |
| `frontend/components/LanguageSwitch.tsx` | CREATE | Staff language toggle |
| `frontend/middleware.ts` | UPDATE | Protect `/onboarding` |
| `components-be.yaml`, `components-fe.yaml` | UPDATE | Register new artifacts |

## Tasks

Each task is test-first: write the failing test, make it pass, then tidy.

### Task 1: Dedicated database
- **Action**: Create `hospitality_mvp`, set `PREFAB_DATABASE_URL` in `backend/.env`, run `alembic upgrade head`. Ask the user to restart the backend so startup creates the prefab tables and seeds RBAC there.
- **Mirror**: `instructions/backend.md` Step 4.
- **Validate**: `uv run alembic current` shows `0003 (head)`; after restart, `user`, `role`, `permission` exist with the prefab shape and the admin role is seeded.

### Task 2: PostgreSQL test harness
- **Action**: Add `tests/pg/conftest.py` that creates a throwaway database, runs migrations to head, yields an in-process client bound to it, and drops it afterwards. Tests are skipped with a clear reason when no PostgreSQL server is reachable. Register `unit` / `integration` markers.
- **Mirror**: `backend/tests/conftest.py:52` (client fixture); the SQLite suite stays untouched.
- **Validate**: `uv run pytest tests/pg -q` runs one placeholder test green; `uv run pytest -q` still passes the existing 432.

### Task 3: Migration `0004` — application role and Free plan
- **Action**: Create role `app_rw` (no login) with read/write on tenant tables and read on control-plane catalogs; seed one `dbcluster` row for the local pooled cluster and the `free` plan with `planmodule.limits = {"payment_links_per_month": 30}` for the `crm` and `payments` modules. Downgrade reverses both.
- **Mirror**: `backend/migrations/versions/0002_control_plane_schema.py` (one statement per `op.execute`, seeds as constants).
- **Validate**: upgrade → downgrade → upgrade on the test database; `alembic check` reports nothing for the new tables.

### Task 4: Tenant-scoped session
- **Action**: `get_tenant_session` yields a session that, at the start of **every** transaction (including after a commit), switches to `app_rw` and sets `app.tenant_id` from the tenant context. `TenantContext` is resolved from the signed-in user's active membership; no membership → 403 with its own message.
- **Mirror**: `backend/app/database.py` (`get_session`); `backend/app/session/dependencies.py:22`.
- **Validate** (`tests/pg/test_tenant_session.py`): tenant A cannot read or update tenant B's property; inserting a row with another tenant's id is rejected; with no tenant set, zero rows are visible; isolation still holds after a commit inside the same session.

### Task 5: Business values
- **Action**: One typed definition of the PRD's configurable values with defaults, and one function that returns the effective value: plan limit from `planmodule.limits`, property values from `property.settings`, platform values from application settings. Unknown keys and wrong types are rejected.
- **Mirror**: `backend/app/config.py` (typed settings).
- **Validate** (`tests/test_business_settings.py`): defaults equal the PRD table; an override in `property.settings` wins; an invalid override raises a clear error.

### Task 6: Onboarding service and endpoints
- **Action**: `POST /api/onboarding` accepts property name, property type (from the allowed list) and city; creates tenant (unique code derived from the name), subscription to `free`, entitlements, owner membership, tenant profile, legal entity, property, owner staff profile, owner role and assignment in one transaction. A user who already has a workspace gets 409. `GET /api/onboarding/status` says whether the user has a workspace.
- **Mirror**: `backend/app/rbac/router.py:87` (create with 409 on conflict); `Read.model_validate`.
- **Validate** (`tests/pg/test_onboarding.py`): happy path creates every row; second call returns 409; invalid type or blank name returns 422; a forced failure midway leaves no tenant behind; two users choosing the same property name both succeed with different codes; unauthenticated returns 401.

### Task 7: Workspace summary endpoint
- **Action**: `GET /api/workspace` returns the property (name, type, city, code), plan name, payment links used this month and the limit, and the user's role in the workspace.
- **Mirror**: `backend/app/rbac/me.py` (single summary endpoint the frontend reads once).
- **Validate** (`tests/pg/test_workspace.py`): returns the caller's own property; usage is `0 / 30`; a user without a workspace gets 403; user A never receives user B's data.

### Task 8: Frontend — language helper
- **Action**: `lib/i18n.ts` with Bahasa Indonesia and English dictionaries, a lookup that falls back to English, and a per-browser saved choice; `LanguageSwitch` component.
- **Mirror**: `frontend/lib/auth-token.test.ts:1`.
- **Validate**: `npm test` — lookup, fallback and missing-key tests pass.

### Task 9: Frontend — onboarding and workspace home
- **Action**: `/onboarding` form with inline validation and server error display. `/dashboard` becomes the workspace home: property card, Free plan card with links used, and empty states for inbox and payment links. On load, a user without a workspace is redirected from `/dashboard` to `/onboarding`, and a user with one from `/onboarding` to `/dashboard`. Add `/onboarding` to the middleware matcher and a Dashboard entry to the menu spec.
- **Mirror**: `frontend/app/(authenticated)/dashboard/page.tsx:22`; `frontend/lib/api-client.ts:57`; CLAUDE.md navigation rules.
- **Validate**: `npm run build` and `npm run lint` succeed. Manual check after a backend restart: sign up → onboarding → dashboard shows the property and `0 / 30`.

### Task 10: Registers and review
- **Action**: Update `components-be.yaml` and `components-fe.yaml`; run code review and security review on the diff (auth, tenant isolation and database queries are all touched); fix critical and high findings.
- **Validate**: review reports no critical or high issues.

## Validation

```bash
cd backend
uv run ruff check app tests && uv run ruff format --check app/tenancy app/services app/routers app/schemas tests
uv run pytest -q                      # SQLite suite (existing 432 + new unit tests)
uv run pytest tests/pg -q             # PostgreSQL integration tests
uv run pytest --cov=app/tenancy --cov=app/services --cov=app/routers/onboarding.py --cov=app/routers/workspace.py --cov-report=term-missing   # needs pytest-cov, see Risks
uv run alembic upgrade head && uv run alembic check

cd ../frontend
npm test && npm run lint && npm run build
```

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Role and tenant settings are lost after a commit, silently turning isolation off (superuser bypass) | Medium | Re-apply at every transaction start; a dedicated test commits mid-session and re-checks isolation |
| Tenant-scoped code accidentally uses the plain `get_session` | Medium | Tenant tables are only touched through `app/tenancy` and services; a test asserts every tenant route depends on `get_tenant_session` |
| Onboarding writes control-plane and tenant rows in one transaction, which needs both privilege levels | Medium | Service runs control-plane writes first, then switches to the tenant scope inside the same transaction; rollback test proves all-or-nothing |
| `pytest-cov` is not in `packages-be.yaml`, so the 80% coverage figure cannot be measured | High | Ask before installing (project package policy). Without it, coverage is argued from the test list, not measured |
| Menus are cached until the backend restarts | High | Ask for a restart after editing `rbac-spec.yaml`; do not check the menu in a browser before that |
| The legacy `prefab_db` keeps 143 unused tables | Low | Optional cleanup by downgrade (D2) |
| NextAuth middleware and the session cookie disagree about who is signed in on `/onboarding` | Low | Reuse `AuthGuard` exactly as `/dashboard` does; no new guard |

## Out of this milestone

Inbox, payment links, transfer proofs, limit enforcement, a settings screen for editing business values, staff invitations, and multi-property switching. Each belongs to a later milestone or is outside the PRD's MVP.

## Acceptance
- [ ] All tasks complete
- [ ] Validation passes
- [ ] Patterns mirrored, not reinvented
- [ ] A new operator reaches a workspace showing their property and `0 / 30` links in one sitting
- [ ] Cross-tenant read and write attempts fail in tests
