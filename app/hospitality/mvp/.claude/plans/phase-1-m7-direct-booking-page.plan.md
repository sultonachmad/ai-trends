# Plan: Direct booking page (Phase 1, Milestone 7)

**Source PRD**: `.claude/prds/phase-1-channel-manager-booking-engine.prd.md`
**Selected Milestone**: 7 — Direct booking page
**Complexity**: Large (the largest milestone in Phase 1)

## Summary

Each property gets a public page where a guest picks dates and guests, sees available
rooms with the all-in price and terms, enters a name and WhatsApp number, and pays a
deposit or the full amount through the existing Phase 0 payment page. The room is held
while payment is awaited. Once paid, the booking is confirmed, the guest gets a WhatsApp
message with a private link to view or cancel it, and the booking and conversation appear
for staff.

## What already exists, and the gaps

| Need | Today | Gap this milestone closes |
|---|---|---|
| Availability and price | `calendar.stay_nights`, `booking_stays.check_stay`, `taken_by_night` | A public, read-only search over them |
| Creating a booking | `bookings.book` (`backend/app/services/bookings.py:208`) always creates `confirmed` | A held (`tentative`) booking that takes units and later confirms or lapses |
| Booking status | The model allows `tentative` and `option_expires_at`, but reads, tabs and schemas know only `confirmed` / `cancelled` | Every read must handle held bookings |
| Payment page | `/pay/[token]`, QRIS, VA, transfer proof | Reused unchanged for the guest |
| "Paid" | Set separately in `gateway_events.py:96` and `proof_review.py:111`; neither touches a booking | One shared step that confirms the linked booking |
| Link limit | `link_quota.py:104` counts every link | Direct-booking deposits must not count (PRD decision) |
| WhatsApp | `send_text` only; free text is refused outside the 24-hour window (`inbox.py:60`) | **A first message to a new guest needs an approved template** |
| Public address | `tenantdomain` is for real hostnames | A short unique page name, resolved without sign-in |
| Choosing what is sold | `rateplan.is_public` exists, unused | A per-plan switch |
| Terms | Snapshot per booking; `guestconsent` table | Versioned acceptance stored with the booking |
| Abuse protection | No rate limiter installed | Anyone could hold every room without paying (D5) |

## Decisions (recommendation first; reply "yes" to accept all)

| # | Question | Recommendation |
|---|---|---|
| D1 | Page address | `/book/<short-name>`, chosen by the owner, unique across the product. The page is off until the owner publishes it |
| D2 | What is sold | Rate plans marked "Sell on booking page". A room type with no such plan does not appear |
| D3 | How a booking is held | A `tentative` booking takes the units at once and shows in the staff list as "Awaiting payment". It reaches channels like any other booking. 60 minutes for QRIS/VA, extended to 24 hours from a transfer screenshot upload |
| D4 | Deposit or full | The guest chooses. The deposit uses the property's percentage (default 50%). The balance is paid at the property; staff can still send a normal payment link for it |
| D5 | Stopping fake holds | At most 2 unpaid holds per WhatsApp number, 3 per visitor address, and 5 per property at a time (all configurable). When reached, the guest is told to message the property on WhatsApp. No CAPTCHA in this milestone |
| D6 | Payment arrives after the hold lapsed | If the room is still free, confirm the booking. If it is gone, do **not** overbook: keep it cancelled and flag the payment for a staff refund |
| D7 | Confirmation message | Send through a new template path in the messaging provider. The simulator accepts it now. **A real WhatsApp provider needs this template approved before the pilot.** A failed send never undoes the booking: staff see "confirmation not sent" |
| D8 | Inbox | Reuse or create the guest's conversation and store the confirmation there, so staff can carry on from it |
| D9 | Guest's private link | View the booking and cancel it, with a one-time token stored only as a hash. No self-service date changes (PRD) |
| D10 | Guest cancels | Within the free period: cancelled and flagged "refund due" for staff. Non-refundable: the page says plainly nothing is returned before they confirm. Refunds stay manual (PRD) |
| D11 | Price changed during checkout | The page sends the price it showed. If it differs, nothing is booked and the guest sees the new price to re-confirm (BR-BE-01) |
| D12 | Double submission | An idempotency key per checkout attempt, using the existing `idempotencyrecord` table (BR-BE-02) |
| D13 | Permissions | New `booking_page:view` / `booking_page:edit`, included in the manager role. Setup is a section on the Settings page, so no new menu entry. Guest pages are public |

