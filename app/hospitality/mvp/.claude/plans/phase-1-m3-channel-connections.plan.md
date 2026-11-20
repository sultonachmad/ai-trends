# Plan: Channel connections (Phase 1, Milestone 3)

**Source PRD**: `.claude/prds/phase-1-channel-manager-booking-engine.prd.md`
**Selected Milestone**: 3 — Channel connections
**Complexity**: Large

## Summary

An operator sees which channels exist, connects the simulated online travel agency through
guided steps (property ID → test → match rooms and rates → settings → go live), and can pause,
resume or disconnect it. The Free plan stops a second connection with a clear message. This
milestone sets up the connection and the matching only; sending updates (Milestone 4) and
receiving bookings (Milestone 5) plug into the provider interface and the "go live", "pause" and
"resume" moments defined here.

## What already exists

| Need | Existing table / code |
|---|---|
| Catalogue of channels (Traveloka, Tiket, Agoda, Booking.com, Airbnb, Google, iCal …) | `channelcatalog` (control plane), seeded in migration `0002` with features and certification status |
| A property's channel rows | `channel` — already used for booking sources (`services/booking_sources.py`) |
| A connection | `channelconnection` — `models/tenant/distribution/channel_connection.py` (channel's property ID, status draft/testing/live/paused/error/disconnected, price adjustment %, who collects, settings, last successful update) |
| Room and rate matching | `channelmapping` — `distribution/channel_mapping.py` (our room type + rate plan ↔ channel room + rate, price adjustment, cap) |
| Change history | `tenantauditentry` — `plumbing/tenant_audit_entry.py` (unused so far) |
| Plan limits | `tenantentitlement.limits` read through `PlanLimits` (`tenancy/business_settings.py`); the `channel_manager` module exists but is not in the Free plan |
| Provider + simulator pattern | `app/payments/gateway.py` + `simulator.py`, `app/messaging/provider.py` + `simulator.py` |

## Decisions (recommendation first — reply "yes" to accept all)

| # | Question | Recommendation |
|---|---|---|
| D1 | Which channels can be connected now? | One: "Simulated agency (test)", shown only while the simulator is switched on. The real agencies are listed as "coming soon" with what each will support. iCal appears as "calendar link — coming in a later step" (Milestone 6). |
| D2 | Where do the simulated agency's rooms come from? | A small test panel, "Create a test listing", makes a listing on the simulated agency: its own property ID and rooms and rates with agency-style names (copied from the property's rooms, plus one extra room that has no match). The operator then connects to that ID, as they would paste a real hotel ID. |
| D3 | Matching rule | Each of our room type + rate plan pairs is matched to at most one channel room + rate, and each channel room + rate is used once. Pairs left unmatched are simply not sold on that channel. One-to-many and per-occupancy matching wait for a real channel that needs them. |
| D4 | What must be true to go live? | The connection test passed and at least one pair is matched. Warnings (not blockers): our pairs left unmatched, channel rooms left unmatched, a channel room that fits fewer guests than ours. |
| D5 | Settings per connection | Commission % (0–50), price adjustment % (−50 to +100, applied to prices sent to the channel from Milestone 4), who collects payment (property or channel). All have defaults from the catalogue and can be changed later. |
| D6 | Pause, resume, disconnect | Pause = closed for sale on the channel, matching kept. Resume = live again (with a full refresh from Milestone 4). Disconnect = ended; history kept; the slot is free again. A draft that was never finished can be discarded. |
| D7 | What counts toward the plan limit? | Every connection that is not disconnected (draft, testing, live, paused, error). Free plan: 1, as a configurable plan value; warning and "limit reached" shown as for payment links. Calendar links and the booking page will not count. |
| D8 | Several listings on one channel | Not now: one connection per channel per property (FR-CM-004 is a "should"). |
| D9 | Change history | Every create, test, match change, settings change, go-live, pause, resume and disconnect is recorded with who and when, and shown on the connection page. |
| D10 | Who may connect and change | Any member of the property, as elsewhere today; owner-only waits for staff roles. |

