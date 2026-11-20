# Plan: Phase 0 — Milestone 3: Payment Links

**Source PRD**: `.claude/prds/phase-0-whatsapp-wedge.prd.md`
**Selected Milestone**: 3 — Payment links
**Complexity**: Large

## Summary

Staff create a payment link for an IDR amount (optionally a down payment of a stated total) from a conversation or on its own; the link is sent into the WhatsApp thread. The guest opens a public page with no sign-in, sees the property, amount and expiry, picks QRIS or a bank virtual account and pays. Staff see each link turn paid, expire or be cancelled. The payment gateway is simulated behind a provider interface, the same way WhatsApp is.

This milestone needs one database migration (three new columns, a provider value, and a lookup function for the public page). No new packages.

## Decisions needed before coding

| # | Decision | Recommendation | Why it matters |
|---|---|---|---|
| D1 | How the QRIS code is shown | A clearly labelled simulated code box showing the payment reference text, not a scannable image | Drawing a real QR image needs a new package (project rules require your approval). A simulated gateway has nothing real to scan anyway; the real image comes with the real gateway |
| D2 | When a link becomes "expired" | Worked out whenever the link is read (page, list, payment attempt); no background job | The app has no scheduler. The guest and staff always see the correct state; the stored status is updated on the next read |
| D3 | Can staff see a link's address again later? | No: the address is shown once at creation (with a copy button) and is in the chat message. Staff can cancel a link and make a new one | The design stores only a fingerprint of the link token, so the full address cannot be rebuilt. Storing it readable would make every link usable by anyone who can read the database |
| D4 | Conversation is resolved or outside WhatsApp's 24-hour window | The link is still created; staff are told it could not be sent to the chat and copy the address themselves | Otherwise staff could not take a payment from a guest who last wrote yesterday |
| D5 | Free-plan limit (30 links per month) | Not enforced yet; enforcement stays in milestone 5 as the PRD lists it. The dashboard already counts links | Keeps this milestone to one outcome; say if you want it pulled forward |
| D6 | How a tester "pays" | A "Simulate payment" button on the public page, shown and accepted only when a setting is on (`PREFAB_PAYMENT_SIMULATOR_ENABLED`, off by default, on in local `.env`) | Plays the part of the guest's banking app. Off by default so it can never mark real links paid |
| D7 | Amount limits | Minimum Rp 10.000, maximum Rp 500.000.000, whole rupiah only; both limits configurable per property | Guards against typing errors (an extra zero) and against amounts gateways reject |
| D8 | Address used in links | New setting `PREFAB_FRONTEND_URL`; when unset, the first address in `PREFAB_CORS_ORIGINS` | The backend must write a full address into the chat message |

## Requirements restated

- Staff create a link: amount, description, expiry (default from the property setting, 24 hours), optional "total" making it a down payment, optional conversation.
- From a conversation, the link is sent as a chat message in Bahasa Indonesia with amount, description, expiry and address.
- The guest page needs no account and shows: property name, description, amount (and "DP of total" when set), expiry, current state. It offers QRIS and virtual account (BCA, Mandiri, BNI, BRI, Permata) and shows payment instructions for the chosen method.
- When the gateway reports the payment, the link becomes paid for staff and guest without a manual refresh. A repeated gateway notification changes nothing.
- A paid, expired or cancelled link accepts no further payment and says why.
- Staff see their property's links with state, amount, description, guest when known, and when each was paid; filter by state; paged. Staff can cancel a link that is still pending.
- A link token cannot be guessed, is never stored readable, and reveals nothing of another tenant.
- Nothing from another tenant is visible or reachable; the public page exposes no guest personal data.
- Staff screens and the guest page are in Bahasa Indonesia with an English switch (guest page: Bahasa by default, per guest).

## Patterns to Mirror

