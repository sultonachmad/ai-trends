# Plan: Tax pack (Phase 2, Milestone 3)

**Source PRD**: `.claude/prds/phase-2-pms-core.prd.md`
**Selected Milestone**: 3 — Tax pack
**Complexity**: Large

## Summary

An owner sets their region's hotel tax (PBJT) and their service charge once, and chooses whether their prices already include them ("nett") or have them added on top ("++"). From then on every bill, receipt and online price shows service charge and PBJT as separate lines. In ++ mode the guest pays them on top. No tax is charged until the owner confirms the rate, because a wrong tax on a real bill is worse than none.

## What already exists, and the gaps

| Need | Today | Gap this milestone closes |
|---|---|---|
| Region | `property.region_code` (regency or city code) | Never set; no list of regions |
| Price mode | `property.price_display_mode` = `nett` or `plus_plus` | Never read |
| Tax rules | `taxrule` (PBJT hotel, service charge, percent, effective dates, compound order), `transactioncodetax` | **Unused.** No tax on any bill |
| Booking tax | `reservation.total_tax` | Always 0 |
| Bill and receipt | Milestone 2 bill, frozen receipts with `tax_total` and per-line `tax_amount` | No tax lines |
| Online price | Booking page and payment links charge the room total | In ++ mode the guest would pay too little |
| Channel bookings | The channel's amount is what the guest paid | Must never have tax added on top |

## Decisions (recommendation first; reply "yes" to accept all)

| # | Question | Recommendation |
|---|---|---|
| D1 | Starting state | **No tax until the owner confirms.** The Settings page asks for region, rates and price mode, and the owner ticks "I have checked these rates with my regional tax office (Bapenda)". Until then bills show no tax lines and a reminder appears |
| D2 | Regions | A starter list for Bali (Badung, Denpasar, Gianyar), Jakarta (its 5 cities), Yogyakarta (Kota Yogyakarta, Sleman), Bandung and Surabaya, each pre-filled with **PBJT 10%** and marked "check with Bapenda", plus "Other region". The law caps PBJT at 10%, so higher rates are refused. **These values are not verified** |
| D3 | Service charge | 0% by default (most villas and budget hotels charge none), up to 15%. PBJT is charged on room price plus service charge by default, with a switch, pending verification |
| D4 | Nett or ++ | **Nett** (prices include service and PBJT, as most small properties quote) is the default. **++** adds them on top of the price. Each booking keeps the mode it was made under, so switching modes never changes existing bookings |
| D5 | What is taxed | Room nights and extras. Each extra category has a "taxed" switch: all on except Transport. Discounts and corrections reduce the base of their category. Restaurant PBJT for outlets waits |
| D6 | Rate changes | Saving new rates creates rules **effective from a date** (today or later). Each night and extra is taxed by the rule of its own date, so past stays never change |
| D7 | Rounding | Per bill line and per tax, to whole rupiah, half up. In nett mode the tax is worked out backwards from the price, so lines always add up to the price exactly |
| D8 | Online prices in ++ mode | The booking page shows and charges the **final price including service and PBJT**, and deposits and payment links use it. Channel bookings are always treated as nett, because the channel's amount is what the guest paid |
| D9 | Receipt | Shows the base price, service charge and PBJT per line, with totals. It is still labelled "Receipt"; PBJT is a regional tax, not VAT, so no tax invoice (faktur pajak) is involved |
| D10 | Permission | Existing `settings:view` and `settings:edit`. Every change is in the history. The monthly tax summary export stays in Milestone 8 |

## Patterns to Mirror

| Category | Source | Pattern |
|---|---|---|
| Settings section | `backend/app/routers/settings.py` (`booking-terms`), `frontend/app/(authenticated)/settings/page.tsx` | GET and PUT per section, `settings:view` / `settings:edit` |
| Pure calculation | `backend/app/services/booking_pricing.py` (`spread_total`) | Pure functions on `Decimal`, unit-tested without a database |
| What is owed | `backend/app/services/bill_balance.py` | One rule, used by every writer |
| Effective dates | `taxrule.effective_from/to` | One active row per code and date |
| Frozen documents | `backend/app/services/receipts.py` | Snapshot into invoice lines at issue |
| Tests | `backend/tests/test_booking_pricing.py`, `tests/pg/test_bills.py`, `test_receipts.py` | Unit tests for maths, HTTP tests for flows |

## Files to Change