## Patterns to Mirror

| Category | Source | Pattern |
|---|---|---|
| Provider interface | `backend/app/payments/gateway.py:44`, `app/messaging/provider.py` | A `Protocol`, a registry keyed by name, named errors; services depend on the interface only |
| Simulator | `backend/app/payments/simulator.py`, `backend/app/routers/simulator.py:40` | Registered under the name `simulator`; dev-only routes behind a settings flag that answer 404 when off |
| Record first, then call out | `backend/app/services/checkout.py` (`start_payment`) | Save our row and commit, call the provider with no lock held, then store the outcome |
| Naming | `backend/app/services/rate_plans.py`, `routers/rate_plans.py` | One service module per topic; router per resource under `/api/...` |
| Errors | `backend/app/routers/bookings.py` (`_MESSAGES`, `_guarded`) | Named service exceptions mapped to HTTP answers; 404 for another tenant's id |
| Limits | `backend/app/services/link_quota.py` | One function feeds both the screen and the check made under a lock |
| Locking | `backend/app/services/rate_plans.py` (`_lock_property`) | Property row lock around counted or unique changes |
| Validation | `backend/app/schemas/rooms.py` (`RoomName`, `UNSAFE_IN_NAMES`) | `extra="forbid"`, safe single-line text, bounded numbers |
| Migration | `backend/migrations/versions/0004_app_role_and_free_plan.py`, `0003` (`RLS_POLICY`) | One statement per `op.execute`; new tenant table gets the isolation policy, FORCE row-level security and app-role grants; design SQL kept in step |
| Tests | `backend/tests/pg/test_rate_plans.py`, `test_link_quota.py`, `test_calendar_isolation.py` | PostgreSQL tests through the HTTP client; limit and simultaneous-request tests; isolation with `other_client` |
| Pages | `frontend/app/(authenticated)/rooms/page.tsx`, `components/rooms/RatePlanDialog.tsx`, `components/payments/LinkQuotaNotice.tsx` | List page + dialogs; usage notice; text via `lib/i18n.ts` in `id` and `en` |

## Files to Change

| File | Action | Why |
|---|---|---|
| `backend/migrations/versions/0009_channel_connections.py` | CREATE | Catalogue entry for the simulated agency; `channel_manager` on the Free plan with `connected_channels: 1` and the same for existing tenants; table for the simulator's test listings (with tenant isolation and grants) |
| `backend/app/models/tenant/distribution/channel_simulator_listing.py`, `.ttest/contexts/schema-tenant.sql`, `schema-control-plane.sql` | CREATE / UPDATE | The simulator's own listing data; design SQL in step |
| `backend/app/tenancy/business_settings.py` | UPDATE | `PlanLimits.connected_channels` (default 1; `None` = unlimited) |
| `backend/app/channels/provider.py` | CREATE | `ChannelProvider` protocol: `test_connection`, `list_products`; registry; errors. Milestones 4 and 5 add sending updates and receiving bookings |
| `backend/app/channels/simulator.py` | CREATE | The simulated agency behind that interface |
| `backend/app/services/channel_catalog.py` | CREATE | What can be connected and what is coming, for this property |
| `backend/app/services/channel_quota.py` | CREATE | Connections used against the plan limit; the check made under the lock |
| `backend/app/services/channel_connections.py` | CREATE | Start, test, settings, go live, pause, resume, disconnect, read, list |
| `backend/app/services/channel_mappings.py` | CREATE | Read the channel's rooms and rates, save the matching, health warnings |
| `backend/app/services/tenant_audit.py` | CREATE | Record a change with who and when (hash-chained, as the table requires) |
| `backend/app/schemas/channels.py` | CREATE | Request and read shapes |
| `backend/app/routers/channels.py` | CREATE | `/api/channels` (catalogue + usage), `/api/channel-connections…` |
| `backend/app/routers/simulator.py` | UPDATE | Dev-only: create and read a test listing |
| `backend/app/services/workspace.py`, `schemas/workspace.py` | UPDATE | Channel usage in the workspace summary |
| `backend/app/main.py`, `backend/docs/rbac-spec.yaml` | UPDATE | Register the router; menu entry "Channels" |
| `backend/tests/pg/test_channel_catalog.py`, `test_channel_connections.py`, `test_channel_mappings.py`, `test_channel_quota.py`, `test_channels_isolation.py`, `tests/test_channel_simulator.py`, `tests/test_tenant_audit.py` | CREATE | Behaviour, limit, simultaneous requests, tenant separation |
| `backend/tests/pg/conftest.py` | UPDATE | Helpers `make_test_listing`, `connect_channel` |
| `frontend/lib/channels-api.ts`, `channel-format.ts` + test, `channel-mapping.ts` + test | CREATE | Calls; status labels and badges; matching helpers (what is unmatched, what is used twice) |
| `frontend/components/channels/ChannelCatalog.tsx`, `ConnectionList.tsx`, `ConnectWizard.tsx`, `MappingEditor.tsx`, `ConnectionSettingsForm.tsx`, `ChannelQuotaNotice.tsx`, `TestListingPanel.tsx` | CREATE | The screens' parts |
| `frontend/app/(authenticated)/channels/page.tsx`, `channels/[id]/page.tsx` | CREATE | Channels overview; one connection (status, matching, settings, history, pause / resume / disconnect) |
| `frontend/app/(authenticated)/dashboard/page.tsx` | UPDATE | Channels card |
| `frontend/lib/i18n.ts`, `frontend/lib/workspace-api.ts`, `frontend/middleware.ts` | UPDATE | Text in both languages; usage type; protect the new pages |
| `components-be.yaml`, `components-fe.yaml`, the PRD | UPDATE | Registers; milestone status |