| Category | Source | Pattern |
|---|---|---|
| Naming | `backend/app/routers/inbox.py:1`, `backend/app/services/inbox.py:1`, `backend/app/schemas/inbox.py:1` | router / service / schema triple per feature |
| Provider interface | `backend/app/messaging/provider.py:1`, `backend/app/messaging/simulator.py:1` | Protocol + registry keyed by the account's `provider`; simulator registers itself |
| Account per property | `backend/app/services/messaging_accounts.py:45` | find-or-create with savepoint and `IntegrityError` re-read |
| Record first, then call provider | `backend/app/services/inbox.py:337` (`send_reply`) | Store, commit, call provider with no lock held, then update state; provider faults never lose the record |
| Idempotent inbound events | `backend/app/services/inbound.py:133` | One entry point; duplicate provider id changes nothing; row lock before reading state |
| Sending a chat message | `backend/app/services/inbox.py:337` | Reuse `send_reply`; its refusals (`resolved`, `window_closed`) are handled, not bypassed |
| Tenant access | `backend/app/tenancy/session.py:40` (`bind_tenant`), `:53` | Tenant-scoped session; explicit `tenant_id` filters as well |
| Errors | `backend/app/routers/inbox.py:36` (`_guarded`) | Named service exceptions mapped to HTTP answers with their own `detail` |
| Dev-only switch | `backend/app/routers/simulator.py:35` | Per-request dependency answering 404 when off; warning logged at startup when on |
| Configurable values | `backend/app/tenancy/business_settings.py:41` | New property-level values with defaults and bounds |
| Migration | `backend/migrations/versions/0004_app_role_and_free_plan.py:99` | Hand-written statements, one per `op.execute`; grants to `app_rw` |
| Tests (backend) | `backend/tests/pg/test_inbox.py`, `test_inbox_isolation.py`, `conftest.py` (`start_workspace`, `guest_says`) | One behaviour per test; second client for cross-tenant cases; scope-probe test |
| Frontend API / logic | `frontend/lib/inbox-api.ts`, `frontend/lib/inbox-format.ts` (+ test), `frontend/lib/use-polling.ts` | Typed calls; pure helpers with tests; timed re-fetch with stale-result guards |
| Frontend pages | `frontend/app/(authenticated)/inbox/page.tsx`, `frontend/components/inbox/*` | Small focused components; all text through `lib/i18n.ts`; semantic Tailwind classes |
| Dialogs | `frontend/components/Dialog.tsx:33` | Shared `Dialog` for the create-link form |
| Public pages | `CLAUDE.md` "Public pages"; `instructions/frontend.md` "Link Landing Pages" | Token in the path (`app/pay/[token]/page.tsx`), outside `(authenticated)/`, not listed in `PUBLIC_LINKS` (it is not a top-level page) |

No existing pattern covers an unauthenticated tenant lookup or money formatting; both are introduced here.

## Files to Change