| File | Action | Why |
|---|---|---|
| `backend/app/services/tax_engine.py` | CREATE | Pure maths: split a line into base, service and PBJT for nett and ++ |
| `backend/app/services/tax_rules.py`, `tax_regions.py` | CREATE | Starter regions, read and save settings as dated rules, category switches |
| `backend/app/schemas/taxes.py`, `routers/settings.py` | CREATE / UPDATE | `GET/PUT /api/settings/taxes` |
| `backend/app/services/bill_balance.py`, `bill_reads.py`, `receipts.py` | UPDATE | Tax in what is owed (++), tax lines on the bill and receipt |
| `backend/app/services/bookings.py`, `channel_bookings.py`, `direct_checkout.py`, `booking_reads.py` | UPDATE | Mode kept on each booking; online price in ++ mode; channel bookings always nett |
| `backend/tests/test_tax_engine.py`, `tests/pg/test_tax_settings.py`, `test_bill_taxes.py` | CREATE | See Tasks |
| `frontend/components/settings/TaxSettings.tsx`, `lib/taxes-api.ts`, `lib/tax-format.ts` + test | CREATE | Settings section and helpers |
| `frontend/components/bills/*`, `app/book/**` price display, `lib/i18n.ts` | UPDATE | Tax lines, "price includes" notes, final prices online, `id` + `en` text |
| `components-be.yaml`, `components-fe.yaml`, the PRD | UPDATE | Registers and milestone status |

No migration is expected: the tables and columns exist.

## Tasks

Each backend task is test-first. Work on `feat/phase-2-m3-tax-pack`, branched from `feat/phase-2-m2-guest-bill`.

### Task 1: Tax maths
- **Action**: Split one amount into base, service and PBJT in nett and ++ modes, with service in or out of the PBJT base. Tests: 10% and 10% on Rp 500,000 in both modes, zero rates, rounding that always adds up, negative lines (discounts), large amounts.
- **Validate**: `uv run pytest tests/test_tax_engine.py -q`

### Task 2: Settings and dated rules
- **Action**: Starter regions, read and save with the confirmation tick, rates bounded (PBJT 0–10%, service 0–15%), new rules from a date with older ones ended the day before, category switches. Tests: no tax before confirmation, effective dates, history, permissions, tenant separation.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_tax_settings.py -q`

### Task 3: Bills, receipts and online prices
- **Action**: Tax lines per night and per extra by date; ++ adds to what is owed; nett shows what is included; receipts freeze it; bookings keep their mode; booking page, deposits and payment links use the final price in ++; channel bookings nett. Tests: a rate change mid-stay, a mode switch not touching old bookings, discounts lowering the tax, transport untaxed, receipt totals equal the bill, check-out block uses the taxed balance.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_bill_taxes.py tests/pg/test_bills.py tests/pg/test_receipts.py tests/pg/test_direct_booking.py tests/pg/test_channel_bookings.py -q`

### Task 4: Frontend
- **Action**: Settings section with region, rates, mode, effective date, category switches and the confirmation tick; tax lines on the bill and receipt; "includes service and tax" or "+ service and tax" next to prices; final prices on the booking page.
- **Validate**: `npx vitest run && npx tsc --noEmit && npm run lint`

### Task 5: Run, browser test, review
- **Action**: Full suites. Browser: set Badung at 10% + 10% service in ++ mode, make a direct booking online and check the charged amount, add extras, check out and read the receipt; switch to nett and confirm old bookings keep their totals; a channel booking stays nett; both languages; phone width; `devtest.sh errors`. Code, security and database review; fix critical and high findings. Update registers and mark the milestone complete.

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
| Starter rates or the PBJT base are wrong for a region | High | Nothing is charged until the owner confirms; starter values are labelled unverified; **verification against official sources is needed before the pilot** |
| ++ mode changes what guests pay online | High | Final price shown before payment; tested end to end; existing bookings keep their mode |
| Rounding makes lines and totals disagree | Medium | Round once per line and tax, derive totals from the rounded lines; tested |
| Channel bookings get tax added twice | Medium | Channel bookings always nett; tested |
| Owners read nett revenue in the channel report as excluding tax | Medium | Report note says room revenue is as priced; tax summary comes in Milestone 8 |

## Acceptance

- [ ] An owner sets region, rates and price mode, and nothing is taxed before they confirm
- [ ] Bills and receipts show service charge and PBJT as separate lines
- [ ] In ++ mode they are added to what is owed, online prices included; in nett mode they are shown as included
- [ ] Rate changes apply from their date; mode changes never touch existing bookings
- [ ] Channel bookings are never taxed on top
- [ ] Lines and totals add up exactly
- [ ] Both languages and phone width work
- [ ] All tasks complete, validation passes, coverage at least 80%
- [ ] Patterns mirrored, not reinvented
