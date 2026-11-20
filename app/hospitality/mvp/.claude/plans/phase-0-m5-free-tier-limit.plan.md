# Plan: Free-tier limit (Phase 0, Milestone 5)

**Source PRD**: `.claude/prds/phase-0-whatsapp-wedge.prd.md`
**Selected Milestone**: 5 — Free-tier limit
**Complexity**: Small

## Summary

The Free plan allows 30 payment links per month. The number is already stored on the plan
(`tenantentitlement.limits.payment_links_per_month`) and the dashboard already shows "x of 30 used",
but nothing stops link number 31. This milestone makes the server refuse a new link once the limit is
reached, makes that refusal safe when two staff create links at the same moment, and shows usage, an
early warning and a clear "limit reached" message wherever staff create links.

## What already exists (no change needed)

| Piece | Where |
|---|---|
| Limit value per plan, default 30, `None` = unlimited | `backend/app/tenancy/business_settings.py:115` (`PlanLimits`) |
| Limit lookup for the tenant | `backend/app/services/workspace.py:90` (`payment_link_limit`) |
| Count of links created this calendar month in the property's timezone | `backend/app/services/workspace.py:106` (`payment_links_used_this_month`) |
| Usage in the workspace payload | `backend/app/schemas/workspace.py:52` (`UsageSummary`) |
| Usage text on the dashboard | `frontend/app/(authenticated)/dashboard/page.tsx:72` |

## Decisions (recommendation first — reply "yes" to accept all)

| # | Question | Recommendation |
|---|---|---|
| D1 | Which links count? | Every link created in the month, including cancelled and expired ones. Otherwise create-then-cancel gets around the limit. This is what the dashboard already counts. |
| D2 | When does the count reset? | The 1st of each calendar month at 00:00 in the property's timezone (already how usage is counted). |
| D3 | Does a transfer recorded by staff with no link count? | No. It is not a payment link. |
| D4 | Early warning? | Yes, from 80% used (24 of 30). The percentage is a configurable platform value, default 80. |
| D5 | What does staff see at the limit? | The "new link" buttons stay visible but open a message instead of the form: "30 of 30 links used this month. You can create links again on 1 December." No upgrade button, because paid plans are out of scope for Phase 0. |
| D6 | What does the server answer? | `403` with the same message, so the limit holds even if the screen is stale or the API is called directly. |
| D7 | Tenant with payments not enabled (limit 0)? | Same refusal path with its own text ("Payment links are not part of your plan."). Cannot happen for Free-plan tenants today. |

## Patterns to Mirror

| Category | Source | Pattern |
|---|---|---|
| Naming | `backend/app/services/payment_links.py:280` | Service function per action (`create_link`), named exception classes at the top of the service |
| Errors | `backend/app/routers/payment_links.py:38` | Named service exceptions turned into HTTP answers in the router's `_guarded` |
| Locking | `backend/app/services/checkout.py:282` | Check a count under a lock inside the same transaction that inserts |
| Config | `backend/app/tenancy/business_settings.py:115` | Business numbers as validated settings with PRD defaults, never literals in services |
| Data access | `backend/app/services/workspace.py:106` | Tenant-scoped session, explicit `tenant_id` filter, count with `func.count()` |
| Logging | `backend/app/services/payment_links.py:313` | `log.info` with ids only, no personal data |
| Tests | `backend/tests/pg/test_payment_links.py`, `test_payment_review_fixes.py:150` | PostgreSQL integration tests through the HTTP client, helpers from `tests/pg/conftest.py`, limits lowered by updating the row or `monkeypatch` |
| UI text | `frontend/lib/i18n.ts` | Every string in both `id` and `en` |
| UI helpers | `frontend/lib/payment-link-format.ts` (+ test) | Pure formatting/decision helpers with vitest tests |

## Files to Change

| File | Action | Why |
|---|---|---|
| `backend/app/services/link_quota.py` | CREATE | `LinkQuota` (used, limit, resets_at, state), `read_quota`, `reserve_link_slot` (lock + check), `PaymentLinkLimitReachedError` |
| `backend/app/services/payment_links.py` | UPDATE | `create_link` calls `reserve_link_slot` in the transaction that inserts the link |
| `backend/app/services/workspace.py` | UPDATE | Build `UsageSummary` from `read_quota`; add `month_end_utc` next to `month_start_utc` |
| `backend/app/schemas/workspace.py` | UPDATE | `UsageSummary` gains `resets_at`, `warning` and `limit_reached` |
| `backend/app/tenancy/business_settings.py` | UPDATE | `PlanLimits.usage_warning_percent` (default 80, 1–100) |
| `backend/app/routers/payment_links.py` | UPDATE | Map `PaymentLinkLimitReachedError` to 403 with the message |
| `backend/tests/pg/test_link_quota.py` | CREATE | Limit, reset, concurrency, isolation and payload tests |
| `backend/tests/test_business_settings.py` | UPDATE | New setting default and bounds |
| `backend/tests/pg/conftest.py` | UPDATE | `set_link_limit(session, tenant_id, limit)` helper |
| `frontend/lib/workspace-api.ts` | UPDATE | New `usage` fields |
| `frontend/lib/link-quota.ts` + `link-quota.test.ts` | CREATE | `quotaState(usage)` → `ok / warning / reached / unlimited`, message keys, reset-date formatting |
| `frontend/components/payments/LinkQuotaNotice.tsx` | CREATE | Usage line with a small bar; warning and limit-reached styles |
| `frontend/app/(authenticated)/payment-links/page.tsx` | UPDATE | Show the notice; at the limit the "new link" button opens the message; refresh usage after create |
| `frontend/app/(authenticated)/inbox/page.tsx` | UPDATE | Same handling for the "send payment link" action |
| `frontend/app/(authenticated)/dashboard/page.tsx` | UPDATE | Use the notice in the plan card |
| `frontend/lib/i18n.ts` | UPDATE | New strings in both languages |
| `components-be.yaml`, `components-fe.yaml` | UPDATE | Register the new pieces |
| `.claude/prds/phase-0-whatsapp-wedge.prd.md` | UPDATE | Milestone status |