## Patterns to Mirror

| Category | Source | Pattern |
|---|---|---|
| Public token scope | `backend/app/tenancy/public.py:40` | Shape check, fingerprint, `SECURITY DEFINER` resolver, then a tenant-bound session; same 404 for every bad token |
| Booking creation | `backend/app/services/bookings.py:208` | Property lock, `check_stay`, `_take`, lines, channel queue in one transaction |
| Payment lock order | `backend/app/services/gateway_events.py:96` | Link first, then payments |
| Link quota | `backend/app/services/link_quota.py:104` | Count in one place |
| Message delivery | `backend/app/services/inbox.py:282` | Store first, then call the provider; a failure is recorded |
| Background loop | `backend/app/services/calendar_link_sync.py` | Tenants from the control plane, per-tenant session, failures isolated |
| Errors | `backend/app/routers/checkout.py:31` | Named service errors mapped to HTTP answers |
| Tests | `backend/tests/pg/test_calendar_links.py`, `test_feature_access.py` | HTTP client, services driven directly, permission and isolation cases |
| Guest page | `frontend/app/pay/[token]/page.tsx` | Public page, Indonesian first with an English switch, phone-first |

## Files to Change

| File | Action | Why |
|---|---|---|
| `backend/migrations/versions/0013_direct_booking.py` | CREATE | `bookingpage` table and resolver; `paymentlink.origin`; manage-token hash on `reservation`; indexes for holds |
| `backend/app/models/control_plane/booking_page.py`, `.ttest/contexts/*.sql` | CREATE / UPDATE | Model, DTOs, design SQL |
| `backend/app/tenancy/business_settings.py`, `public_booking.py` | UPDATE / CREATE | Hold and abuse limits; public scope by page name and manage token |
| `backend/app/services/booking_page.py` | CREATE | Owner setup: name, publish, plans sold |
| `backend/app/services/booking_search.py` | CREATE | Public availability and all-in prices |
| `backend/app/services/booking_holds.py` | CREATE | Create, confirm, extend and lapse holds; background loop |
| `backend/app/services/direct_checkout.py` | CREATE | Checkout: limits, price check, idempotency, hold + payment link |
| `backend/app/services/booking_confirmation.py` | CREATE | WhatsApp confirmation, conversation, retry state |
| `backend/app/services/guest_booking.py` | CREATE | View and cancel by private link |
| `backend/app/services/{bookings,booking_reads,gateway_events,proof_review,transfer_proofs,link_quota}.py` | UPDATE | Held status; shared "paid" step; hold extension; quota exclusion |
| `backend/app/messaging/{provider,simulator}.py` | UPDATE | `send_template` |
| `backend/app/routers/booking_page.py`, `public_booking.py`, `schemas/booking_page.py`, `main.py` | CREATE / UPDATE | Staff and public routes; start the hold loop |
| `backend/docs/rbac-spec.yaml` | UPDATE | Document the new permissions |
| `backend/tests/pg/test_booking_{page,search,holds,checkout,confirmation,guest}.py` | CREATE | See Tasks |
| `frontend/app/book/[slug]/page.tsx`, `frontend/app/booking/[token]/page.tsx` | CREATE | Public booking and manage pages |
| `frontend/components/booking-page/*` | CREATE | Search, results, guest form, terms, confirmation |
| `frontend/components/settings/BookingPageSection.tsx`, settings page | CREATE / UPDATE | Owner setup and shareable pre-filled links |
| `frontend/components/bookings/*`, `app/pay/[token]/page.tsx` | UPDATE | "Awaiting payment", "refund due", "confirmation not sent"; a way back after paying |
| `frontend/lib/{booking-page-api,booking-page-format}.ts` + test, `lib/i18n.ts` | CREATE / UPDATE | API, pure helpers, `id` + `en` text |
| `components-be.yaml`, `components-fe.yaml`, the PRD | UPDATE | Registers and milestone status |

## Tasks

