# Plan: Bookings in from channels (Phase 1, Milestone 5)

**Source PRD**: `.claude/prds/phase-1-channel-manager-booking-engine.prd.md`
**Selected Milestone**: 5 — Bookings in
**Complexity**: Large

## Summary

A booking made on the simulated agency — new, modified or cancelled — appears in the
bookings list on its own, without retyping, never twice, with its channel reference,
commission and who collects the payment. A booking for a night with nothing left is
accepted anyway (the channel already confirmed it to the guest) and flagged
"overbooking risk"; a booking for a channel room with no match lands in a
"needs attention" list. Availability on the calendar follows, and the channel's
window is updated within seconds.

## What already exists

| Need | Existing |
|---|---|
| The inbound envelope | `channelbooking` table — idempotent by (connection, external id, version), `event_kind new/modify/cancel`, `raw`, `reservation_id`, `processing_status pending/applied/needs_attention/…`, `attention_reason 'unmapped_product','overbooking_risk','price_mismatch'`, `acknowledged_at` |
| Booking creation | `bookings.book(order)` — the single entry point built for exactly this in Milestone 2: stay + guest + source channel, optional hand-set total, `allow_overbooking` |
| Channel sources | `channel` rows per catalogue code; `staff_source()` find-or-creates; connection knows its `channel_id` |
| Overbooking | `inventory` counts; `book(allow_overbooking=True)`; the "overbooking risk" flag already computed for the list |
| Change/cancel | `update_booking` (release old nights, take new), `cancel_booking` |
| Availability out | Milestone 4's queue triggers already fire inside `book`/`update`/`cancel` |
| Guest records | `booking_guests.find_or_create_guest` |
| Provider interface | `app/channels/provider.py` (fetch_property, push_ari, fetch_current_ari) |
| Simulator | stores listings + acknowledged ARI; a pusher loop runs in-process |

## Decisions (recommendation first — reply "yes" to accept all)