No migration: the limit lives in existing columns, and no new packages are needed.

## Tasks

### Task 1: Quota service (tests first)
- **Action**: Write `tests/pg/test_link_quota.py` for `read_quota` and the create endpoint, then `link_quota.py`. `reserve_link_slot` takes a per-tenant transaction-level advisory lock (`pg_advisory_xact_lock`), counts this month's links, and raises `PaymentLinkLimitReachedError(used, limit, resets_at)` when `limit is not None and used >= limit`. The lock is released by the commit that inserts the link, so two simultaneous requests at 29 of 30 give exactly one link.
- **Why an advisory lock**: the limit row is in a control-plane table the app role can only read, so it cannot be row-locked; an advisory lock needs no grant and no schema change.
- **Mirror**: locking and counting in `checkout.py:282`; exceptions as in `payment_links.py`.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_link_quota.py -q`

### Task 2: Enforce on create
- **Action**: Call `reserve_link_slot` in `create_link` after input checks and before the insert; map the error to 403 in the router. Cases to test: link 30 succeeds and link 31 is refused; cancelled and expired links still count; links from last month do not count (insert with an old `created_at`); limit `None` is unlimited; limit 0 is refused with its own text; two simultaneous creates at limit−1 give one 201 and one 403; another tenant's links do not count; a refused create sends nothing to the chat.
- **Mirror**: `_guarded` in `routers/payment_links.py:38`; simultaneous-request test in `test_proof_approval.py:308`.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_link_quota.py tests/pg/test_payment_links.py -q`

### Task 3: Usage in the workspace payload
- **Action**: Add `usage_warning_percent` to `PlanLimits`; `UsageSummary` returns `resets_at` (start of next month in the property's timezone, as UTC), `warning` and `limit_reached`, all from `read_quota` so the screen and the enforcement can never disagree. Test the month boundary in a non-UTC timezone (Asia/Makassar) and December → January.
- **Mirror**: `month_start_utc` in `workspace.py:47`; settings tests in `test_business_settings.py`.
- **Validate**: `uv run pytest tests/test_business_settings.py tests/pg/test_workspace.py -q`

### Task 4: Frontend
- **Action**: `link-quota.ts` helpers with tests first; `LinkQuotaNotice`; wire into the payment links page, the inbox link action and the dashboard. After a successful create, re-fetch the workspace so the count moves. If the server answers 403 (stale screen), show the limit message and re-fetch.
- **Mirror**: `payment-link-format.ts` and its test; existing dialog and notice styling; all text through `i18n.ts`.
- **Validate**: `npx vitest run && npx tsc --noEmit && npm run lint`

### Task 5: Run, browser test, review
- **Action**: Full backend suite with coverage and `alembic check`. Start with `bash scripts/devtest.sh start`; with Playwright, on a fresh workspace lower the limit to 3 in the dev database, create links and watch the count, see the warning, hit the limit from both the payment links page and an inbox conversation, check the message and reset date in both languages and at phone width; `devtest.sh errors` clean; stop. Then code review and security review (limit bypass paths); fix critical and high findings. Update the registers and mark the milestone complete.
- **Validate**: commands below.

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
| Two staff create links at the same moment and both pass the check | Medium | Per-tenant advisory lock held until the insert commits; simultaneous-request test |
| Screen shows a different number than the server enforces | Medium | One function (`read_quota`) feeds both; the screen re-fetches after every create and after a refusal |
| Month boundary wrong for Bali (UTC+8) | Low | Reuse the existing timezone-aware month start; tests around midnight on the 1st |
| Existing tests create more than 30 links in one tenant | Low | Each test starts its own workspace; run the full suite |
| Operators hit the limit with no way forward | Medium (product) | Message gives the reset date; raising a tenant's limit is a one-row change in `tenantentitlement.limits` until paid plans exist |

## Acceptance

- [ ] Link number 31 in a month is refused by the server with a clear message; link 30 succeeds
- [ ] Simultaneous requests cannot exceed the limit
- [ ] Usage, an 80% warning and the limit message with reset date show on the dashboard, the payment links page and the inbox link action, in both languages
- [ ] Limit and warning percentage are configurable values, not literals
- [ ] All tasks complete, validation passes, coverage at least 80%
- [ ] Patterns mirrored, not reinvented