No new packages.

## Tasks

Each backend task is test-first.

### Task 1: Migration, plan limit, change history
- **Action**: Migration `0009` as listed; model for the simulator listing; `PlanLimits.connected_channels`; `tenant_audit.record(...)` with its hash chain and a unit test that a chain verifies and a tampered entry does not.
- **Mirror**: `0004_app_role_and_free_plan.py`; `link_quota.plan_limits`.
- **Validate**: `uv run alembic upgrade head && uv run alembic check && uv run pytest tests/test_tenant_audit.py tests/test_business_settings.py -q`, plus the up/down/up run on an empty database

### Task 2: Provider interface and simulated agency
- **Action**: `ChannelProvider` with `test_connection(property_id)` and `list_products(property_id)` (rooms with their rates and guest capacity), named errors (`ChannelUnavailableError`, `UnknownChannelPropertyError`). The simulator answers from its test listings. Dev-only route creates a listing from the property's room types with agency-style names plus one unmatched room.
- **Mirror**: `payments/gateway.py`, `payments/simulator.py`, `routers/simulator.py`.
- **Validate**: `uv run pytest tests/test_channel_simulator.py -q`

### Task 3: Catalogue and plan limit
- **Action**: `GET /api/channels` returns connectable channels, coming-soon channels with features, and usage against the limit (used, limit, warning, limit reached). `channel_quota.reserve_connection_slot` checks under the property lock. Tests: Free plan shows 1; simulator hidden when its flag is off; limit as a plan value; unlimited plan.
- **Mirror**: `link_quota.py`, `test_link_quota.py`.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_channel_catalog.py tests/pg/test_channel_quota.py -q`

### Task 4: Connections
- **Action**: `POST /api/channel-connections` (channel + its property ID → draft, slot reserved), `POST …/{id}/test` (record first, call the provider without a lock, store testing or the error in plain words), `PATCH …/{id}` (settings), `POST …/{id}/go-live`, `/pause`, `/resume`, `/disconnect`, `GET` list and detail with history. Allowed moves between states enforced in one place. Tests: the whole path; each refused move; test against an unknown property ID; provider down; second connection refused at the limit; two simultaneous connects give one; disconnect frees the slot; one connection per channel; isolation.
- **Design note**: go-live, pause and resume each call one hook function that does nothing yet. Milestone 4 fills them with "full refresh" and "close all".
- **Mirror**: `checkout.start_payment`; `_guarded`.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_channel_connections.py tests/pg/test_channels_isolation.py -q`

