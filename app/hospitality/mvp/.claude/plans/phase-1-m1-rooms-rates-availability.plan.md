# Plan: Rooms, prices and availability (Phase 1, Milestone 1)

**Source PRD**: `.claude/prds/phase-1-channel-manager-booking-engine.prd.md`
**Selected Milestone**: 1 — Rooms, prices and availability
**Complexity**: Large

## Summary

An operator sets up room types (name, number of units, guest capacity) and rate plans (name,
cancellation terms, a base price per room type), then uses a calendar to change the price, close
dates and set a minimum stay for any date range. This is the single source of truth that later
milestones send to channels and show on the booking page, so it also delivers one read function —
"what is sellable, at what price, on these dates" — that those milestones reuse. No bookings exist
yet, so availability in this milestone is simply the number of sellable units, minus closed dates.

## What already exists

The tables were created in Phase 0 Milestone 1 (migration `0003`) and have models and DTOs; nothing
reads or writes them yet.

| Need | Existing table / model |
|---|---|
| Room type | `unittype` — `backend/app/models/tenant/inventory/unit_type.py` |
| Physical unit | `unit` — `backend/app/models/tenant/inventory/unit.py` |
| Rate plan | `rateplan` — `backend/app/models/tenant/rates/rate_plan.py` (requires a cancellation policy and a payment policy) |
| Rate plan ↔ room type | `rateplanunittype` — `rates/rate_plan_unit_type.py` (link only, no price) |
| Price for one date | `ratedaily` — `rates/rate_daily.py` (unique per rate plan + room type + date) |
| Closed date, minimum stay | `restriction` — `rates/restriction.py` (unique per date + room type + rate plan + channel, nulls treated as equal) |
| Cancellation / payment terms | `cancellationpolicy`, `paymentpolicy` — `rates/` |
| Units sold per date | `inventoryday` — `inventory/inventory_day.py` (first used in Milestone 2, with bookings) |

## Decisions (recommendation first — reply "yes" to accept all)

| # | Question | Recommendation |
|---|---|---|
| D1 | How does the operator say how many units a room type has? | Enter a number. The product creates that many units named "<type> 1…n", which can be renamed. Lowering the number retires the highest-numbered units. |
| D2 | Where is the normal price kept? | A base price per rate plan and room type (new column on the link table). The calendar stores only the dates that differ. A date with no override uses the base price. |
| D3 | What does "minimum stay" apply to? | The arrival date: "guests arriving on this date must stay at least N nights". It is the simplest rule to explain and the one channels all support. |
| D4 | Does closing dates apply per room type or per rate plan? | Per room type in this milestone (the room is closed for everyone). Keeping one rate plan direct-only arrives with channels (Milestone 4). |
| D5 | How far ahead can the calendar be edited? | 365 days from today in the property's timezone, as a configurable value. Past dates are read-only. |
| D6 | Cancellation terms on a rate plan | Choose "free cancellation until N days before arrival" (default 7) or "non-refundable", as decided in the PRD. The product keeps the matching policy records behind the scenes. |
| D7 | Deposit | One property setting, default 50%, range 10–100% (PRD decision). Shown in Settings; used from Milestone 7. |
| D8 | Price rules | Whole rupiah, final all-in amounts, within a configurable minimum and maximum (defaults Rp 10.000 and Rp 500.000.000, the same as payment links). |
| D9 | Removing things | A room type or rate plan is switched off (hidden, kept for history), never deleted. |
| D10 | Limits | Configurable: 30 room types, 100 units per room type, 10 rate plans per property; a bulk change may cover at most 365 days. |
| D11 | Who may edit | Any member of the property, as elsewhere today. Restricting prices to the owner waits for staff roles. |
| D12 | Meals | Rate plan carries "room only" or "with breakfast" (already in the table; Traveloka and Tiket need it later). Nothing else from the wider rate model is exposed. |

## Patterns to Mirror