| File | Action | Why |
|---|---|---|
| `backend/migrations/versions/0005_payment_links.py` | CREATE | `paymentlink.conversation_id`, `guest_id`, `deposit_of_total`; indexes; `simulator` as a gateway provider; token lookup function for the public page |
| `.ttest/contexts/schema-tenant.sql` | UPDATE | Keep the design schema in step with the migration |
| `backend/app/models/tenant/payments/payment_link.py`, `payment_gateway_account.py` | UPDATE | New columns and provider value |
| `backend/app/payments/__init__.py`, `gateway.py`, `simulator.py`, `tokens.py` | CREATE | Gateway protocol + registry, simulated gateway, link token generation and hashing |
| `backend/app/services/payment_links.py` | CREATE | Create, list, read, cancel, effective state, chat message |
| `backend/app/services/checkout.py` | CREATE | Public side: resolve token, start a payment, payment instructions |
| `backend/app/services/gateway_events.py` | CREATE | Single entry point for gateway notifications (idempotent) |
| `backend/app/services/gateway_accounts.py` | CREATE | Find or create the property's gateway account |
| `backend/app/services/onboarding.py` | UPDATE | New workspaces get a (simulated) gateway account |
| `backend/app/tenancy/public.py` | CREATE | Tenant-scoped session for the public page, from the link token |
| `backend/app/schemas/payment_links.py` | CREATE | Request and response shapes, staff and public |
| `backend/app/routers/payment_links.py` | CREATE | Staff: `/api/payment-links…` |
| `backend/app/routers/checkout.py` | CREATE | Public: `GET /api/pay/{token}`, `POST /api/pay/{token}/payments` |
| `backend/app/routers/simulator.py` | UPDATE | `POST /api/simulator/payments/{token}/pay` behind its own switch |
| `backend/app/config.py`, `.env.example`, `backend/.env` | UPDATE | `FRONTEND_URL`, `PAYMENT_SIMULATOR_ENABLED` |
| `backend/app/tenancy/business_settings.py` | UPDATE | Minimum and maximum link amount |
| `backend/app/main.py`, `backend/docs/rbac-spec.yaml` | UPDATE | Register routers; "Payment links" menu entry |
| `backend/tests/test_payment_tokens.py`, `test_payment_gateway_simulator.py` | CREATE | Unit tests |
| `backend/tests/pg/test_payment_links.py`, `test_checkout.py`, `test_gateway_events.py`, `test_payment_links_isolation.py`, `test_migration_0005.py` | CREATE | Integration tests |
| `backend/tests/pg/conftest.py`, `test_onboarding.py`, `backend/tests/test_business_settings.py`, `test_hospitality_models.py` | UPDATE | Helpers and coverage of the additions |
| `frontend/lib/money.ts` + `.test.ts` | CREATE | Rupiah formatting and amount parsing |
| `frontend/lib/payment-links-api.ts`, `checkout-api.ts` | CREATE | Typed calls |
| `frontend/lib/payment-link-format.ts` + `.test.ts` | CREATE | State labels, time-left text |
| `frontend/components/payments/CreateLinkDialog.tsx`, `LinkCreatedNotice.tsx`, `PaymentLinkTable.tsx`, `PaymentInstructions.tsx` | CREATE | Page parts |
| `frontend/app/(authenticated)/payment-links/page.tsx` | CREATE | Staff list, create, cancel |
| `frontend/app/pay/[token]/page.tsx` | CREATE | Public guest page |
| `frontend/app/(authenticated)/inbox/page.tsx`, `dashboard/page.tsx` | UPDATE | "Send payment link" in a thread; dashboard card links to the list |
| `frontend/lib/i18n.ts`, `frontend/middleware.ts` | UPDATE | New strings; protect `/payment-links` |
| `components-be.yaml`, `components-fe.yaml` | UPDATE | Register new artifacts |

## Tasks

Each task is test-first.

### Task 1: Migration 0005 and models
- **Action**: Add the three columns (with tenant-safe foreign keys, `SET NULL` on delete), list and conversation indexes, allow `simulator` in the gateway provider check, and create `resolve_payment_link(token_hash)` returning the link's tenant id — a `SECURITY DEFINER` function owned by the migration role, executable by `app_rw`, returning nothing else. Update the two models and the design SQL to match.
- **Mirror**: `backend/migrations/versions/0004_app_role_and_free_plan.py`.
- **Validate**: upgrade → downgrade → upgrade on an empty database; `alembic check` clean; under `app_rw` with no tenant set the function finds a link's tenant and a direct `SELECT` on `paymentlink` still returns nothing.

### Task 2: Tokens and the gateway interface
- **Action**: Token = 32 random bytes, URL-safe; only its SHA-256 is stored; comparison in constant time. `PaymentGateway` protocol (`create_charge` → reference + instructions), registry, simulated gateway producing a QRIS reference string or a 16-digit virtual account number per bank.
- **Mirror**: `backend/app/messaging/provider.py`, `simulator.py`.
- **Validate**: `uv run pytest tests/test_payment_tokens.py tests/test_payment_gateway_simulator.py -q`.

### Task 3: Gateway account per property
- **Action**: Onboarding creates the simulated gateway account; find-or-create covers existing workspaces.
- **Mirror**: `backend/app/services/messaging_accounts.py:45`.
- **Validate**: onboarding test; simultaneous first use creates one account.

