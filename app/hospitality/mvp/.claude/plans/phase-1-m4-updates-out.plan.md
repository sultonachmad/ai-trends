# Plan: Updates out to channels (Phase 1, Milestone 4)

**Source PRD**: `.claude/prds/phase-1-channel-manager-booking-engine.prd.md`
**Selected Milestone**: 4 — Updates out
**Complexity**: Large

## Summary

A change anywhere that affects what can be sold — a calendar edit, a booking made,
changed or cancelled, a room count, a base price, a connection going live or being
paused — is queued and pushed to every connected channel within seconds, with retries
until the channel acknowledges. Staff see each connection's health (last successful
update, what is still waiting, retries, "at risk"), what the channel currently holds
next to our truth, and the full message log; a "Sync now" button re-sends any date
range on demand.

## What already exists

| Need | Existing |
|---|---|
| The moments to hook | `services/channel_hooks.py` (`on_go_live` / `on_pause` / `on_resume` — empty, built for this); `calendar.apply_calendar_change` returns `AppliedChange(dates, room_type_ids)` "later milestones send exactly this" |
| The message log | `channelmessage` table — direction, `message_type` incl. `ari_delta`/`ari_full_sync`, status `queued/sent/acked/failed/dead`, `attempts`, `next_attempt_at`, `date_from/to`, request/response payloads, `error`, `sent_at` |
| Connection health fields | `channelconnection.last_ari_success_at`, `error_message`, `settings` |
| The truth to send | `services/calendar.py` (`stay_nights`, `read_calendar` internals: price per mapped rate, availability = units − sold, closed, minimum stay); `inventory.sold_by_night` |
| Provider interface + simulator | `app/channels/provider.py` (`fetch_property` so far), `app/channels/simulator.py` with its listing store |
| Background work in-process | `services/proof_retention.run_startup_purge` (lifespan task pattern), `app/jobs/purge_proofs.py` (scheduler-job pattern) |
| Permissions | every feature route already checks `channels:view` / `channels:edit` (new endpoints join them) |

One migration: the pending-update queue table (the log table above already exists).
No new packages.

## Decisions (recommendation first — reply "yes" to accept all)

| # | Question | Recommendation |
|---|---|---|
| D1 | How do updates reach channels? | An in-process background task started with the app, polling a queue table every 5 seconds. Nothing to install; one process owns pushing (documented; leader election when we run more than one). Never pushed inside a staff request — the request only queues. |
| D2 | The queue | A small table `channelariupdate`: one row per (connection, room type, date) that needs (re)sending, inserted with `ON CONFLICT DO NOTHING` — natural de-duplication, and the delta is exactly the rows present. |
| D3 | What triggers a queue entry | Calendar changes; booking created/changed/cancelled (availability moved); room-type unit count changes; base-price changes; matching changes (newly mapped pairs); go-live and resume (whole horizon); pause (whole horizon, as "closed everywhere"). |
| D4 | Holding back units | One property setting, `channel_hold_back_units` (default 0, 0–20), owner-edited in Settings: every room type's availability sent to channels is reduced by it (never below zero). Direct and walk-in sale keeps the full count. |
| D5 | Direct-only rate plans | Nothing new: a rate plan not matched to a channel is simply not sold there — the matching screen from Milestone 3 is the control. The connection page says so where it lists what is sold. |
| D6 | Price adjustment | The connection's price adjustment (−50…+100%, set in Milestone 3) is applied to every price sent; whole rupiah, rounded half up. The log records the price before and after. |
| D7 | Retries | Backoff 5 s, 30 s, 2 m, 10 m, then every 30 m; the attempt count and next attempt time live on the log row. After 3 failed attempts the connection is flagged "update failing repeatedly". Retries continue forever — the queue never silently drops a change. |
| D8 | "At risk" (BR-CM-05) | No successful acknowledgment for `channel_stale_after_hours` (default 48) **or** pending updates older than 15 minutes. Shown on the connection, its page and the dashboard card. |
| D9 | Full re-sync | A "Sync now" action per connection (whole horizon or a chosen date range) processes immediately; `python -m app.jobs.sync_channels` does the same for every connection, to run daily from a scheduler. Both record `ari_full_sync` messages, which also refresh the staleness clock. |
| D10 | What the channel currently holds (FR-CM-025) | The provider gains `fetch_current_ari`; the simulated agency stores every acknowledged day (availability, price per rate, closed, minimum stay) and answers from that store. The connection page compares it with our truth for the next 60 days and lists the dates that differ ("drift"). |
| D11 | Simulator test knobs | A dev-only route marks a listing to fail its next N pushes (`ChannelUnavailableError`), so retry, backoff, "failing repeatedly" and "at risk" can be exercised; drift is tested by tampering with the agency's stored state. |
| D12 | Pause semantics | Pausing pushes availability 0 (closed) for the whole horizon — the channel stops selling at once; resuming re-sends the truth. |