| Category | Source | Pattern |
|---|---|---|
| Naming | `backend/app/services/payment_links.py:280`, `backend/app/routers/payment_links.py` | One service module per topic with verb functions; router file per resource under `/api/...` |
| Errors | `backend/app/routers/payment_links.py:38` (`_guarded`) | Named service exceptions mapped to HTTP answers in the router; 404 for another tenant's id |
| Validation | `backend/app/schemas/payment_links.py` | Pydantic request models with `extra="forbid"` and field constraints; amounts as whole rupiah |
| Config | `backend/app/tenancy/business_settings.py` (`PropertySettings`) | Business numbers as validated settings with defaults; never literals in services |
| Data access | `backend/app/services/link_quota.py`, `services/property_settings.py:34` | Tenant-scoped session, explicit `tenant_id` filter, row lock on the parent before a counted change |
| Upserts | none in the codebase yet | State explicitly: use PostgreSQL `INSERT … ON CONFLICT … DO UPDATE` on the existing unique keys for per-date rows |
| Logging | `backend/app/services/payment_links.py:313` | `log.info` with ids and counts only |
| Migration | `backend/migrations/versions/0006_transfer_proofs.py` | One statement per `op.execute`; design SQL in `.ttest/contexts/schema-tenant.sql` kept in step |
| Tests | `backend/tests/pg/test_payment_links.py`, `tests/pg/test_proof_isolation.py`, `tests/pg/conftest.py` | PostgreSQL integration tests through the HTTP client; isolation tests with `other_client`; helpers in conftest |
| Frontend API | `frontend/lib/payment-links-api.ts` | Typed functions over `request` from `lib/api-client.ts` |
| Frontend helpers | `frontend/lib/payment-link-format.ts` + test, `lib/money.ts` | Pure helpers with vitest tests |
| Pages | `frontend/app/(authenticated)/payment-links/page.tsx`, `components/payments/CreateLinkDialog.tsx` | Workspace load → page; dialogs for create and edit; all text via `lib/i18n.ts` in `id` and `en` |
| Menus | `backend/docs/rbac-spec.yaml` | New pages added as menu entries |

## Files to Change

| File | Action | Why |
|---|---|---|
| `backend/migrations/versions/0007_rate_base_price.py` | CREATE | `rateplanunittype.base_amount` (numeric, ≥ 0); nothing else |
| `backend/app/models/tenant/rates/rate_plan_unit_type.py` | UPDATE | New column |
| `.ttest/contexts/schema-tenant.sql` | UPDATE | Keep the design SQL in step |
| `backend/app/tenancy/business_settings.py` | UPDATE | Calendar horizon, price bounds, limits (D5, D8, D10), deposit percent (D7) |
| `backend/app/schemas/rooms.py` | CREATE | Room type create/update/read |
| `backend/app/schemas/rate_plans.py` | CREATE | Rate plan create/update/read with prices per room type and cancellation choice |
| `backend/app/schemas/calendar.py` | CREATE | Calendar read (days per room type and rate plan) and bulk change request |
| `backend/app/services/room_types.py` | CREATE | List, create, update, switch off; keep units in line with the count |
| `backend/app/services/rate_policies.py` | CREATE | Find or create the cancellation and payment policy records a rate plan needs |
| `backend/app/services/rate_plans.py` | CREATE | List, create, update, switch off; base prices per room type |
| `backend/app/services/calendar.py` | CREATE | `read_calendar` (the shared "what is sellable" read) and `apply_calendar_change` (the one write path for prices, closed dates, minimum stay) |
| `backend/app/services/calendar_dates.py` | CREATE | Date helpers: property "today", horizon, range and weekday expansion |
| `backend/app/routers/rooms.py`, `rate_plans.py`, `calendar.py` | CREATE | `/api/room-types`, `/api/rate-plans`, `/api/calendar` |
| `backend/app/routers/settings.py`, `services/property_settings.py`, `schemas/…` | UPDATE | Deposit percent (owner edits) |
| `backend/app/main.py` | UPDATE | Register three routers (minimal edit) |
| `backend/docs/rbac-spec.yaml` | UPDATE | Menus: Calendar, Rooms & rates |
| `backend/tests/pg/test_room_types.py`, `test_rate_plans.py`, `test_calendar.py`, `test_calendar_isolation.py` | CREATE | Behaviour and tenant separation |
| `backend/tests/test_calendar_dates.py`, `tests/test_business_settings.py` | CREATE / UPDATE | Date helpers; new settings |
| `backend/tests/pg/conftest.py` | UPDATE | Helpers `make_room_type`, `make_rate_plan` |
| `frontend/lib/rooms-api.ts`, `rate-plans-api.ts`, `calendar-api.ts` | CREATE | Typed API calls |
| `frontend/lib/calendar-grid.ts` + test | CREATE | Date window, cell state, range selection, weekday helpers |
| `frontend/components/rooms/RoomTypeDialog.tsx`, `RatePlanDialog.tsx` | CREATE | Create and edit forms |
| `frontend/components/calendar/CalendarGrid.tsx`, `CalendarBulkDialog.tsx`, `CalendarCellDialog.tsx` | CREATE | The calendar and its two edit dialogs |
| `frontend/app/(authenticated)/rooms/page.tsx` | CREATE | Rooms & rates: room types and rate plans |
| `frontend/app/(authenticated)/calendar/page.tsx` | CREATE | Calendar |
| `frontend/app/(authenticated)/settings/page.tsx` | UPDATE | Deposit percent |
| `frontend/app/(authenticated)/dashboard/page.tsx` | UPDATE | "Set up your rooms" card until a room type exists |
| `frontend/lib/i18n.ts`, `frontend/middleware.ts` | UPDATE | Text in both languages; protect the new pages |
| `components-be.yaml`, `components-fe.yaml` | UPDATE | Register the new pieces |
| `.claude/prds/phase-1-channel-manager-booking-engine.prd.md` | UPDATE | Milestone status |

