# Plan: Calendar links (Phase 1, Milestone 6)

**Source PRD**: `.claude/prds/phase-1-channel-manager-booking-engine.prd.md`
**Selected Milestone**: 6 — Calendar links
**Complexity**: Large

## Summary

An operator links a room type to Airbnb or a similar site in two directions: we give
them a private `.ics` link to paste there, and they paste that site's `.ics` link here.
Dates booked on the site take a unit off sale in our calendar, on every channel and in
staff booking; dates we have no units left for show as blocked on the site.
Availability only: no prices or guest details leave the product.

## What already exists, and the gaps

| Need | Today | Gap this milestone closes |
|---|---|---|
| Feed table | `icalfeed` (`direction`, `url`, `export_token_hash`, `last_synced_at`, `last_error`) | `unit_id` is required, but rooms are sold by room type and units are not assigned. Needs `unit_type_id` and a way to pair a site's two directions |
| Blocked units | `inventoryday.blocked` column; the computed `available` subtracts it | **Nothing reads or writes it.** Calendar, booking checks, channel pushes and the overbooking flags all compute `units - sold` through `sold_by_night` (six callers) |
| Imported events | none | New table, so a re-import can release only what the site removed |
| Fetching a URL | `httpx` is installed | No protection against a pasted URL reaching internal addresses |
| Parsing `.ics` | none | Needs a parser (decision D2) |
| Public token route | `app/payments/tokens.py`, `routers/checkout.py` | Reuse as is |
| Background loop | `run_channel_pusher`, `run_booking_poller` | Same shape |
| Updates to channels | `channel_queue.enqueue` | Call it when blocks change |
| Plan limit | `channel_quota` counts `channelconnection` rows | Calendar links create no connection row, so they are not counted, as the PRD requires |

## Decisions (recommendation first; reply "yes" to accept all)

| # | Question | Recommendation |
|---|---|---|
| D1 | What is one calendar link attached to? | One room type and one site. Each date the site marks as busy takes **one unit** of that room type. For a room type with 3 units, link each Airbnb listing separately |
| D2 | How do we parse `.ics`? | **Add the `icalendar` package** (needs your approval under the package policy; no keys or env vars). The input is untrusted and has real format variations (folded lines, time zones, all-day vs timed events). The alternative is a small hand-written parser limited to the fields we need |
| D3 | How often do we read their calendar? | Every 30 minutes (configurable, 15 to 360), plus a "Sync now" button. The product says plainly that sites read calendars only every few hours, so double bookings remain possible, and suggests holding back a unit |
| D4 | What does our link show as busy? | A date is busy when that room type has no units left for this site, or is closed. Dates blocked only by this same site's import are not sent back to it, so a block cannot echo and become permanent |
| D5 | Site blocks a date we already sold | Keep both. The block is recorded, the date shows as oversold and staff see a "calendar conflict" in the bookings attention card. No booking is cancelled automatically |
| D6 | A fetch fails or returns garbage | **Keep the existing blocks** and show the error and last successful sync. Dates are released only by a valid calendar that no longer lists them. A link failing for 24 hours is marked "at risk" |
| D7 | Private link handling | Only a hash is stored, as with payment links. The link is shown once when created; "Replace link" issues a new one and the old one stops working |
| D8 | What the `.ics` contains | Dates and a generic "Not available" title. No guest, price, booking number or property details |
| D9 | Where it lives in the app | A "Calendar links" section on the existing Channels page, under `channels:view` / `channels:edit`. No new menu entry. The public `.ics` route needs only its token |

## Patterns to Mirror

| Category | Source | Pattern |
|---|---|---|
| Public token | `backend/app/payments/tokens.py:15-26`, `backend/app/routers/checkout.py:1-7` | Random token, stored fingerprint, same 404 for every bad token |
| Background loop | `backend/app/services/channel_booking_pull.py` | Tenants from the control plane, per-tenant `bind_tenant`, one failure never stops the others, PostgreSQL only |
| Record, then call out | `backend/app/services/channel_push.py` (`_push_chunk`) | No transaction or lock held during the network call |
| Inventory writes | `backend/app/services/inventory.py:44-100` | `inventory.py` stays the only writer of `inventoryday` counts |
| Queue to channels | `backend/app/services/channel_queue.py` | Enqueue inside the transaction that changed availability |
| Errors | `backend/app/routers/channels.py:94` (`_guarded`) | Named service exceptions mapped to HTTP answers |
| Settings | `backend/app/tenancy/business_settings.py:144` | Validated fields with defaults |
| Tests | `backend/tests/pg/test_channel_push.py`, `test_feature_access.py` | HTTP client, services driven directly in place of the loop, permission and isolation cases |
| Frontend | `frontend/components/channels/*`, `lib/channel-format.ts` | Pure helpers tested first, all text in `lib/i18n.ts` |

## Files to Change

