# Plan: Bookings list (Phase 1, Milestone 2)

**Source PRD**: `.claude/prds/phase-1-channel-manager-booking-engine.prd.md`
**Selected Milestone**: 2 — Bookings list
**Complexity**: Large

## Summary

Staff can enter a booking for a WhatsApp, phone or walk-in guest, change it, cancel it and record
money received, and see every booking in one list. Each booking takes units of a room type off
sale for its nights; cancelling or shortening it gives them back, and the calendar from Milestone 1
shows what is left. This is the list that channel bookings (Milestone 5) and direct bookings
(Milestone 7) will land in, so one function creates a booking and one function changes how many
units a date has sold.

## What already exists

Tables from Phase 0 Milestone 1 (migration `0003`), with models, unused so far:

| Need | Existing table / model |
|---|---|
| Booking | `reservation` — `backend/app/models/tenant/reservations/reservation.py` (number, status, source, dates, guests, total, paid, balance, notes, terms snapshots) |
| Room line of a booking | `reservationunit` — `reservations/reservation_unit.py` (room type, rate plan, optional specific unit) |
| Price per night | `reservationdailyrate` — `reservations/reservation_daily_rate.py` |
| Units sold per date | `inventoryday` — `inventory/inventory_day.py` (`available` is worked out by the database) |
| Where it came from | `channel` — `organisation/channel.py` (code, kind, `is_direct`) |
| Guest | `guest` — already filled by the inbox (`services/inbound.py:73`) |
| Money received | `payment` — already has `reservation_id` and methods `cash`, `bank_transfer`, `other` |
| Prices and availability | `services/calendar.py` — `read_calendar`, from Milestone 1 |

No migration is expected; if implementation shows a missing column, it will be a small additive one.

## Decisions (recommendation first — reply "yes" to accept all)

| # | Question | Recommendation |
|---|---|---|
| D1 | What can one booking hold? | One room type, one or more units of it, one rate plan, one stay. Several room types in one booking wait for the PMS. |
| D2 | Is a specific unit (room number) chosen? | No. A booking takes "one Deluxe", not "Deluxe 3". Assigning units belongs to check-in (Phase 2). |
| D3 | Staff book when nothing is left | Warn and let them book anyway after confirming; the booking is flagged "overbooking risk" for as long as that date is oversold. Channels need the same flag in Milestone 5. |
| D4 | Closed dates and minimum stay | They are selling rules for guests and channels. Staff see a notice but are not blocked. |
| D5 | Price | Suggested from the calendar (the nightly prices of the chosen rate plan, added up). Staff can change the total; the nightly amounts are adjusted to match. Whole rupiah, all-in. |
| D6 | Sources staff can pick | WhatsApp, Walk-in, Phone, Instagram, Other. All count as direct (no commission). |
| D7 | Guest | Name required; WhatsApp or phone number optional. A number that matches a guest from the inbox links to that guest instead of creating a second one. |
| D8 | Starting from a chat | A "Create booking" button in an inbox conversation opens the form with the guest and source filled in. |
| D9 | Status | Confirmed when saved. Staff can cancel with an optional reason. No check-in or check-out yet. |
| D10 | Payment state | Staff record money received (amount, cash / bank transfer / other, date). The booking shows unpaid, partly paid or paid, and the balance. Paying through a payment link attached to the booking comes with the booking page in Milestone 7. |
| D11 | Changing a booking | Dates, room type, number of units, rate plan, price, guests, notes and source can be changed while it is confirmed; availability moves with it. |
| D12 | Booking number | A short code staff and guests can read aloud, e.g. `VK-7F3K2Q`, unique per property. |
| D13 | Dates allowed | Arrival from 30 days ago (to record stays after the fact) up to the calendar horizon; 1 to 365 nights. Both are configurable values. |
| D14 | Lowering a room type's unit count below what is sold | Allowed, and the affected bookings are flagged "overbooking risk" — refusing would block an owner whose room is genuinely out of use. The form warns before saving. |
| D15 | The list | Tabs: Upcoming, Staying now, Past, Cancelled. Search by guest name or booking number. Newest arrivals first where it makes sense; loads more on demand. |
| D16 | On the calendar | "Available" becomes units minus units sold, and oversold dates are marked. |

