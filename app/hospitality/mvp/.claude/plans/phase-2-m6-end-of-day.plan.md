# Plan: End of day (Phase 2, Milestone 6)

**Source PRD**: `.claude/prds/phase-2-pms-core.prd.md`
**Selected Milestone**: 6 — End of day
**Complexity**: Large

## Summary

Each morning an operator closes the previous day. The product lists what still needs attention (guests not checked in or out, open cash drawers, proofs waiting, APOA overdue), shows the day's summary (occupancy, room revenue, extras, money by method, the cash book) and freezes it. Front-desk staff run a cash drawer per shift: opening float, cash in and out, a count at the end and the difference. A closed day's money can no longer be changed by back-dating. Corrections go on today.

## What already exists, and the gaps

| Need | Today | Gap this milestone closes |
|---|---|---|
| Day close | `businessday` (one per property and date: open, closing, closed; checklist; stats snapshot; who closed) | Unused |
| Cash drawer | `cashiershift` (per staff member: business date, opening float, expected, counted, a computed difference, status); `payment.cashier_shift_id`, `foliotransaction.cashier_shift_id` | Unused; desk payments belong to no shift |
| Money | Desk payments (cash, transfer, card, QRIS, other) may be dated up to a year back and removed later; refunds recorded later; online payments | A past day's totals can change at any time |
| Bill lines | Dated by business date; voids only the same day; later mistakes are corrections on today | Fits a closed day already |
| Attention lists | Front desk (arrivals, departures), transfer proofs, APOA | Not brought together |

## Decisions (recommendation first; reply "yes" to accept all)

| # | Question | Recommendation |
|---|---|---|
| D1 | Which day is closed | **The previous day, the next morning** (any day before today, oldest open first). Closing "today" late at night would need a business date that runs ahead of the calendar, which small properties find confusing. The front desk shows "Yesterday (25 Nov) is not closed yet" until it is. Days with no activity can be closed in one go |
| D2 | What must be clear first | **Blocking**: confirmed arrivals still not checked in or marked no-show, guests still in house past their departure, open cash drawers of that day. **Warnings**: transfer proofs waiting, APOA overdue, guests who left unpaid. Blocking items can be overridden by someone with `bookings:edit`, with a reason in the history |
| D3 | What closing does | Saves the **summary snapshot** and **locks the day's money**. Desk payments and refunds dated on a closed day, or removing a payment received on a closed day, are refused ("this day is closed; record it today"). Bill lines are already dated today. **Reopen** by `endofday:edit` with a reason, in the history; closing again replaces the snapshot |
| D4 | Daily summary | Rooms available and sold, **occupancy**, room revenue as priced, **ADR**, **RevPAR**; arrivals, departures, no-shows, cancellations; extras by category; service charge and PBJT; money received and refunded **by method**, online versus desk; payments for future stays (deposits); the cash book; guests who left unpaid. Shown live for an open day and frozen at close |
| D5 | Cash drawer (shift) | Staff **open a drawer** with an opening float. Every desk payment and refund they record goes to their open drawer; if none is open, one opens with a zero float (said on screen). **Paid-outs** (petty cash, for example buying supplies) are recorded with a reason. **Closing**: count the cash; expected = float + cash in − cash out − paid-outs; a non-zero difference needs a note. Shift totals by method for every method |
| D6 | Paid-outs | Stored as outgoing cash payments with no booking, marked "paid-out", so the cash book adds up. Booking and channel figures only count payments of a booking, which is checked in tests |
| D7 | Permissions | New `endofday:view` (summary, checklist, all drawers) and `endofday:edit` (close, reopen). Opening and closing **your own** drawer and paid-outs need `bills:edit`, like taking payments. Manager role holds all |
| D8 | Where | A new **"End of day"** page under Reservations: date picker, checklist, summary, drawers. A drawer button on the front desk. A banner when yesterday is not closed |

## Patterns to Mirror

| Category | Source | Pattern |
|---|---|---|
| Money entries and locks | `backend/app/services/booking_payments.py:56` (`record_payment`) | Lock property, then booking; recompute balance |
| Day reads | `backend/app/services/front_desk_reads.py:184` (`read_today`) | Reads by property date |
| Figures | `backend/app/services/channel_report.py` | Room revenue from nightly rates of earning bookings |
| Refusals | `backend/app/services/front_desk_errors.py`, `apoa_errors.py` | Stable `code` the page translates |
| Override with permission | `backend/app/routers/front_desk.py` (`check_out`, `check_in`) | Second permission checked in the route |
| History | `backend/app/services/tenant_audit.py:50` | `record` inside the transaction |
| Tests | `backend/tests/pg/test_bills.py`, `test_apoa.py` | HTTP client, permissions, tenant separation |
| Frontend | `frontend/app/(authenticated)/apoa/page.tsx`, `components/bills/*` | Tabs, dialogs, tested helpers, text in `lib/i18n.ts` |

## Files to Change