No new packages.

## Tasks

Each backend task is test-first: write the failing tests, then the code.

### Task 1: Settings, migration, date helpers
- **Action**: Add the settings (horizon 365, price bounds, limits, deposit 50). Migration `0007` adds `rateplanunittype.base_amount`; update the model and the design SQL. Write `calendar_dates.py`: property "today", last editable date, expanding a range with chosen weekdays, refusing past or out-of-horizon dates.
- **Mirror**: `business_settings.py`; `0006_transfer_proofs.py`.
- **Validate**: `uv run pytest tests/test_calendar_dates.py tests/test_business_settings.py -q && uv run alembic upgrade head && uv run alembic check`

### Task 2: Room types
- **Action**: `GET/POST /api/room-types`, `PATCH /api/room-types/{id}` (name, kind, units, guests, on/off). Creating or raising the count adds units; lowering it retires the highest-numbered ones; names are unique among a property's active room types; limits enforced. Tests: create, list order, rename, change count up and down, switch off, duplicate name, limits, validation, another tenant's id is 404.
- **Mirror**: `services/payment_links.py`, `routers/payment_links.py`.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_room_types.py -q`

### Task 3: Rate plans
- **Action**: `GET/POST /api/rate-plans`, `PATCH /api/rate-plans/{id}`: name, breakfast or room only, cancellation choice (free until N days / non-refundable), the room types it sells and a base price for each, on/off. `rate_policies.py` finds or creates the policy records. Tests: create with prices, add and remove a room type, change a base price, both cancellation choices, price out of bounds, unknown or inactive room type, limit, isolation.
- **Mirror**: as Task 2; decimal handling as `payment_links.money`.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_rate_plans.py -q`

### Task 4: Calendar read and write
- **Action**: `GET /api/calendar?from=&to=` returns, per active room type and date: units, available, closed, minimum stay, and the price per rate plan (override or base, with a flag saying which). `POST /api/calendar/changes` applies one change to a date range, optional weekdays and chosen room types: set price for a rate plan, clear price back to base, close, open, set or clear minimum stay. One transaction; all or nothing; upserts on the existing unique keys; a cleared value removes the row. Tests: defaults with no overrides, each change kind, weekday filter, overlapping changes (last wins), clearing, range limits, past dates refused, horizon, a 365-day change stays fast, two simultaneous changes to the same dates leave one consistent result, isolation.
- **Design note**: every calendar write goes through `apply_calendar_change`, and every read through `read_calendar`. Milestone 2 adds units sold, Milestone 4 hooks channel updates onto the write path, Milestone 7 reads prices from the same function.
- **Mirror**: locking as `property_settings.py:34`; errors as `_guarded`.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_calendar.py tests/pg/test_calendar_isolation.py -q`

### Task 5: Deposit setting
- **Action**: Add deposit percent to the settings API and page (owner edits, others read). Tests for bounds and owner-only.
- **Mirror**: bank account in `routers/settings.py`.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_bank_settings.py -q` (extended)