## Patterns to Mirror

| Category | Source | Pattern |
|---|---|---|
| Naming | `backend/app/services/payment_links.py:280`, `services/calendar.py` | One service module per topic; one create function reused by later entry points |
| Errors | `backend/app/routers/payment_links.py:38`, `routers/calendar.py` | Named service exceptions mapped to HTTP answers in `_guarded`; 404 for another tenant's id |
| Validation | `backend/app/schemas/calendar.py`, `schemas/rooms.py` (`RoomName`) | Pydantic requests with `extra="forbid"`; safe single-line text; `Rupiah` amounts |
| Config | `backend/app/tenancy/business_settings.py` | Limits and windows as validated settings |
| Locking | `backend/app/services/calendar.py` (`apply_calendar_change`), `services/checkout.py:282` | Lock the property row, then change counted rows in the same transaction |
| Idempotent single entry | `backend/app/services/gateway_events.py` (`handle_gateway_event`) | One function all sources call; safe to call twice |
| Guests | `backend/app/services/inbound.py:73` | Find or create a guest by phone number |
| Paging | `backend/app/services/payment_links.py` (cursor `iso|uuid`) | Keyset pagination with an opaque cursor |
| Money | `backend/app/services/payment_links.py` (`money`, `format_rupiah`), `frontend/lib/money.ts` | Decimal on the server, whole rupiah in forms |
| Dates | `backend/app/services/calendar_dates.py`, `frontend/lib/calendar-grid.ts` | Property-local dates; maths on `YYYY-MM-DD` strings in the browser |
| Tests | `backend/tests/pg/test_calendar.py`, `test_calendar_isolation.py`, `tests/pg/conftest.py` | PostgreSQL tests through the HTTP client, isolation tests with `other_client`, helpers in conftest, simultaneous-request tests with `asyncio.gather` |
| Pages | `frontend/app/(authenticated)/payment-links/page.tsx`, `components/calendar/CalendarChangeDialog.tsx` | List page with tabs and "load more"; dialogs for create and edit; text via `lib/i18n.ts` in `id` and `en` |
| Upsert | none in the codebase yet | State explicitly: `INSERT … ON CONFLICT (tenant_id, unit_type_id, stay_date) DO UPDATE` on `inventoryday`, in date order |

## Files to Change

| File | Action | Why |
|---|---|---|
| `backend/app/tenancy/business_settings.py` | UPDATE | Back-entry days (30), longest stay (365), page size |
| `backend/app/services/inventory.py` | CREATE | The one place units sold per date change: `take_units`, `release_units`, `sold_by_date`, `sync_physical` |
| `backend/app/services/booking_sources.py` | CREATE | Find or create the property's source rows (WhatsApp, walk-in …) |
| `backend/app/services/booking_numbers.py` | CREATE | Readable unique booking numbers |
| `backend/app/services/booking_pricing.py` | CREATE | Suggested nightly prices from the calendar; spreading an edited total over the nights |
| `backend/app/services/bookings.py` | CREATE | `create_booking` (the single entry point later milestones reuse), `update_booking`, `cancel_booking`, list, read, quote |
| `backend/app/services/booking_payments.py` | CREATE | Record money received; keep paid and balance in step |
| `backend/app/services/booking_guests.py` | CREATE | Find or create the guest (shared logic lifted from `inbound.py`) |
| `backend/app/services/inbound.py` | UPDATE | Use the shared guest function |
| `backend/app/services/calendar.py` | UPDATE | `available` = units − sold; oversold flag per date |
| `backend/app/services/room_types.py` | UPDATE | Keep `inventoryday.physical` in step when the unit count changes |
| `backend/app/schemas/bookings.py`, `schemas/calendar.py` | CREATE / UPDATE | Request and read shapes; `oversold` on a calendar day |
| `backend/app/routers/bookings.py` | CREATE | `/api/bookings` (list, create, read, change, cancel, payments) and `/api/bookings/quote` |
| `backend/app/main.py`, `backend/docs/rbac-spec.yaml` | UPDATE | Register the router; menu entry "Bookings" |
| `backend/tests/pg/test_bookings.py`, `test_booking_changes.py`, `test_booking_payments.py`, `test_inventory.py`, `test_bookings_isolation.py` | CREATE | Behaviour, availability, simultaneous bookings, tenant separation |
| `backend/tests/test_booking_pricing.py`, `test_booking_numbers.py` | CREATE | Pure logic |
| `backend/tests/pg/conftest.py` | UPDATE | Helper `make_booking` |
| `frontend/lib/bookings-api.ts`, `booking-format.ts` + test, `booking-forms.ts` + test | CREATE | Calls; state labels, night counts, payment state; form checks |
| `frontend/components/bookings/BookingDialog.tsx`, `BookingTable.tsx`, `BookingDetailDialog.tsx`, `RecordPaymentDialog.tsx` | CREATE | Create/edit form with live price and availability notice; list; detail with payments and cancel |
| `frontend/app/(authenticated)/bookings/page.tsx` | CREATE | The list page |
| `frontend/app/(authenticated)/inbox/page.tsx` | UPDATE | "Create booking" from a conversation |
| `frontend/components/calendar/CalendarGrid.tsx`, `frontend/lib/calendar-api.ts` | UPDATE | Show what is left; mark oversold dates |
| `frontend/app/(authenticated)/dashboard/page.tsx` | UPDATE | Arrivals today and bookings needing attention |
| `frontend/lib/i18n.ts`, `frontend/middleware.ts` | UPDATE | Text in both languages; protect the new page |
| `components-be.yaml`, `components-fe.yaml`, the PRD | UPDATE | Registers; milestone status |