### Task 4: Create, list, read, cancel (staff)
- **Action**: `POST /api/payment-links` (amount, description, optional `expires_in_hours`, `total_amount`, `conversation_id`), `GET /api/payment-links` (state filter, `limit` ≤ 50, cursor), `GET /api/payment-links/{id}`, `POST /api/payment-links/{id}/cancel`. Creation returns the full address once. With a conversation, the link is committed first and then sent with `send_reply`; a refusal is reported in the response (`sent_to_chat: false`, reason) and the link stays valid (D4). Effective state turns `active` into `expired` on read (D2).
- **Mirror**: `backend/app/routers/inbox.py:36`; `backend/app/services/inbox.py:337`.
- **Validate** (`tests/pg/test_payment_links.py`): defaults from property settings; amount below minimum, above maximum, with decimals, zero or negative → 422; total smaller than amount → 422; expiry out of bounds → 422; unknown conversation → 404; chat message contains amount and address and appears in the thread; window closed → link created, not sent; list ordering, paging, filter; cancel pending → cancelled; cancel paid → 409; expired link reads as expired and cannot be cancelled into another state; the token never appears in list or read responses.

### Task 5: Public page data and starting a payment
- **Action**: `GET /api/pay/{token}` returns property name, description, amount, down-payment total, currency, expiry, state, allowed methods and whether the simulator is on. `POST /api/pay/{token}/payments` (method, bank for virtual accounts) records a pending payment with an idempotency key of link + method + bank, then asks the gateway for instructions; repeating the request returns the same instructions. Refused when the link is not payable.
- **Mirror**: `backend/app/services/inbox.py:337` (record first, provider after).
- **Validate** (`tests/pg/test_checkout.py`): unknown or malformed token → 404 with the same body and no hint; valid token needs no session; response contains no guest name, phone, tenant id or internal ids beyond the payment reference; repeat request returns the same payment; paid / expired / cancelled link → 409 with its own message; unsupported method or bank → 422; gateway fault → payment kept as failed, 502 with a clear message.

### Task 6: Gateway notifications
- **Action**: `handle_gateway_event(...)`: store the raw event once (unique per gateway account and event id), lock the link, mark the payment captured, the link paid with `paid_at`, and other pending payments of the link cancelled. A second "paid" for an already-paid link is recorded and flagged, never applied twice. Simulator endpoint `POST /api/simulator/payments/{token}/pay` (D6) builds an event and calls it.
- **Mirror**: `backend/app/services/inbound.py:133`.
- **Validate** (`tests/pg/test_gateway_events.py`): pay → link paid, payment captured with amounts; duplicate event id → no change; two simultaneous pay events → paid once; pay on expired or cancelled link → refused; simulator off → 404; amount mismatch in the event → payment not captured and flagged.

### Task 7: Isolation and public-surface safety
- **Action**: No new code; prove it.
- **Validate** (`tests/pg/test_payment_links_isolation.py`): tenant B gets 404 on every staff route for tenant A's link; lists never mix; B cannot attach A's conversation to a link; a token only ever reveals its own link; staff and public routes run as `app_rw` with the right tenant (scope probe); the public session cannot read other tables' rows of other tenants.

### Task 8: Frontend logic
- **Action**: `money.ts` (format `Rp 850.000`, parse typed amounts, reject decimals), `payment-link-format.ts` (state label key, "expires in 3 hours"), API modules, i18n keys in both languages.
- **Mirror**: `frontend/lib/inbox-format.ts` and its test.
- **Validate**: `npx vitest run`.

### Task 9: Staff screens
- **Action**: `/payment-links`: table (state, amount, description, guest, created, paid), state filter, "show older", cancel with confirmation, "New payment link" dialog; after creation a notice with the address and a copy button, shown once. In an inbox thread, a "Send payment link" button opens the same dialog for that conversation and the sent message appears in the thread. Dashboard card links to the list. Menu entry "Payment links" after Inbox. List re-fetches on the timer so a payment shows without reload.
- **Mirror**: `frontend/app/(authenticated)/inbox/page.tsx`; `frontend/components/Dialog.tsx`; `components/DeleteConfirm.tsx` for the cancel confirmation.
- **Validate**: `npx tsc --noEmit && npm run lint`.

