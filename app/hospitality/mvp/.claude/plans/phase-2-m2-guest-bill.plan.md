# Plan: Guest bill (Phase 2, Milestone 2)

**Source PRD**: `.claude/prds/phase-2-pms-core.prd.md`
**Selected Milestone**: 2 — Guest bill
**Complexity**: Large

## Summary

Every booking gets one bill. It shows the room nights, the extras the guest used, discounts and corrections, and every payment from any source, ending in one balance. Staff add charges and take payments at the desk. Check-out is blocked while money is owed unless a permitted person lets the guest leave unpaid with a reason, and a numbered receipt is issued at check-out. First this milestone fixes channel-collected bookings, which today show the full room price as owed.

## What already exists, and the gaps

| Need | Today | Gap this milestone closes |
|---|---|---|
| Room charges | `reservationdailyrate` per night, booking `total_amount` | Shown on the bill as they are; not copied |
| Extras, discounts, corrections | `folio`, `foliotransaction` (kinds charge, adjustment, void; never deleted), `transactioncode` (codes already unique) | **All unused.** No bill, no charge codes. No migration is expected |
| Payments | `payment` rows by booking: staff entries, payment links, transfer proofs | Staff methods are only cash, bank transfer and other. The table already allows `card` and `qris` |
| Balance | `reservation.balance_due = total − paid`, written in 4 places | Extras are not counted, and payment state is worked out from the room total only |
| **Channel collection** | `reservation.payment_collect_model` = `property`, `channel` or `mixed` | **Ignored.** A booking the channel was paid for shows its whole price as owed, so a check-out block would stop guests who already paid |
| Receipt | `invoice` (kind `receipt`), `invoiceline`, `documentsequence`, a `legalentity` per tenant from onboarding | All unused. No numbering service |
| Check-out | Milestone 1 warns about a balance only | No block, no permitted override |

## Decisions (recommendation first; reply "yes" to accept all)

| # | Question | Recommendation |
|---|---|---|
| D1 | What is on the bill? | One bill per booking: **room nights** from the booking's prices, **extras** and **discounts** posted on the bill, and **payments** from every source. Room prices are still changed only by editing the booking |
| D2 | Channel-collected bookings | When the channel was paid (`channel`), the room nights show as **"Paid to channel"**, and the guest owes only extras. `mixed` and `property` mean the guest pays the property. Payment state follows the balance, so these bookings show as paid |
| D3 | Extras | Fixed categories: Extra bed, Food & drinks, Laundry, Transport, Minibar, Late check-out, Other. Each has a description, quantity and unit price. Property-defined categories wait |
| D4 | Discounts and corrections | Nothing is deleted. A line can be **voided the same day** with a reason. Later mistakes get a **correction** line with a reason. A **discount** is a negative line with a reason. All are in the history |
| D5 | Payments at the desk | Cash, bank transfer, card (EDC terminal), QRIS (printed code) and other. Online payments and verified transfer proofs appear automatically. No card numbers are stored |
| D6 | Check-out with money owed | **Blocked.** Someone with `bookings:edit` can let the guest leave unpaid with a reason; the booking is then flagged "left unpaid". Overpayment flags a refund, as in Milestone 1 |
| D7 | Receipt | A numbered receipt per legal entity (`KW-2026-000123`) is issued **automatically at check-out**, frozen and printable in Bahasa Indonesia or English. Before check-out staff can print an **unnumbered bill**. Tax lines join in Milestone 3 |
| D8 | After check-out | The bill is closed to new charges. Refunds can still be recorded. Late charges and reopening wait |
| D9 | Permissions and place | New `bills:view` and `bills:edit`, in the manager role. The bill opens from the front desk and from a booking; there is no new menu entry |
| D10 | Deposits | Payments before arrival show on the bill as deposits. Deposit liability accounting waits for end of day (Milestone 6) |

## Patterns to Mirror

| Category | Source | Pattern |
|---|---|---|
| Money entries | `backend/app/services/booking_payments.py:45` (`_recompute`), `:56` | Lock property, then booking; recompute after each change |
| Numbering | `backend/app/services/booking_numbers.py` | Generated number with retry under a lock |
| Refusals | `backend/app/services/front_desk_errors.py` | Stable `code` the page translates |
| Permission inside a route | `backend/app/routers/front_desk.py` (`check_out`) | Second permission checked for one option |
| History | `backend/app/services/tenant_audit.py:50` | `record` inside the transaction |
| Tests | `backend/tests/pg/test_front_desk.py`, `test_booking_refunds.py` | HTTP client, permission and isolation cases |
| Frontend | `frontend/components/front-desk/*`, `components/bookings/BookingDetailDialog.tsx`, `lib/booking-forms.ts` | Dialogs, tested helpers, text in `lib/i18n.ts` |

## Files to Change