No new packages.

## Tasks

Each backend task is test-first.

### Task 1: Units sold per date
- **Action**: `inventory.py`. `take_units(room type, nights, count)` and `release_units(…)` upsert `inventoryday` rows in date order inside the caller's transaction and return the dates left oversold. `sync_physical` updates future rows when a room type's unit count changes. Wire `calendar.read_calendar` to units − sold and an `oversold` flag. Tests: take, release, release never below zero, oversold dates reported, two simultaneous takes of the last unit leave sold = 2 and exactly one caller told it oversold, unit-count change reflected, isolation.
- **Mirror**: locking in `calendar.apply_calendar_change`.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_inventory.py tests/pg/test_calendar.py -q`

### Task 2: Pricing, numbers, sources, guests
- **Action**: Pure functions first: nightly prices for a stay from the calendar read; spreading an edited total across nights so the nightly amounts add up exactly; booking number generation with a retry on collision. Then find-or-create for sources and guests (move the guest logic out of `inbound.py` unchanged in behaviour).
- **Mirror**: `payment_links.money`; `inbound.py:73`.
- **Validate**: `uv run pytest tests/test_booking_pricing.py tests/test_booking_numbers.py -q && REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_inbound.py -q`

### Task 3: Create, read, list, quote
- **Action**: `POST /api/bookings/quote` returns nightly prices, total, availability per night and notices (closed, minimum stay, not enough units) for a stay without saving. `POST /api/bookings` creates: validates dates and capacity, takes units, stores the booking, its room lines, nightly prices and terms snapshot; refuses when units are short unless `allow_overbooking` is set. `GET /api/bookings` with tab, search and cursor; `GET /api/bookings/{id}` with payments. Tests: happy path, price suggested vs. edited, guest linking by phone, each source, capacity, date limits, short availability refused then accepted with the flag, the flag clearing when another booking is cancelled, list tabs around today in the property's timezone, search, paging, two simultaneous bookings for the last unit (one succeeds, one is told it is short), isolation.
- **Design note**: `create_booking` takes a source, a guest and a stay — nothing about who is calling. Milestones 5 and 7 call it with a channel or the booking page as the source.
- **Mirror**: `payment_links.create_link`, `_guarded`.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_bookings.py tests/pg/test_bookings_isolation.py -q`