## Patterns to Mirror

| Category | Source | Pattern |
|---|---|---|
| Provider interface | `backend/app/channels/provider.py:44` | Protocol + registry + frozen dataclasses + named errors; extend, don't fork |
| Simulator | `backend/app/channels/simulator.py`, `routers/channel_simulator.py` | Behaviour from the listing store; dev-only knobs behind `require_channel_simulator_enabled` |
| Queue + worker | `services/inventory.py` (upsert in date order under the caller's transaction), `services/proof_retention.py` (lifespan task), `app/jobs/purge_proofs.py` | Queue rows written in the same transaction as the change; a loop owns the sending |
| Record first, call out | `services/checkout.py` (`start_payment`) | Our rows commit; the external call happens with no lock held; outcome stored after |
| Hooks | `services/channel_hooks.py` | The three moments already exist — this milestone is their body |
| Errors | `routers/channels.py` (`_MESSAGES`, `_guarded`) | Named service exceptions → HTTP answers |
| Settings | `tenancy/business_settings.py` (`PropertySettings`) | New numbers as validated fields with defaults |
| Tests | `tests/pg/test_channel_connections.py`, `test_booking_changes.py`, `test_feature_access.py` | Integration through the HTTP client; services called directly where the worker would run; simulator knobs for failure paths; permission checks on new routes |
| Frontend | `components/channels/*`, `lib/channel-format.ts` + test | Status badges, pure helpers tested first, text via `lib/i18n.ts` in `id` and `en` |

## Files to Change

| File | Action | Why |
|---|---|---|
| `backend/migrations/versions/0010_channel_ari_queue.py` | CREATE | `channelariupdate` (tenant, property, connection, room type, date; unique on the four) with tenant isolation, FORCE RLS, grants |
| `backend/app/models/tenant/distribution/channel_ari_update.py`, `.ttest/contexts/schema-tenant.sql` | CREATE / UPDATE | Model + DTOs for the queue table; design SQL in step |
| `backend/app/tenancy/business_settings.py` | UPDATE | `channel_hold_back_units`, `channel_stale_after_hours`, `channel_pending_stale_minutes`, `channel_push_interval_seconds`, backoff schedule |
| `backend/app/channels/provider.py` | UPDATE | `AriDay` (date, availability, closed, min stay, price per mapped rate), `push_ari(call, property_id, rooms) -> acknowledged`, `fetch_current_ari(call, property_id, room_ids, dates)` |
| `backend/app/channels/simulator.py` | UPDATE | Acknowledge and store ARI per listing; answer `fetch_current_ari`; fail-next-N knob |
| `backend/app/routers/channel_simulator.py` | UPDATE | Dev-only: fail-next-N route |
| `backend/app/services/channel_truth.py` | CREATE | What we sell on a connection per date: availability (units − sold − hold-back, min 0), closed, minimum stay, price per mapped rate with the connection's adjustment |
| `backend/app/services/channel_queue.py` | CREATE | `enqueue(session, context, property_id, room_type_ids, dates)` — the only writer, `ON CONFLICT DO NOTHING`; plus reading due work per connection |
| `backend/app/services/channel_push.py` | CREATE | The sender: batch due rows per connection → build truth → `push_ari` (no lock held) → `channelmessage` rows (attempts, backoff, payloads) → on ack delete queue rows, set `last_ari_success_at`; health flags (failing repeatedly, pending age, stale) |
| `backend/app/services/channel_hooks.py` | UPDATE | The bodies: go-live/resume enqueue the horizon; pause enqueues it as "close all" |
| `backend/app/services/{calendar,bookings,room_types,rate_plans,channel_mappings}.py` | UPDATE | Call `channel_queue.enqueue` for what each changed |
| `backend/app/services/workspace.py`, `schemas/workspace.py` | UPDATE | `channels_needing_attention` count for the dashboard |
| `backend/app/routers/channels.py` | UPDATE | `POST /api/channel-connections/{id}/sync` (date range optional; `channels:edit`), status/log/current-state folded into the connection detail (`channels:view`); log endpoint with paging if the detail grows |
| `backend/app/main.py` | UPDATE | Lifespan starts the push loop (unless disabled); guard for tests |
| `backend/app/jobs/sync_channels.py` | CREATE | Daily full re-sync, run from a scheduler |
| `backend/tests/pg/test_channel_queue.py`, `test_channel_push.py`, `test_channel_health.py`, `test_channels_isolation.py` | CREATE / UPDATE | Triggers, delta/dedup, hold-back, adjustment, retry/backoff, ack/staleness, pause/close-all, sync-now, drift, permissions, isolation |
| `backend/tests/pg/conftest.py` | UPDATE | Helper `push_now(pg_session_factory, ...)` (run the sender once, like the worker would) |
| `frontend/lib/channels-api.ts`, `channel-format.ts` + test | UPDATE | sync action; health/status labels and badges; drift formatting |
| `frontend/components/channels/ConnectionStatus.tsx`, `MessageLog.tsx`, `ChannelStateDiff.tsx`, `SyncDialog.tsx` | CREATE | Status (last success, pending, at risk, failing), the log with attempt counts and errors, the drift list, the sync-now dialog |
| `frontend/app/(authenticated)/channels/[id]/page.tsx`, `channels/page.tsx`, `components/channels/ChannelsCard.tsx` | UPDATE | New sections; needs-attention badge on the overview and card |
| `frontend/components/settings/ChannelHoldBackSection.tsx`, settings page | UPDATE/CREATE | Hold-back units, owner-edited |
| `frontend/lib/i18n.ts` | UPDATE | New strings in `id` and `en` |
| `components-be.yaml`, `components-fe.yaml`, the PRD | UPDATE | Registers; milestone status |

## Tasks

Each backend task is test-first.

### Task 1: Migration, settings, queue
- **Action**: Migration `0010` and the model for `channelariupdate`; new `PropertySettings` fields; `channel_queue.enqueue` (idempotent, in the caller's transaction, date-ordered) and the due-work reader. Tests: enqueue dedups; reading gives dates grouped by connection; isolation.
- **Mirror**: `migrations/versions/0009_channel_connections.py` (tenant table + policy + grants); `services/inventory.py`.
- **Validate**: `uv run alembic upgrade head && uv run alembic check && REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_channel_queue.py -q`

### Task 2: Provider interface and simulator
- **Action**: `AriDay`, `push_ari` (returns per-room acknowledgement), `fetch_current_ari`; the simulator stores acknowledged days per listing (availability, price per external rate id, closed, min stay), honours the fail-next-N counter, answers current state. Unit tests for the store and knobs.
- **Mirror**: `channels/provider.py`, `channels/simulator.py`.
- **Validate**: `uv run pytest tests/test_channel_simulator.py -q`

### Task 3: Triggers
- **Action**: Wire `enqueue` into calendar changes, booking create/change/cancel (old **and** new nights), unit-count changes, base-price changes, matching changes; fill the three hooks (pause = "close all" enqueue + flag, go-live/resume = horizon). Tests: each cause queues exactly its dates and rooms; a change while nothing is connected queues nothing; pause/resume/go-live ranges.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_channel_queue.py tests/pg/test_channel_connections.py -q`

### Task 4: The sender
- **Action**: `channel_push.process_due(session_factory)` — per live connection: batch due rows, build truth via `channel_truth` (hold-back, adjustment applied), commit, call `push_ari` with no lock, write `channelmessage` (attempts, backoff `next_attempt_at`, request/response digests), on ack delete queue rows and stamp `last_ari_success_at`; health flags. The lifespan loop calls it every `channel_push_interval_seconds`; `POST …/sync` runs it for one connection over a range now; the daily job for all. Tests: happy path; delta only; adjustment and hold-back in the payload; retry/backoff via fail-next-N; repeated-failure and at-risk flags; ack clears everything; pause pushes closed; drift detection via tampering; permissions on the new route.
- **Mirror**: `services/checkout.py` record-then-call; `proof_retention.py` loop.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_channel_push.py tests/pg/test_channel_health.py -q`

### Task 5: Frontend
- **Action**: Helpers + tests first (status labels, badge classes, drift rows, attempt text). Connection page: status block (last success, waiting count, at-risk/failing warnings, Sync now with optional range), message log (newest first, status badge, attempts, error), "what the channel holds" drift list. Overview + dashboard card: needs-attention badge. Settings: hold-back section (owner). Both languages.
- **Validate**: `npx vitest run && npx tsc --noEmit && npm run lint`

### Task 6: Run, browser test, review
- **Action**: Full backend suite + `alembic check`; up/down/up on an empty database; design SQL applies. `devtest.sh start`: connect the simulated agency, go live, then change a price / close dates / make and cancel a booking and watch each update land on the agency (state view) within seconds; hold back a unit; fail the next pushes and watch retries, the failing badge and at-risk; Sync now over a range; pause pushes closed everywhere; tamper the agency state and see the drift list; check permissions (a view-only member sees status but no Sync); both languages; phone width; console and `devtest.sh errors` clean; stop. Code + security review; fix critical and high findings. Registers; milestone complete.

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
| Pushing inside a request makes staff actions slow or fail with the channel | High | Requests only queue; the worker sends, with no lock held (pattern already proven by the gateway) |
| Two app processes both push (future deployment) | Medium (later) | Documented single-writer assumption now; advisory lock per connection in the sender is a one-line addition when needed |
| Queue rows orphaned by a bug (never sent, never cleared) | Medium | Pending-age is surfaced as "at risk"; Sync now always rebuilds truth for a range; tests recount queue rows after every scenario |
| Booking changes enqueue a huge range (year-long stays) | Low | Bounded by the booking's own nights (max 366) and per-push cell cap; batched per connection |
| Drift comparison cost | Low | Capped to the next 60 days on demand, not polled |
| The worker makes pg tests flaky (lifespan not running in tests anyway) | Low | Tests drive `process_due` directly; the loop is a thin caller |
| The simulator accepts everything, hiding real push failures | Medium | Fail-next-N knob exercised in tests; payloads logged and asserted |
| Scope creep into receiving bookings (Milestone 5) | Medium | `push_ari` and `fetch_current_ari` only; nothing inbound in this milestone |

## Acceptance

- [ ] A calendar change, a booking change and a price change each reach the connected channel within 30 seconds (worker poll 5 s)
- [ ] Only what changed is sent; repeated changes collapse
- [ ] Failed pushes retry with backoff, are logged with attempts and errors, and surface "failing" and "at risk" states
- [ ] Sync now re-sends a chosen range immediately; the daily job covers every connection
- [ ] Pause closes the channel everywhere; resume re-sends; go-live starts with a full sync
- [ ] Hold-back units and the connection's price adjustment are applied to what is sent
- [ ] The connection page shows last success, waiting work, the message log, and drift against our truth
- [ ] New routes respect `channels:view` / `channels:edit`; both languages; phone width
- [ ] All tasks complete, validation passes, coverage at least 80%
- [ ] Patterns mirrored, not reinvented