| File | Action | Why |
|---|---|---|
| `backend/app/services/bill_balance.py` | CREATE | One way to work out what is owed (D1, D2), used by every writer |
| `backend/app/services/booking_payments.py`, `bookings.py`, `front_desk.py`, `booking_reads.py`, `front_desk_reads.py` | UPDATE | Use it instead of `total − paid` |
| `backend/app/services/bills.py` | CREATE | Bill, charges, discounts, voids, corrections, desk payments |
| `backend/app/services/receipts.py` | CREATE | Numbering and frozen receipts |
| `backend/app/services/front_desk.py` | UPDATE | Check-out block, leave-unpaid override, receipt at check-out |
| `backend/app/schemas/bills.py`, `backend/app/routers/bills.py`, `app/main.py` | CREATE / UPDATE | `/api/bills/{booking_id}`, charges, payments, receipt |
| `backend/docs/rbac-spec.yaml` | UPDATE | `bills:view`, `bills:edit` |
| `backend/tests/pg/test_bill_balance.py`, `test_bills.py`, `test_receipts.py` | CREATE | See Tasks |
| `frontend/components/bills/*`, `frontend/app/(authenticated)/bills/[id]/receipt/page.tsx` | CREATE | Bill dialog, charge and payment forms, print view |
| `frontend/lib/bills-api.ts`, `bill-format.ts` + test | CREATE | API and pure helpers |
| `frontend/components/front-desk/*`, `components/bookings/BookingDetailDialog.tsx`, `lib/i18n.ts`, `middleware.ts` | UPDATE | Open the bill, check-out block and override, `id` + `en` text |
| `components-be.yaml`, `components-fe.yaml`, the PRD | UPDATE | Registers and milestone status |

## Tasks

Each backend task is test-first. Work on `feat/phase-2-m2-guest-bill`, branched from `feat/phase-2-m1-front-desk`.

### Task 1: What is owed
- **Action**: One balance rule for room nights, channel collection, extras and payments. Replace the four `total − paid` writers and work payment state out from the balance. Tests: channel-collected bookings owe nothing for the room; `mixed` bookings owe it; extras and discounts count; balances stay right after edits, early departure, payments, removed payments and online payments.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_bill_balance.py tests/pg/test_bookings.py tests/pg/test_front_desk.py tests/pg/test_direct_booking.py -q`

### Task 2: The bill
- **Action**: Read the bill; post charges and discounts; void the same day; correct later; take desk payments with the new methods. Tests: quantity × price, reasons required, voids only the same day and only once, corrections, closed bills after check-out, cancelled and no-show bookings read-only, permissions, tenant separation, double clicks.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_bills.py -q`

### Task 3: Check-out and receipt
- **Action**: Block check-out while money is owed; the permitted override with a reason; receipt numbered per legal entity, issued once at check-out and frozen; unnumbered bill before. Tests: numbering never repeats or skips under two check-outs at once; the receipt does not change when the booking is later edited; undo check-out keeps the issued receipt and the next check-out issues a new one; the override needs `bookings:edit`.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_receipts.py tests/pg/test_front_desk.py tests/pg/test_feature_access.py -q`

### Task 4: Frontend
- **Action**: Bill dialog from the front desk and booking detail, charge, discount, void, correction and payment forms, the check-out block with the override, and the print page. Large touch targets, read-only without `bills:edit`.
- **Validate**: `npx vitest run && npx tsc --noEmit && npm run lint`

### Task 5: Run, browser test, review
- **Action**: Full suites, migration up/down/up on an empty database, `devtest.sh restart`. Browser: a direct booking with a deposit, extras, a discount, a void, a card payment, blocked check-out, payment, check-out and receipt print; a channel-collected booking checks out with only extras owed; the override by a permitted user; both languages; phone width; `devtest.sh errors`. Code, security and database review; fix critical and high findings. Update registers and mark the milestone complete.

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
| Balance differs between pages because one writer was missed | High | One balance rule (Task 1); every writer found and tested |
| Channel collection model is wrong for a channel | Medium | Shown plainly on the bill as "Paid to channel"; staff can still post and collect extras |
| Receipt numbers repeat or skip | Medium | Number taken under a row lock on the sequence, in the check-out transaction; tested with parallel check-outs |
| Staff use discounts to hide cash | Medium | Reason required, named in the history, visible on the bill; Milestone 6 adds shift totals |
| Guests leave unpaid through the override | Medium | Needs `bookings:edit` and a reason; flagged on the booking |
| A receipt is not a tax invoice | Medium | Labelled "Receipt"; tax lines and invoices come with Milestone 3 |

## Acceptance

- [ ] Every booking shows one bill with room nights, extras, discounts, payments and one balance
- [ ] Channel-collected bookings owe only extras
- [ ] Staff post charges, discounts, same-day voids and corrections with reasons; nothing is deleted
- [ ] Desk payments by cash, transfer, card and QRIS; online payments appear automatically
- [ ] Check-out is blocked while money is owed, except through the permitted override
- [ ] A numbered, frozen receipt is issued at check-out and can be printed
- [ ] Routes need `bills:view` or `bills:edit`; tenants stay separate
- [ ] Both languages and phone width work
- [ ] All tasks complete, validation passes, coverage at least 80%
- [ ] Patterns mirrored, not reinvented