### Task 4: Change and cancel
- **Action**: `PATCH /api/bookings/{id}` — release the old nights and take the new ones in one transaction, re-price unless the total was set by hand, same overbooking rule. `POST /api/bookings/{id}/cancel` with optional reason — releases units, keeps the record and its payments. A cancelled booking cannot be changed. Tests: extend, shorten, move, change room type and count, cancel returns units, cancel twice, change after cancel, concurrent change and cancel.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_booking_changes.py -q`

### Task 5: Money received
- **Action**: `POST /api/bookings/{id}/payments` (amount, method, received date, note) and removing a wrongly entered one; paid and balance recomputed from the payment records; payment state unpaid / partly paid / paid / overpaid. Tests: partial then full, overpayment shown not refused, removal, cancelled booking keeps its payments, validation, isolation.
- **Mirror**: `Payment` records as in `transfer_proofs._store_proof`.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_booking_payments.py -q`

### Task 6: Unit count and settings
- **Action**: `room_types.update_room_type` calls `sync_physical`; the response says which future dates became oversold. New settings with tests.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_room_types.py tests/test_business_settings.py -q`

### Task 7: Frontend — bookings page
- **Action**: Helpers with tests first. Page with four tabs, search, table (phone: stacked rows), "New booking". Booking dialog: dates, room type, units, rate plan, guests, guest name and number, source, notes; the price and any notices update from the quote as the form changes, with stale answers ignored; total editable; "book anyway" confirmation when short. Detail dialog: summary, nightly prices, payments, record payment, change, cancel.
- **Mirror**: `payment-links/page.tsx`, `CalendarChangeDialog.tsx`, `usePolling` stale guards.
- **Validate**: `npx vitest run && npx tsc --noEmit && npm run lint`

### Task 8: Frontend — inbox, calendar, dashboard
- **Action**: "Create booking" in a conversation; calendar shows what is left and marks oversold dates; dashboard card with today's arrivals and bookings at risk.
- **Validate**: as Task 7

### Task 9: Run, browser test, review
- **Action**: Full backend suite with coverage and `alembic check`. `bash scripts/devtest.sh start`; with Playwright on a fresh workspace: set up rooms, create bookings from the page and from a chat, watch the calendar count drop, book the last unit, see the short-availability warning and book anyway, see the flag, cancel and see it clear, change dates, record a deposit and the balance, search, each tab, both languages, phone width; console and `devtest.sh errors` clean; stop. Code review and security review; fix critical and high findings. Update the registers; mark the milestone complete.

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
| Two bookings take the last unit at the same moment | Medium | One function changes units sold, by upsert in date order inside the booking's transaction; simultaneous-request tests |
| Units sold drifts from the bookings that exist (a bug in change or cancel) | Medium | Change = release old + take new in one transaction; a test that recounts sold from the bookings after every scenario |
| Deadlock between two bookings over overlapping dates | Low | Rows always touched in date order under the property lock |
| The reservation tables model far more than is used (groups, companies, check-in) | High | Fill only the fields in the Decisions table; leave the rest at defaults |
| Edited totals do not add up across nights | Medium | Spreading tested for exact sums, including amounts that do not divide evenly |
| "Today" for the tabs is wrong for properties away from UTC | Medium | Property-local dates throughout; boundary tests |
| Moving the guest logic changes inbox behaviour | Low | Move without changing it; the existing inbound tests must stay green |
| Staff ignore the overbooking warning and double-book | Medium (product) | Explicit confirmation, a visible flag in the list, calendar and dashboard |
| Booking data leaks between properties | Low | Every id looked up within the caller's property; isolation tests for each route |
| Guest names and numbers stored without a stated basis | Medium | Keep only what a booking needs; the privacy notice arrives with the booking page (Milestone 7) |

## Acceptance

- [ ] Staff can create, change and cancel a booking and record money received
- [ ] Availability on the calendar follows bookings, changes and cancellations
- [ ] Simultaneous bookings cannot both silently take the last unit
- [ ] Short availability is warned about, can be overridden on purpose, and is flagged while it lasts
- [ ] The list shows every booking with dates, room type, guest, price, source, payment state and status, by tab and search
- [ ] `create_booking` can be called by later milestones without change
- [ ] Works in Bahasa Indonesia and English, and at phone width
- [ ] All tasks complete, validation passes, coverage at least 80%
- [ ] Patterns mirrored, not reinvented