| # | Question | Recommendation |
|---|---|---|
| D1 | How do bookings arrive? | The simulated agency gains a booking store on its listing. A dev-only route creates a booking on the agency ("Create a test booking", mirroring "Create a test listing"). A **poller** in the same style as the pusher fetches new/modified/cancelled bookings from every live connection every 10 s and feeds them through the same handler a real webhook would (`handle_booking_event`) — so the inbound path is exercised exactly as a certified channel's polling SLA would be. |
| D2 | The handler | `channel_bookings.handle_booking_event(session, event)` — one idempotent entry point (BR-CM-03): store the envelope first (unique on id+version), then apply new/modify/cancel, mark `applied` or `needs_attention`, set `acknowledged_at` only after durable storage (FR-CM-031). |
| D3 | New booking | Translate the channel's rooms/rates back through the mapping to our room type + rate plan (FR-CM-032), attach commission (from the connection) and the collect model, and call `book()` with `allow_overbooking=True` always — a channel booking is never rejected (BR-CM-02); shortage is flagged on the reservation and the envelope (`attention_reason='overbooking_risk'`). |
| D4 | Guest | The channel sends guest name and phone; a matching phone links to the existing guest (the inbox's person), else a new guest record. |
| D5 | Price | The channel's selling price is the booking total (hand-set, `price_edited=True`), broken over nights from the channel's data; a difference beyond 1 % from our calendar truth sets `attention_reason='price_mismatch'` (a warning, never a rejection — FR-CM-033 as a flag). |
| D6 | Modify | The channel sends a new version with new dates/rooms/guest. The handler calls `update_booking` (availability moves); if the mapped room changed, old and new nights both update. |
| D7 | Cancel | `cancel_booking` with reason "Dibatalkan di kanal" — units return, the record and payments stay. The channel's own cancellation reference is kept on the envelope. |
| D8 | Unmapped product | A booking naming a channel room/rate with no active mapping is **stored and acknowledged** but marked `needs_attention` with `attention_reason='unmapped_product'`; it appears in the bookings page's attention list with a "match this room" shortcut. No reservation is created until staff map the room (then a "Apply" action creates it). |
| D9 | Where staff see it | The bookings page gains a "Needs attention" chip on channel bookings that are flagged, and the attention list shows the reason with a link to the connection's matching. The channel's name and commission show on the booking detail. |
| D10 | Availability out | No new triggers — `book`/`update`/`cancel` already queue the nights (Milestone 4), so the channel's window shrinks within seconds of its own booking landing. |
| D11 | Duplicate deliveries | The (connection, external id, version) unique key ignores repeats; an older version arriving after a newer one is ignored (highest-version-wins). |
| D12 | Pull cadence & bookkeeping | The poller remembers each connection's last seen version/time (`channelconnection.last_booking_pull_at` already exists); every pull and every applied event is recorded (tenant audit: `channel.booking.applied/flagged/cancelled`). |

## Patterns to Mirror

| Category | Source | Pattern |
|---|---|---|
| Idempotent inbound entry | `gateway_events.handle_gateway_event` | Store-first on a unique key, apply, ack after durability |
| Record first, then act | `checkout.start_payment` | Envelope row committed before any booking work |
| Provider interface | `app/channels/provider.py` | Add `fetch_booking_changes(call, property_id, since) -> list[ChannelBookingEvent]` |
| Simulator store | `app/channels/simulator.py` (ARI store) | A bookings store on the listing; dev-only create route like `channel_simulator.listings` |
| Background loop | `services/channel_push.run_channel_pusher` | Same shape: tenants → connections → work, PostgreSQL-only, stop event |
| Booking creation | `services/bookings.book` + `BookingOrder` | Reuse untouched; the channel source row plays the `source` |
| Flags on the list | `booking_reads._oversold_bookings`, dashboard card | Same read-time flag pattern for price/unmapped attention |
| Tests | `tests/pg/test_channel_push.py` (push_now helper, simulator knobs) | A `pull_now(session_factory, tenant_id)` helper; permission and isolation tests |

## Files to Change

| File | Action | Why |
|---|---|---|
| `backend/app/channels/provider.py` | UPDATE | `ChannelBookingEvent`, `ChannelGuest`, `fetch_booking_changes` on the protocol |
| `backend/app/channels/simulator.py` | UPDATE | Booking store per listing (create/modify/cancel with versions), `fetch_booking_changes` |
| `backend/app/routers/channel_simulator.py` | UPDATE | Dev-only: create / modify / cancel a booking on a listing |
| `backend/app/services/channel_bookings.py` | CREATE | `handle_booking_event` (idempotent), translation through mappings, new/modify/cancel application, attention reasons, acknowledgement |
| `backend/app/services/channel_booking_pull.py` | CREATE | The poller: live connections → fetch changes → handle; `run_booking_poller` loop |
| `backend/app/services/booking_reads.py`, `schemas/bookings.py` | UPDATE | Channel fields (source name/commission/collect), attention flags, the needs-attention list on the bookings page |
| `backend/app/routers/bookings.py` | UPDATE | Attention list endpoint (or a filter on the existing list) |
| `backend/app/routers/channels.py` | UPDATE | Per-connection booking events (for the connection page's recent activity) |
| `backend/app/main.py` | UPDATE | Start the poller beside the pusher |
| `backend/tests/pg/test_channel_bookings.py` | CREATE | New/modify/cancel, duplicates, stale versions, overbooking flag, unmapped, price mismatch, guest linking, commission, availability out, isolation, permissions |
| `backend/tests/pg/conftest.py` | UPDATE | `agency_booking(...)` helper, `pull_now(...)` |
| `frontend/lib/bookings-api.ts`, `booking-format.ts` + test | UPDATE | Attention fields, channel-source labels |
| `frontend/components/bookings/BookingTable.tsx`, `BookingDetailDialog.tsx` | UPDATE | Attention chip, channel source line, "view connection" link |
| `frontend/app/(authenticated)/channels/[id]/page.tsx` | UPDATE | Recent channel bookings section |
| `frontend/lib/i18n.ts` | UPDATE | New strings in `id` and `en` |
| `components-be.yaml`, `components-fe.yaml`, the PRD | UPDATE | Registers; milestone status |

No migration is expected: `channelbooking`, `reservation.channel_id` and
`channelconnection.last_booking_pull_at` already exist. If implementation shows a gap
(a per-envelope flag column), it will be a small additive one.

## Tasks

Each backend task is test-first.

### Task 1: Provider interface and the agency's booking store
- **Action**: `ChannelBookingEvent` (external id, version, kind, room/rate ids, dates,
  guests, prices, currency, collect model, raw), `fetch_booking_changes(call,
  property_id, since)`. The simulator: a bookings list per listing with
  create/modify/cancel keeping versions; dev-only routes to drive it. Unit tests for
  version ordering and the store.
- **Validate**: `uv run pytest tests/test_channel_simulator.py -q`

### Task 2: The idempotent handler
- **Action**: `channel_bookings.handle_booking_event` — store the envelope (unique
  id+version; older-than-applied versions ignored), translate through mappings,
  `book()`/`update_booking()`/`cancel_booking()` with the channel source, commission and
  collect model; attention reasons (overbooking, unmapped, price mismatch);
  acknowledge after durability; audit entries. Tests: new booking lands with the
  channel's name and price; duplicate delivery ignored; stale version ignored; modify
  moves dates and availability; cancel returns units; overbooked night accepted and
  flagged; unmapped room stored + flagged, no reservation; price mismatch flagged;
  guest phone links to the inbox's guest.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_channel_bookings.py -q`

### Task 3: The poller
- **Action**: `channel_booking_pull.pull_due` (tenants from the control plane, live
  connections, `since` from `last_booking_pull_at`), the lifespan loop (10 s),
  recording pulls. Tests: a booking made on the agency reaches the bookings list after
  one `pull_now`; two bookings in order both land; nothing live → nothing pulled;
  availability out (the agency's own window shrinks after its booking is applied).
- **Validate**: as Task 2

### Task 4: Reads, attention list and permissions
- **Action**: Booking rows gain channel fields and attention flags; a needs-attention
  view (reason, envelope, "view connection"); connection page shows recent channel
  bookings; route permissions (`bookings:view`, `channels:view`). Tests for each read
  and permission; isolation with `other_client`.
- **Validate**: as Task 2

### Task 5: Frontend
- **Action**: Attention chip and channel-source line on the bookings list/detail;
  the needs-attention list (reason + link to the connection's matching); recent
  bookings on the connection page; both languages; helper tests first.
- **Validate**: `npx vitest run && npx tsc --noEmit && npm run lint`

### Task 6: Run, browser test, review
- **Action**: Full backend suite + `alembic check`; `devtest.sh start`; with Playwright:
  connect, go live, create a booking on the agency (dev panel), watch it appear within
  seconds with the channel's name and price; modify it; cancel it; overbook the last
  night and see the flag; book an unmapped room and see the attention list; check
  availability moved on the calendar; permissions (view-only staff cannot pull);
  both languages, phone width; console and `devtest.sh errors` clean; stop. Code and
  security review; fix critical and high findings. Registers; milestone complete.

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
| A channel booking double-books silently | Medium | `book()` under the property lock with the same counting as staff bookings; overbooking allowed only via the explicit flag and always flagged |
| Modify races a staff edit on the same reservation | Medium | Both go through `update_booking` under the property row lock; last writer wins, version history kept in the envelope |
| An unmapped booking is quietly forgotten | Medium | Stored + flagged + surfaced in the attention list; nothing is dropped unrecorded |
| The poller and a future webhook double-apply | Low (now) | The unique (id, version) key makes the path idempotent regardless of transport |
| Availability drift after applying a channel booking | Medium | Milestone 4's triggers fire inside `book`/`update`/`cancel` — verified by test |
| The simulator's bookings look nothing like a real agency's | Medium | Real-shaped payloads (external ids, versions, guest objects, price breakdowns) |
| Scope creep into VCC/messaging/reviewing no-shows | Medium | Out of scope per the PRD; the envelope keeps `raw` so later features can extend |

## Acceptance

- [ ] A booking made on the simulated agency appears in the bookings list on its own within seconds, never twice
- [ ] Modifications and cancellations from the channel move the booking and give the units back
- [ ] A booking for a sold-out night is accepted and flagged "overbooking risk"
- [ ] A booking for an unmapped channel room is stored, flagged and surfaced for staff
- [ ] The channel's own availability window shrinks after its booking is applied
- [ ] The booking shows its channel, commission and collect model; the connection page lists recent channel bookings
- [ ] All routes respect their permissions; both languages; phone width
- [ ] All tasks complete, validation passes, coverage at least 80%
- [ ] Patterns mirrored, not reinvented