### Task 10: Guest page
- **Action**: `/pay/[token]`: property name, amount, description, expiry; method choice; instructions (simulated QRIS box per D1, or virtual account number with copy button); state re-checked every few seconds so "Paid" appears by itself; clear screens for paid, expired, cancelled and not-found; language switch (Bahasa default); works at phone width; no navigation chrome that needs sign-in; simulator button when enabled.
- **Mirror**: `instructions/frontend.md` "Link Landing Pages"; `instructions/theme.md`.
- **Validate**: `npx tsc --noEmit && npm run lint`.

### Task 11: Run, browser test, review
- **Action**: Per CLAUDE.md "Run and Test After Every Change": `scripts/devtest.sh start`; with Playwright — simulate a guest message, send a link from the thread, open the address from the message in a signed-out browser context, choose virtual account, simulate payment, see "Paid" on the guest page and in the staff list without reload; create a standalone link and cancel it; open an expired and an unknown link; phone width; both languages; console and `devtest.sh errors` clean; stop. Then code review and security review (money and an unauthenticated surface: security review is mandatory); fix critical and high findings. Update registers; mark the milestone complete.
- **Validate**: flow works, log clean, reviews have no open critical or high findings.

## Validation

```bash
cd backend
uv run ruff check app/payments app/services app/routers app/schemas app/tenancy tests
uv run pytest -q
uv run pytest -q --cov=app/payments --cov=app/services --cov=app/schemas --cov=app/tenancy --cov-report=term-missing
uv run alembic upgrade head && uv run alembic check

cd ../frontend
npx vitest run && npx tsc --noEmit && npm run lint

cd .. && bash scripts/devtest.sh start   # Playwright walk-through, `bash scripts/devtest.sh errors`, `stop`
```

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| The public endpoint becomes a way into tenant data | Medium | Lookup function returns only a tenant id for an exact token fingerprint; everything after runs tenant-scoped as `app_rw`; response is a fixed, minimal shape; tests assert what is absent |
| Link address is also present in the chat message stored in the database | High (by design) | Accepted: the guest must receive it. Messages are tenant-scoped; the link table itself holds only the fingerprint; links expire and can be cancelled |
| No rate limiting on the public endpoints | High | Tokens are 256-bit, so guessing is not practical; request bodies are tiny and bounded. Rate limiting remains the open follow-up before the pilot, now more pressing |
| A link is paid twice (two methods, or a late notification after expiry) | Medium | Link row locked while applying an event; second capture recorded and flagged for refund handling, which is out of scope |
| Simulated gateway hides real behaviour (asynchronous notifications, signatures, partial payments, fees) | High | One event entry point with idempotency and amount check; `signature_valid` recorded; real gateway replaces the simulator behind the same interface |
| Expiry worked out on read leaves stale stored states | Medium | Every read and every payment attempt uses the effective state; list filter uses the expiry time, not only the stored state |
| Staff lose the link address after closing the notice | Medium | It is in the chat message; cancel-and-recreate otherwise (D3) |
| Changing generated model files by hand drifts from the design SQL | Medium | Update `schema-tenant.sql` in the same change; `alembic check` and the model tests guard the rest |
| Free-plan limit not enforced until milestone 5 | Low | Dashboard already shows the count; noted for the user (D5) |

## Out of this milestone

Real gateway connection and signature checks, cards and e-wallets, refunds, partial payments, payment schedules, receipts and invoices, linking a payment to a reservation or folio, transfer-proof upload (milestone 4), free-plan limit enforcement (milestone 5), reminders for unpaid links, scannable QR image.

## Acceptance
- [ ] All tasks complete
- [ ] Validation passes
- [ ] Patterns mirrored, not reinvented
- [ ] A link sent from a conversation can be opened signed-out, paid by simulated virtual account, and shows as paid to guest and staff without a manual refresh
- [ ] Cross-tenant access to links fails in tests, and the public page exposes no guest personal data