### Task 5: Matching
- **Action**: `GET …/{id}/products` (the channel's rooms and rates, fetched live), `PUT …/{id}/mappings` (replace the whole matching, all or nothing), mapping health in the connection detail. Tests: save, replace, clear; a pair or a channel room used twice refused; rooms, plans or channel ids that do not exist refused; a plan that does not sell the room refused; warnings for unmatched pairs, unmatched channel rooms and smaller capacity; go-live refused with nothing matched; a room type switched off later shows as a warning, not an error.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_channel_mappings.py -q`

### Task 6: Frontend — overview and connect steps
- **Action**: Helpers with tests first. `/channels`: usage notice, my connections with status, catalogue (connect / coming soon). Connect steps in one dialog: property ID → test result → matching → settings → go live, resumable from a draft. Test listing panel when the simulator is on.
- **Mirror**: `rooms/page.tsx`, `RatePlanDialog.tsx`, `LinkQuotaNotice.tsx`.
- **Validate**: `npx vitest run && npx tsc --noEmit && npm run lint`

### Task 7: Frontend — one connection
- **Action**: `/channels/[id]`: status with last test, matching editor with warnings, settings form, pause / resume / disconnect with confirmation, history list. Dashboard card.
- **Validate**: as Task 6

### Task 8: Run, browser test, review
- **Action**: Full backend suite with coverage and `alembic check`. `bash scripts/devtest.sh start`; with Playwright on a fresh workspace with rooms and rate plans: create a test listing, connect, see a failed test with a wrong ID then a passed one, match rooms, see the warnings, set commission and price adjustment, go live, pause, resume, change a match, try a second connection and see the limit message, disconnect and connect again, read the history; both languages; phone width; console and `devtest.sh errors` clean; stop. Code review and security review; fix critical and high findings. Update the registers; mark the milestone complete.

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
| The provider interface is shaped by the simulator and does not fit a real agency | High | Model it on Booking.com's published connection flow (property ID, room and rate IDs, test, activate); keep it to two calls now; revisit when the first certified connection starts |
| The simulator's listing feels unlike a real extranet, so matching is never really tested | Medium | Agency-style names that differ from ours, an extra unmatched room, a smaller capacity on one room |
| A new table without tenant isolation leaks test listings | Low | Migration applies the same policy, FORCE and grants as every tenant table; an isolation test reads it as the other tenant |
| Existing tenants get no channel entitlement and see "not in your plan" | Medium | The migration adds it for every tenant on the Free plan; a test starts from a tenant created before the change |
| Two staff connect at the same moment and pass the limit | Medium | Slot reserved under the property lock; simultaneous-request test |
| Hash chain of the change history breaks under concurrent writes | Medium | Entries written under the property lock in the same transaction as the change; chain verified in tests |
| Go-live, pause and resume do nothing visible until Milestone 4 | Certain | Say so on the screen ("updates start in the next step") in test mode only; hooks in place |
| Scope creep into sending updates or receiving bookings | Medium | The interface has two calls; anything else is rejected in review |

## Acceptance

- [ ] An operator can connect the simulated agency through the guided steps and go live
- [ ] Rooms and rates can be matched, changed and cleared, with warnings for what is left over
- [ ] A connection can be paused, resumed and disconnected; a disconnected one frees the slot
- [ ] The Free plan refuses a second connection on the server, including simultaneous attempts, with a clear message
- [ ] Every change to a connection or its matching is recorded with who and when and can be read
- [ ] Real agencies are shown as coming soon; nothing pretends to be connected to them
- [ ] Works in Bahasa Indonesia and English, and at phone width
- [ ] All tasks complete, validation passes, coverage at least 80%
- [ ] Patterns mirrored, not reinvented