| File | Action | Why |
|---|---|---|
| `backend/migrations/versions/0012_calendar_links.py` | CREATE | `icalfeed`: add `unit_type_id`, `link_id`, `label`, make `unit_id` nullable, unique token index. New `icalblock` table with tenant isolation |
| `backend/app/models/tenant/distribution/ical_feed.py`, `ical_block.py`, `.ttest/contexts/schema-tenant.sql` | UPDATE / CREATE | Models, DTOs, design SQL |
| `backend/app/services/inventory.py` | UPDATE | `taken_by_night` (sold + blocked), `set_blocked` |
| `backend/app/services/{calendar,booking_reads,bookings,channel_bookings,channel_truth}.py` | UPDATE | Count blocked units as unavailable |
| `backend/app/channels/ical_fetch.py` | CREATE | Safe fetch (see Risks) |
| `backend/app/channels/ical_format.py` | CREATE | Parse imported calendars, write exported ones |
| `backend/app/services/calendar_links.py` | CREATE | Create, list, replace token, remove, build the export |
| `backend/app/services/calendar_link_sync.py` | CREATE | Import one link, diff blocks, run the loop |
| `backend/app/routers/calendar_links.py`, `schemas/calendar_links.py` | CREATE | Staff API and public `GET /api/ical/{token}.ics` |
| `backend/app/routers/channel_simulator.py` | UPDATE | Dev-only test calendar, read in-process, so a browser run needs no outside site |
| `backend/app/tenancy/business_settings.py`, `config.py`, `main.py` | UPDATE | Interval and limits; start and stop the loop |
| `backend/tests/test_ical_format.py`, `test_ical_fetch.py`, `tests/pg/test_calendar_links.py` | CREATE | See Tasks |
| `frontend/lib/calendar-links-api.ts`, `calendar-link-format.ts` + test | CREATE | API and status helpers |
| `frontend/components/channels/CalendarLinksSection.tsx`, `CalendarLinkDialog.tsx` | CREATE | List, add, copy, replace, sync, remove |
| `frontend/app/(authenticated)/channels/page.tsx`, `components/bookings/ChannelAttentionCard.tsx`, `lib/i18n.ts` | UPDATE | Section, conflict entries, `id` + `en` text |
| `components-be.yaml`, `components-fe.yaml`, `packages-be.yaml`, the PRD | UPDATE | Registers and milestone status |

## Tasks

Each backend task is test-first.

### Task 1: Schema and blocked units count everywhere
- **Action**: Migration `0012`, models, `taken_by_night`, `set_blocked`; move the six `sold_by_night` callers to the right read. Tests: a blocked unit lowers availability on the calendar, refuses a staff booking without overbooking consent, flags a channel booking and reaches the channel push.
- **Mirror**: `inventory.py`, migration `0010`.
- **Validate**: `uv run alembic upgrade head && uv run alembic check && REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_calendar_links.py tests/pg/test_channel_push.py tests/pg/test_channel_bookings.py -q`

### Task 2: Parse and write `.ics`
- **Action**: All-day and timed events, missing end date, folded lines, time zones, cancelled events, repeating events (bounded to the horizon), caps on size and event count. Export has no guest or price data and stable event ids.
- **Validate**: `uv run pytest tests/test_ical_format.py -q`

### Task 3: Safe fetch
- **Action**: Rules listed under Risks, tested with an injected transport and resolver: private, loopback, link-local and metadata addresses, a redirect to one of them, DNS answers that mix public and private, oversize and slow responses.
- **Validate**: `uv run pytest tests/test_ical_fetch.py -q`

### Task 4: Links, export and import
- **Action**: Service, routes, background loop and the diff of blocks, written in one transaction with the channel queue. Tests: site block takes a unit; removed event releases it; a failed fetch keeps blocks; two sites on one date take two units; no echo; conflict flagged; token replaced; other tenants see a 404; permissions; plan limit unaffected.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_calendar_links.py -q`

### Task 5: Frontend
- **Action**: Calendar links section, one-time link display with copy, status (last sync, error, at risk), Sync now, replace, remove, conflict entries, read-only without `channels:edit`, the plain warning about slow sites.
- **Validate**: `npx vitest run && npx tsc --noEmit && npm run lint`

### Task 6: Run, browser test, review
- **Action**: Full backend suite, `alembic check`, migration up/down/up on an empty database. With `devtest.sh`: create a link, open the `.ics`, import the test calendar, see the date blocked on the calendar and on the simulated agency, remove the event and see it released, make a fetch fail, check a view-only member, both languages, phone width, `devtest.sh errors`. Code and security review; fix critical and high findings. Update registers; mark the milestone complete.

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
| A pasted URL makes our server call internal addresses (SSRF) | High | HTTPS only, standard port, no credentials in the URL; every resolved address must be public; connect to the checked address so DNS cannot change it; re-check each of at most 3 redirects; 10 s timeout; 2 MB cap; errors never echo the response body |
| Import URLs are secrets (they grant access to the site's calendar) | Medium | Never logged; shown masked after saving |
| Counting `blocked` changes availability across existing flows | High | Task 1 comes first and runs the existing booking and channel suites |
| A bad import releases real blocks and causes a double booking | Medium | Failed or malformed calendars change nothing (D6) |
| Block echo between two systems | Medium | Own import excluded from own export (D4); our event ids ignored on import |
| iCal is slow, so double bookings still occur | High | Stated in the product; conflicts flagged; hold-back suggested |
| A real Airbnb calendar differs from test data | Medium | **The automated and browser runs use fixtures and the dev test calendar.** A check with one real listing is needed before the pilot |
| Long calendars or many links slow the loop | Low | Event cap, horizon cap, due links only, one failure isolated |

## Acceptance

- [ ] A date busy on the linked site takes a unit off sale here and on connected channels within one sync
- [ ] A date with no units left here shows as busy in the exported calendar
- [ ] A removed event releases the unit; a failed fetch releases nothing
- [ ] The export contains no guest, price or booking details
- [ ] Calendar links do not count toward the plan's channel limit
- [ ] Unsafe URLs are refused, including through redirects
- [ ] Routes respect `channels:view` / `channels:edit`; a bad token gets a 404; tenants stay separate
- [ ] Both languages and phone width work
- [ ] All tasks complete, validation passes, coverage at least 80%
- [ ] Patterns mirrored, not reinvented
