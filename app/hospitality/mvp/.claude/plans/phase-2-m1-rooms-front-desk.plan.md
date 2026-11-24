# Plan: Rooms and front desk (Phase 2, Milestone 1)

**Source PRD**: `.claude/prds/phase-2-pms-core.prd.md`
**Selected Milestone**: 1 — Rooms and front desk
**Complexity**: Large

## Summary

Staff get one Front desk page: today's arrivals, in-house guests, departures and a room list. They assign real rooms, check guests in and out, move rooms, mark no-shows and undo a same-day mistake. Bookings have only ever been `tentative`, `confirmed` or `cancelled`, so the main risk is that the new statuses silently break existing report, payment, channel and edit flows. Those are fixed first.

## What already exists, and the gaps

| Need | Today | Gap this milestone closes |
|---|---|---|
| Rooms | `unit` with `hk_status`, `fo_status`, `service_status` | Status fields are never written |
| Room on a booking | `reservationunit.unit_id`, `is_assignment_locked`, `checked_in_at/by`, `checked_out_at/by` | Never used. No migration is expected |
| No double assignment | Database rule `ex_reservationunit_no_double_booking` | A clash must become a clear message |
| Statuses | The database allows `in_house`, `checked_out`, `no_show` | No code sets them |
| Change history | `reservationchange`, `unitstatuslog`, `tenant_audit` | The first two are unused |
| **Editing a booking** | `bookings.py:412` deletes and rewrites room lines | **Any edit would erase the assigned room and check-in record** |
| **Channel report** | `channel_report.py:107` counts `status == confirmed` | **Revenue would vanish the moment a guest checks in** |
| **Late payment** | `booking_holds.py:124` flags extra payments only on `confirmed` | **An extra payment on an in-house booking would be counted, not flagged for refund** |
| **Channel cancel** | `channel_bookings.py:303` ignores anything not `confirmed` | **A channel cancelling an in-house guest would be marked done with nobody told** |
| **Staff cancel** | `cancel_booking` accepts any status except cancelled | **An in-house or checked-out booking could be cancelled and its nights resold** |
| **Removing rooms** | `room_types.py:202` retires units | **A room with a current or future guest could be retired** |
| **Status shown** | `booking_reads.py:176` shows everything else as confirmed | **Staff and guests could not see in-house, checked-out or no-show** |

## Decisions (recommendation first; reply "yes" to accept all)

| # | Question | Recommendation |
|---|---|---|
| D1 | Where does it live? | New page `/front-desk` under the Reservations menu group, with tabs Arrivals, In-house, Departures and Rooms. New permissions `frontdesk:view` and `frontdesk:edit`, included in the manager role. **The backend must restart to show the menu** |
| D2 | How are rooms assigned? | Staff choose from rooms of the booked type that are free for the whole stay. "Assign" suggests the first free, ready room. A room can be locked so it is not moved by accident. Full automatic assignment waits |
| D3 | A booking with several rooms | Each room is assigned separately, but the booking checks in and out **as a whole**. Partial check-in waits |
| D4 | What blocks check-in? | The date must be between arrival and departure, every room must be assigned, and no room may be out of order. A room not marked clean needs an explicit "check in anyway". An unpaid balance is a **warning only** until Milestone 2. ID capture joins in Milestone 4 |
| D5 | Check-out | Sets the booking checked out and each room vacant and dirty. An unpaid balance is a **warning only** until Milestone 2, which adds the proper block |
| D6 | Leaving early | Unused nights go back on sale, and channels are updated. Staff choose **keep the full price** (default) or **charge only nights stayed**. A guest leaving on arrival day still counts one night |
| D7 | No-show | Staff mark it from the arrival date; it is never automatic. Nights go back on sale, and payments stay on record. It is excluded from revenue and is not counted as a cancellation. Any refund or charge stays a staff decision |
| D8 | Undo | Undo check-in and undo check-out on the same day only, with a required reason. Undo check-out is refused if the stay was shortened or the room has been taken |
| D9 | Bookings already past | Unprocessed arrivals and departures from the **last 7 days** appear as "needs attention". Older ones stay as they are, so a property starting today is not flooded |
| D10 | Changes after check-in | Only the departure date, guests and notes can be edited. Extending keeps the same room and needs it free. Cancel is refused. A channel change or cancel for an in-house guest is **shown to staff, never applied automatically** |

## Patterns to Mirror

| Category | Source | Pattern |
|---|---|---|
| Naming | `backend/app/services/booking_refunds.py` | One focused service, named errors, commits at the end |
| Locks | `backend/app/services/bookings.py:92`, `:355` | `lock_property`, then `get_for_update` |
| Errors | `backend/app/routers/bookings.py:121` | `_guarded` maps named errors to HTTP answers |
| Permissions | `backend/app/routers/reports.py:19` | `require_permission` constant, thin router |
| History | `backend/app/services/tenant_audit.py:50` | `record` inside the transaction |
| Availability | `backend/app/services/inventory.py:81`, `bookings.py:341` | `release_units`, then queue a channel update |
| Dates | `backend/app/services/calendar_dates.py` | Property time zone for "today" |
| Tests | `backend/tests/pg/test_booking_refunds.py`, `test_feature_access.py` | HTTP client, permission and isolation cases |
| Frontend | `frontend/app/(authenticated)/bookings/page.tsx`, `components/bookings/*`, `lib/booking-format.ts` | Tabs, table on desktop, rows on phone, tested helpers, text in `lib/i18n.ts` |

## Files to Change