| File | Action | Why |
|---|---|---|
| `backend/migrations/versions/0019_day_close.py` | CREATE | One open drawer per staff member and property; payments by drawer; payments by date |
| `backend/app/services/cash_drawers.py` | CREATE | Open, current-or-open, paid-out, count and close, shift totals |
| `backend/app/services/day_close.py`, `day_summary.py`, `day_checks.py` | CREATE | Checklist, summary, close, reopen, closed-day lock |
| `backend/app/services/booking_payments.py`, `booking_refunds.py` | UPDATE | Link to the drawer; refuse closed days |
| `backend/app/schemas/end_of_day.py`, `routers/end_of_day.py`, `routers/cash_drawers.py`, `app/main.py` | CREATE / UPDATE | `/api/end-of-day/...`, `/api/cash-drawers/...` |
| `backend/app/services/front_desk_reads.py`, `schemas/front_desk.py` | UPDATE | "Yesterday not closed" for the banner |
| `backend/docs/rbac-spec.yaml` | UPDATE | `endofday:view`, `endofday:edit`, menu entry |
| `backend/tests/pg/test_cash_drawers.py`, `test_day_close.py`, `test_day_summary.py` | CREATE | See Tasks |
| `frontend/app/(authenticated)/end-of-day/page.tsx`, `components/end-of-day/*`, `components/cash-drawer/*`, `lib/end-of-day-api.ts`, `lib/end-of-day-format.ts` + test | CREATE | Page, drawer dialog, helpers |
| `frontend/app/(authenticated)/front-desk/page.tsx`, `middleware.ts`, `lib/i18n.ts` | UPDATE | Drawer button, banner, route, `id` + `en` text |
| `components-be.yaml`, `components-fe.yaml`, the PRD | UPDATE | Registers and milestone status |

## Tasks

Each backend task is test-first. Work on `feat/phase-2-m6-end-of-day`, branched from `feat/phase-2-m5-apoa`.

### Task 1: Cash drawers
- **Action**: Open with a float; desk payments and refunds go to the open drawer (one opens with zero float if none); paid-outs with a reason; count and close with a note when there is a difference; totals by method. Tests: expected cash adds up with payments, refunds and paid-outs; one open drawer per person; only your own drawer; removed payments drop out; paid-outs never appear on a booking or in the channel report.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_cash_drawers.py tests/pg/test_bills.py -q`

### Task 2: Summary and checklist
- **Action**: The day's figures (D4) and blocking and warning items (D2) for any past date. Tests: occupancy, ADR and RevPAR against a hand-worked example; money by method including online; deposits for future stays; each blocking item appears and clears.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_day_summary.py -q`

### Task 3: Close, lock and reopen
- **Action**: Close past days in order (refuse today, refuse a later day while an earlier one is open, unless the earlier days had no activity and are closed together), override with a reason and `bookings:edit`, snapshot, lock (refuse back-dated payments and refunds, and removing payments of a closed day), reopen with a reason. Tests: each refusal, the override permission, reopen then close again replaces the snapshot, history entries, tenant separation.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_day_close.py tests/pg/test_booking_payments.py tests/pg/test_booking_refunds.py -q`

### Task 4: Frontend
- **Action**: End-of-day page with date, checklist (blocking in red, warnings in amber, links to fix), summary, drawers and the close button with override; drawer dialog on the front desk (open, paid-out, count and close); "yesterday not closed" banner; both languages; phone width.
- **Validate**: `npx vitest run && npx tsc --noEmit && npm run lint`

### Task 5: Run, browser test, review
- **Action**: Full suites, migration up/down/up. Browser at phone width: open a drawer, take cash and card payments, a paid-out, count with a difference and a note, close yesterday with a blocking item (override), try a back-dated payment, reopen, both languages, `devtest.sh errors`. Code, security and database review; fix critical and high findings. Update registers and mark the milestone complete. A backend restart is needed to see the new menu entry.

## Validation

```bash
cd backend
uv run ruff check <changed files>
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
| Closing blocks a busy front desk | Medium | Close the previous day, any time today; blocking items have a permitted override with a reason |
| Staff need to correct a closed day | Medium | Record it today (payments, corrections), or reopen with a reason; both are in the history |
| Paid-outs leak into booking or channel figures | Medium | Paid-outs have no booking; tests check bookings, bills and the channel report |
| Drawers opened automatically with zero float hide a real float | Low | The screen says so; the float can be set before the first payment |
| Figures differ from the channel report | Medium | Same room-revenue rule as the channel report, tested together |
| A night shift crosses midnight | Medium | A drawer belongs to the day it opened; the checklist names drawers still open from that day |

## Acceptance

- [x] An operator sees what blocks closing a day, fixes or overrides it with a reason, and closes it
- [x] The day's summary (occupancy, ADR, RevPAR, revenue, money by method, cash book) is frozen at close
- [x] Staff open, use and count a cash drawer; differences need a note; paid-outs are recorded
- [x] A closed day's money cannot be changed by back-dating; reopening is permitted and logged
- [x] The front desk shows when yesterday is not closed
- [x] Access needs `endofday:view` or `endofday:edit` (drawers: `bills:edit`); tenants stay separate
- [x] Both languages and phone width work
- [x] All tasks complete, validation passes, coverage at least 80%
- [x] Patterns mirrored, not reinvented

## Changes during build and review

- **Cash movements table.** The payment table requires every outgoing row to point at the payment it refunds, so refunds and paid-outs go into a new immutable table `cashmovement` (migration 0019). Refunds now say how the money went back (bank transfer, cash or other); cash comes out of today's drawer, whatever date the refund is for.
- **Reopening.** The original schema made a closed day permanent. A closed day can now be neither deleted nor rewritten; only the reopen action, which names the row in its own transaction, may open it, with a reason. The old figures are kept in the history.
- **Drawers.** Only cash opens a drawer by itself; card, QRIS and transfers are noted on an open drawer. A drawer from an earlier day must be counted and closed before it takes more cash. A payment in a counted drawer cannot be removed. Closed drawers cannot be changed in the database.
- **Which days.** The first close starts at the property's first day (at most 92 days); days before it cannot be closed. A day can be closed from 00:05 the next morning, so late online payments have arrived.
- **Not in the summary:** service charge and PBJT; they come with the monthly tax export (Milestone 8).
- **Known limits:** rooms available is today's count of sellable rooms (frozen at close); no cap on floats or paid-outs.