### Task 6: Frontend — Rooms & rates
- **Action**: API modules; `/rooms` page with two lists (room types, rate plans) and their dialogs; empty states that lead the operator from "add a room type" to "add a rate plan" to "open the calendar"; dashboard card until set up. Text in both languages.
- **Mirror**: `payment-links/page.tsx`, `CreateLinkDialog.tsx`, `money.ts`.
- **Validate**: `npx vitest run && npx tsc --noEmit && npm run lint`

### Task 7: Frontend — Calendar
- **Action**: `calendar-grid.ts` helpers with tests first. Grid: one block per room type with an availability row and a price row per rate plan; dates across (14 on a wide screen, 7 on a phone), previous / next / today; closed dates and overridden prices visibly marked, weekends and today distinguishable without relying on colour alone. Click a cell to edit one date; "Change several dates" opens the bulk dialog (range, weekdays, room types, what to change). Keyboard reachable; no sideways page scroll on a phone.
- **Mirror**: `PaymentLinkTable.tsx` scroll container; dialogs as above.
- **Validate**: `npx vitest run && npx tsc --noEmit && npm run lint`

### Task 8: Run, browser test, review
- **Action**: Full backend suite with coverage, `alembic check`, migration up/down/up on an empty database, design SQL applies. `bash scripts/devtest.sh start`; with Playwright on a fresh workspace: add two room types and two rate plans, see base prices on the calendar, raise weekend prices for a month, close a week, set a minimum stay, clear an override, edit one cell, lower a unit count, switch a rate plan off; both languages; phone width; console and `devtest.sh errors` clean; stop. Code review and security review; fix critical and high findings. Update the registers; mark the milestone complete.
- **Validate**: commands below.

## Validation

```bash
cd backend
uv run ruff check app tests
REQUIRE_PG_TESTS=1 uv run pytest -q --cov=app --cov-report=term
uv run alembic check
cd ../frontend
npx vitest run && npx tsc --noEmit && npm run lint
cd .. && bash scripts/devtest.sh start   # Playwright walk-through
bash scripts/devtest.sh errors && bash scripts/devtest.sh stop
```

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| The existing tables model far more than this milestone needs (derived rates, per-person pricing, hourly units) and tempt scope creep | High | Expose only the fields in the Decisions table; leave the rest at their defaults |
| The calendar read is slow for 30 room types × 10 rate plans × many dates | Medium | Read sparse override rows for the window in a few queries and merge with base prices in memory; cap the window per request; test with a full property |
| A bulk change writes thousands of rows | Medium | One upsert statement per kind; cap at 365 days; timing test |
| Later milestones need a different shape and this is rebuilt | Medium | One read function and one write path, named in the design note, are the only things later milestones depend on |
| "Today" and the horizon are wrong around midnight for properties away from UTC | Medium | All date maths in the property's timezone; tests at the boundary |
| Lowering the unit count will conflict with bookings once they exist | Certain (Milestone 2) | Out of scope now; noted for Milestone 2 to refuse when bookings need the unit |
| A calendar grid is hard to use on a phone | Medium | 7-day window, large cells, bulk dialog as the main way to edit; checked at 390px in the walk-through |
| Tenant data leaks through room type or rate plan ids in requests | Low | Every id looked up within the caller's property; isolation tests for each route |

## Acceptance

- [ ] An operator can create room types and rate plans and see base prices on the calendar
- [ ] Price, closed dates and minimum stay can be changed for one date or a range with chosen weekdays, and cleared again
- [ ] Past dates and dates beyond the horizon cannot be changed
- [ ] One read function returns units, availability, closed state, minimum stay and price per rate plan for any date window
- [ ] Limits and defaults are configurable values
- [ ] Works in Bahasa Indonesia and English, and at phone width
- [ ] All tasks complete, validation passes, coverage at least 80%
- [ ] Patterns mirrored, not reinvented
