# Plan: Channel report (Phase 1, Milestone 8)

**Source PRD**: `.claude/prds/phase-1-channel-manager-booking-engine.prd.md`
**Selected Milestone**: 8 — Channel report
**Complexity**: Medium

## Summary

An operator picks a period and sees, per booking source including direct, the bookings,
nights, revenue, commission and net revenue, with totals. This milestone also closes three
gaps from earlier work: staff cannot mark a refund as done, one refund flag is not shown on
the payment links page, and the feature menus do not follow the project's RBAC menu rule.

## What already exists, and the gaps

| Need | Today | Gap this milestone closes |
|---|---|---|
| Revenue per night | `reservationdailyrate.amount` | No index for reading by date (added in migration `0014`) |
| Source of each booking | `reservation.channel_id`, `channel.is_direct` | None |
| Commission | `reservation.commission_amount`, set on channel bookings | Must be spread over nights for a period that cuts a stay |
| Summary table | `channelperformancedaily` exists, unused | Not used: the report is computed live, so it cannot go stale |
| Charts | No chart package is installed | Simple share bars with CSS; no new package |
| Refund flag | `source_detail.refund_due` | Staff cannot clear it |
| Refund review on links | `payment_links.py:48` uses `needs_refund_review` | **`booking_holds.py:47` writes a different key, `needs_refund`, so the payment links page misses those flags** |
| Menu | 8 feature entries are top-level | **`CLAUDE.md` requires permission-gated pages to be children of a business-area group. This was missed in the RBAC correction** |

## Decisions (recommendation first; reply "yes" to accept all)

| # | Question | Recommendation |
|---|---|---|
| D1 | Which date places a booking in a period? | **The night stayed.** A stay crossing two months is split between them, so monthly revenue adds up correctly |
| D2 | What counts as revenue? | Confirmed bookings only. Unpaid holds and cancelled bookings are excluded, including money kept from non-refundable cancellations, which the page states plainly |
| D3 | Columns | Bookings, nights, revenue, average per night, cancellation rate, commission, net revenue. Lead time and cost per booking wait until asked for |
| D4 | Commission | The amount stored on each booking, spread evenly by its nightly revenue. Direct sources are zero. Changing a channel's rate does not rewrite past bookings |
| D5 | Rows | One row per source, highest revenue first, with a "Direct" subtotal, a "Channels" subtotal and a grand total |
| D6 | Period | This month, last month, last 30 days or custom, up to 366 days, in the property's time zone |
| D7 | Permission and menu | New `reports:view`, included in the manager role, because revenue is sensitive. Page at `/reports` under a "Reports" group |
| D8 | Marking a refund done | A "Mark refund as done" action under `bookings:edit`, recording amount, date, note and who did it in the history. It clears the flag. Money is still sent outside the product |
| **D9** | **Fix the menu now?** | **Yes.** Group the existing pages: *Guests* (Inbox), *Payments* (Payment links, Transfer proofs), *Reservations* (Bookings, Calendar), *Distribution* (Rooms & rates, Channels), *Reports*, *Property* (Settings). Dashboard stays top-level because it has no permission. Page addresses do not change. **The backend must restart to show it** |

## Patterns to Mirror

| Category | Source | Pattern |
|---|---|---|
| Date window | `backend/app/services/calendar_dates.py:87` | `check_read_window` refuses reversed or oversized ranges |
| Tenant reads | `backend/app/services/booking_reads.py` | Every query filters `tenant_id`; session is tenant-scoped |
| Routes and permissions | `backend/app/routers/channels.py:44` | `require_permission` constant, thin router, named errors |
| History | `backend/app/services/tenant_audit.py:50` | `record` inside the transaction |
| Booking locks | `backend/app/services/bookings.py` | `lock_property`, then `get_for_update` |
| Tests | `backend/tests/pg/test_direct_booking.py`, `test_feature_access.py` | HTTP client, permission and isolation cases |
| Frontend | `frontend/app/(authenticated)/channels/page.tsx`, `lib/channel-format.ts` | Page state, pure helpers tested first, text in `lib/i18n.ts` |

## Files to Change