| File | Action | Why |
|---|---|---|
| `backend/app/services/front_desk.py` | CREATE | Check-in, check-out, early departure, no-show, undo |
| `backend/app/services/room_assignment.py` | CREATE | Free rooms, assign, unassign, move, lock |
| `backend/app/services/front_desk_reads.py` | CREATE | Arrivals, in-house, departures, rooms today |
| `backend/app/services/unit_status.py` | CREATE | The one writer of room status, with its log |
| `backend/app/schemas/front_desk.py`, `backend/app/routers/front_desk.py`, `app/main.py` | CREATE / UPDATE | Routes under `/api/front-desk` |
| `backend/app/services/bookings.py` | UPDATE | Keep rooms and stay records through edits; status rules for edit and cancel |
| `backend/app/services/booking_reads.py`, `schemas/bookings.py` | UPDATE | Real status, room names, correct tabs |
| `backend/app/services/channel_report.py` | UPDATE | Count in-house and checked-out stays |
| `backend/app/services/booking_holds.py`, `gateway_events.py` | UPDATE | Extra payments on any active stay are flagged |
| `backend/app/services/channel_bookings.py` | UPDATE | Flag channel changes to active or finished stays |
| `backend/app/services/guest_booking.py` | UPDATE | Guests see the true status |
| `backend/app/services/room_types.py` | UPDATE | Do not retire a room with a current or future guest |
| `backend/docs/rbac-spec.yaml` | UPDATE | Permissions and menu entry |
| `backend/tests/pg/test_front_desk.py`, `test_room_assignment.py`, `test_front_desk_regressions.py` | CREATE | See Tasks |
| `frontend/app/(authenticated)/front-desk/page.tsx`, `components/front-desk/*`, `middleware.ts` | CREATE / UPDATE | Page and protected route |
| `frontend/lib/front-desk-api.ts`, `front-desk-format.ts` + test | CREATE | API and pure helpers |
| `frontend/components/bookings/BookingDetailDialog.tsx`, `BookingTable.tsx`, `lib/bookings-api.ts`, `lib/booking-format.ts`, `lib/i18n.ts` | UPDATE | New statuses, room shown, edits limited, `id` + `en` text |
| `components-be.yaml`, `components-fe.yaml`, the PRD | UPDATE | Registers and milestone status |

## Tasks

Each backend task is test-first. Work on a new branch, `feat/phase-2-m1-front-desk`.

### Task 1: Protect existing flows
- **Action**: Write failing tests for each bold gap above, then fix them: edits keep rooms and stay records; the report counts in-house and checked-out stays; extra payments are flagged; channel changes reach staff; staff cancel is refused after check-in; a room in use cannot be retired; the true status is shown.
- **Mirror**: `test_channel_report.py`, `test_booking_refunds.py`, `test_channel_bookings.py`.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_front_desk_regressions.py tests/pg/test_channel_report.py tests/pg/test_channel_bookings.py tests/pg/test_direct_booking.py -q`

### Task 2: Room assignment
- **Action**: Free-room list, assign, unassign, lock, in-house move with room statuses and log. Tests: a clash is refused with a clear message, including two staff assigning at once; wrong room type; out-of-order room; locked room; back-to-back stays; other tenants.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_room_assignment.py -q`

### Task 3: Check-in, check-out and exceptions
- **Action**: D3 to D8, each writing history. Tests: every check-in rule, multi-room bookings, dirty-room confirmation, early departure at both prices and its effect on availability, channels and report, arrival-day departure, no-show, undo rules, double clicks.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_front_desk.py -q`

### Task 4: Lists and routes
- **Action**: Arrivals, in-house, departures and rooms today in the property's time zone, D9's attention window, permissions. Tests for 403, tenant separation and the time-zone day boundary.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_front_desk.py tests/pg/test_feature_access.py -q`

### Task 5: Frontend
- **Action**: Front desk tabs, assign and move dialog, check-in and check-out confirmations with warnings, early departure choice, no-show, undo, rooms list, read-only without `frontdesk:edit`, large touch targets, and new statuses on the Bookings page.
- **Validate**: `npx vitest run && npx tsc --noEmit && npm run lint`

### Task 6: Run, browser test, review
- **Action**: Full suites. `devtest.sh restart`. Browser: book direct and through a channel, assign, check in with a dirty-room warning, move room, extend, leave early, check out, no-show, undo, confirm the report and availability, a view-only API case, both languages, phone width, `devtest.sh errors`. Code, security and database review; fix critical and high findings. Update registers and mark the milestone complete.

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
| New statuses break existing money, channel or report flows | High | Task 1 comes first; every known `confirmed` check is reviewed and tested |
| Editing a booking loses its room | High | Fixed and tested in Task 1 |
| Two staff assign the same room | Medium | Property lock plus the database rule; the clash becomes a clear message |
| Early departure makes revenue or availability wrong | Medium | Reuses the existing stay-change path; tested against report and channels |
| A wrong check-out sells an occupied room | Medium | Confirmation step, same-day undo, history |
| Balance warnings let guests leave unpaid until Milestone 2 | Medium | Stated in the product; Milestone 2 adds the block. **Do not pilot before Milestone 2** |
| Phase 0 and 1 are still not on `master` | Medium | Branch from the current branch; merge those pull requests first if possible |

## Acceptance

- [ ] Staff see today's arrivals, in-house guests, departures and rooms in the property's time zone
- [ ] Staff assign and move rooms, and one room can never hold two overlapping stays
- [ ] Check-in and check-out follow D3 to D5 and update room status with history
- [ ] Early departure, no-show and same-day undo work as decided
- [ ] Editing a booking never loses its room or stay record
- [ ] Reports, payments, channels and guest pages stay correct for every new status
- [ ] Every route needs `frontdesk:view` or `frontdesk:edit`; tenants stay separate
- [ ] Both languages and phone width work
- [ ] All tasks complete, validation passes, coverage at least 80%
- [ ] Patterns mirrored, not reinvented