Each backend task is test-first. Tasks 1 to 3 change existing payment and booking paths, so the existing suites run after each.

### Task 1: Schema and held bookings
- **Action**: Migration, models, settings. `tentative` handled in every booking read, tab, schema and action. Held units count everywhere; staff cannot edit a hold or take a payment on it, but can cancel it.
- **Validate**: `uv run alembic upgrade head && uv run alembic check && REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_booking_holds.py tests/pg/test_bookings.py -q`

### Task 2: One "paid" step
- **Action**: Gateway events and proof approval both call one function that records the amount and confirms the linked booking under D6. Screenshot upload extends the hold. Lapse loop releases units and reaches channels. Deposit links do not count toward the limit.
- **Mirror**: `gateway_events.py` lock order.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_booking_holds.py tests/pg/test_payment_links.py tests/pg/test_proof_isolation.py -q`

### Task 3: Page setup and public search
- **Action**: Name, publish, plans sold, reserved names. Search honours closed dates, minimum stay, guests, blocks and holds, and leaks no unit counts beyond what is needed.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_booking_page.py tests/pg/test_booking_search.py -q`

### Task 4: Checkout
- **Action**: Validation, consent with versioned terms, price check, limits, idempotency, hold and payment link in one flow. Tests include two guests racing for the last unit.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_booking_checkout.py -q`

### Task 5: WhatsApp confirmation and guest link
- **Action**: Template send, conversation, failure state, view and cancel by private link, refund-due flag.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_booking_confirmation.py tests/pg/test_booking_guest.py -q`

### Task 6: Frontend
- **Action**: Booking page, pre-filled links, manage page, owner setup, staff states. Helpers tested first. Both languages, phone-first, keyboard and screen-reader basics (FR-BE-050).
- **Validate**: `npx vitest run && npx tsc --noEmit && npm run lint`

### Task 7: Run, browser test, review
- **Action**: Full suites, `alembic check`, migration up/down/up. Browser: publish a page; as a signed-out guest on a phone, search, book and pay by QRIS and by transfer; see the booking confirmed, the WhatsApp message in the inbox and the private link working; let a hold lapse; hit the hold limit; change a price mid-checkout; cancel as the guest; check a member without permission. `devtest.sh errors` clean. Code and security review; fix critical and high findings. Update registers and mark the milestone complete.

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
| A guest pays and the booking is not confirmed | Medium | One shared "paid" step in the payment transaction; retried events stay idempotent; tested for both payment routes |
| Changing the payment paths breaks Phase 0 | Medium | Links without a booking behave exactly as today; existing suites run after Tasks 1 and 2 |
| Fake bookings hold all rooms | High | Limits in D5, short holds. Limits can be evaded by a determined attacker; a CAPTCHA or edge rate limit is needed before wide public launch |
| Visitor address is wrong behind a proxy | Medium | Forwarded headers trusted only from a configured proxy; the phone and property limits still apply |
| WhatsApp template not approved by pilot time | High | **Start approval early.** Until then the page still shows the confirmation and staff see it was not sent |
| Payment lands just after a hold lapses | Medium | D6 under the property lock; never overbooks silently |
| Deposit is outside the payment-link amount limits | Low | Same min/max applied at checkout, with a clear message to contact the property |
| Personal data on a public page | Medium | Manage page shows only what the guest entered, masked phone; `no-store`; tokens out of access logs |
| Scope creep into PMS or promo features | Medium | PRD out-of-scope list holds |

## Acceptance

- [ ] A signed-out guest can pick dates, see the all-in price and terms, book and pay a deposit or in full on a phone
- [ ] The page opens in Bahasa Indonesia with an English switch, and a link can pre-fill dates and room type
- [ ] The room is held while payment is awaited and released on time
- [ ] Payment confirms the booking; WhatsApp confirmation and the conversation appear; the booking is in the staff list
- [ ] The guest can view and cancel by private link
- [ ] Direct deposits do not count toward the 30 monthly payment links
- [ ] A payment never silently overbooks, and no paid booking is lost
- [ ] Hold limits, price re-confirmation and duplicate submission protection work
- [ ] Routes respect permissions; tenants stay separate
- [ ] All tasks complete, validation passes, coverage at least 80%
- [ ] Patterns mirrored, not reinvented