| File | Action | Why |
|---|---|---|
| `backend/migrations/versions/0014_report_index.py` | CREATE | Index on `reservationdailyrate (tenant_id, stay_date)` |
| `backend/app/models/tenant/reservations/reservation_daily_rate.py`, `.ttest/contexts/schema-tenant.sql` | UPDATE | Index in model and design SQL |
| `backend/app/services/channel_report.py` | CREATE | The report |
| `backend/app/schemas/reports.py`, `backend/app/routers/reports.py`, `app/main.py` | CREATE / UPDATE | `GET /api/reports/channels?from=&to=` |
| `backend/app/services/booking_refunds.py`, `routers/bookings.py`, `schemas/bookings.py` | CREATE / UPDATE | Mark a refund as done |
| `backend/app/services/booking_holds.py`, `gateway_events.py` | UPDATE | One shared refund flag; a refund outcome is always flagged |
| `backend/docs/rbac-spec.yaml` | UPDATE | `reports:view`, business-area menu groups |
| `backend/tests/pg/test_channel_report.py`, `test_booking_refunds.py` | CREATE | See Tasks |
| `frontend/app/(authenticated)/reports/page.tsx`, `components/reports/*`, `middleware.ts` | CREATE / UPDATE | Report page, protected route |
| `frontend/lib/{reports-api,report-format}.ts` + test | CREATE | API and pure helpers |
| `frontend/components/bookings/BookingDetailDialog.tsx`, `lib/bookings-api.ts`, `lib/i18n.ts` | UPDATE | Refund action, `id` + `en` text |
| `components-be.yaml`, `components-fe.yaml`, the PRD | UPDATE | Registers and milestone status |

## Tasks

Each backend task is test-first.

### Task 1: Report calculation
- **Action**: Migration, then `channel_report`. Tests: a stay crossing the period edge is split; holds and cancelled bookings are excluded; commission is spread correctly and rows add up to the totals to the rupiah; every source appears, including direct; empty period; tenant separation.
- **Validate**: `uv run alembic upgrade head && uv run alembic check && REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_channel_report.py -q`

### Task 2: Route and permission
- **Action**: Endpoint, validation, `reports:view`. Tests for 403, invalid and oversized ranges.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_channel_report.py tests/pg/test_feature_access.py -q`

### Task 3: Refund flags
- **Action**: Use one refund flag constant, always flag a refund outcome, add "mark refund as done" with history. Tests: the flag reaches the payment links page; marking done clears it once; it needs `bookings:edit`; a booking without a refund due is refused.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_booking_refunds.py tests/pg/test_direct_booking.py -q`

### Task 4: Frontend and menu
- **Action**: Report page with period choices, table on desktop, cards on phone, share bars, plain notes on what is counted. Refund action in the booking detail. Menu groups in `rbac-spec.yaml`.
- **Validate**: `npx vitest run && npx tsc --noEmit && npm run lint`

### Task 5: Run, browser test, review
- **Action**: Full suites and migration up/down/up. `devtest.sh restart` for the menu. Browser: make direct and channel bookings, compare the report by hand, change the period, check grouped menus for an owner and a narrow role, mark a refund done, both languages, phone width, `devtest.sh errors`. Code and security review; fix critical and high findings. Update registers and mark the milestone complete.

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
| Rounding makes rows and totals disagree | Medium | Compute in exact decimals, round once per booking, derive totals from the rounded rows; tested |
| Commission looks wrong after staff edit a channel booking's price | Medium | The stored commission is used and the page says so; reconciliation against invoices is out of scope (FR-CM-091) |
| Slow report on long periods | Low | New index, 366-day limit, a single grouped query |
| Menu change hides a page from a role | Low | Permissions are unchanged; tested with owner and narrow role |
| Operators read "revenue" as cash received | Medium | The page states it is the value of nights stayed, not money collected |

## Acceptance

- [ ] An operator can see bookings, nights, revenue, commission and net revenue by source for a chosen period
- [ ] Direct sources are included, and rows add up exactly to the totals
- [ ] A stay crossing the period edge counts only its nights inside the period
- [ ] Holds and cancelled bookings are excluded from revenue
- [ ] The report needs `reports:view`; tenants stay separate
- [ ] Staff can mark a refund as done, with history
- [ ] All refund flags appear on the payment links page
- [ ] Feature menus follow the RBAC placement rule
- [ ] Both languages and phone width work
- [ ] All tasks complete, validation passes, coverage at least 80%
- [ ] Patterns mirrored, not reinvented
