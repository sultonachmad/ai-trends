# Plan: Phase 0 — Milestone 2: WhatsApp Inbox

**Source PRD**: `.claude/prds/phase-0-whatsapp-wedge.prd.md`
**Selected Milestone**: 2 — WhatsApp inbox
**Complexity**: Large

## Summary

Staff open an Inbox page, see their property's guest conversations newest first with unread counts, open a thread, read the history and reply; they can mark a conversation resolved. WhatsApp itself is simulated behind a provider interface: outbound messages go to a simulator, and a development-only panel lets a tester send messages in as a guest. The inbound path is the same function a real WhatsApp webhook will call later.

The tables already exist (`messagingaccount`, `conversation`, `message`, `guest`), so no schema migration is expected. No new packages.

## Decisions needed before coding

| # | Decision | Recommendation | Why it matters |
|---|---|---|---|
| D1 | How new messages reach the screen | The page asks the server every few seconds (5 s for the list, 3 s for the open thread), only while the tab is visible | Meets the PRD's "appear without a manual refresh" with no new infrastructure. Live push can replace it later without changing the endpoints |
| D2 | How a tester plays the guest | A "Simulate guest message" panel on the Inbox page, plus the endpoint behind it, both switched on only by a setting (`PREFAB_MESSAGING_SIMULATOR_ENABLED`, off by default, on in local `.env`) | Without it nobody can produce an inbound message. Off by default so it cannot be left open in production |
| D3 | Who can use the inbox | Every member of the workspace can read, reply and resolve | Matches milestone 1; role rules first matter in milestone 4 (second approver) |
| D4 | WhatsApp's 24-hour reply window | Enforce it in the simulator: a free-text reply is refused, with a clear message, when the guest's last message is older than 24 hours | Real WhatsApp refuses these and requires an approved template, which is out of scope. Enforcing now avoids building a flow that breaks on the real provider. Downside: staff cannot reply to an old chat until templates exist |
| D5 | Guest writes again after a conversation was resolved | A new conversation is opened; the resolved one stays in history | This is what the existing unique rule on conversations is built for |

## Requirements restated

- Inbox lists the caller's property conversations: guest name, phone, last message preview and time, unread count; filter open / resolved; newest activity first; paged.
- Opening a conversation shows its messages oldest to newest and clears its unread count.
- Staff reply with plain text (1 to 4 096 characters); the reply appears in the thread with its delivery state and who sent it.
- Staff can resolve and reopen a conversation.
- An inbound message creates the guest (matched by WhatsApp number) and the conversation when needed, raises the unread count, and never duplicates when the provider repeats a delivery.
- New inbound messages show up without a manual refresh.
- Nothing from another tenant is ever visible or reachable by id.
- All staff text in Bahasa Indonesia and English.
- Dashboard's inbox card shows the real unread count and links to the Inbox.

## Patterns to Mirror

| Category | Source | Pattern |
|---|---|---|
| Naming | `backend/app/routers/workspace.py:1`, `backend/app/services/workspace.py:1` | `app/routers/<feature>.py` exporting `<feature>_router`; logic in `app/services/<feature>.py`; shapes in `app/schemas/<feature>.py` |
| Tenant access | `backend/app/routers/workspace.py:44`, `backend/app/tenancy/session.py:52` | Routes depend on `get_tenant_context` + `get_tenant_session`; every query also filters `tenant_id` explicitly |
| Errors | `backend/app/routers/onboarding.py:45`, `backend/app/routers/workspace.py:22` | Service raises a named exception; router maps it to `HTTPException` with its own `detail`; 404 never bare |
| Logging | `backend/app/services/onboarding.py:216` | `log = logging.getLogger(__name__)`; `log.info("... %s", value)`; no message bodies or phone numbers in logs |
| Configurable values | `backend/app/tenancy/business_settings.py:27` | Add new property-level values to `PropertySettings` with a default and bounds |
| Settings | `backend/app/config.py:30` | New env-driven switch as a typed `Settings` field with a comment; documented in `.env.example` |
| Tests (backend) | `backend/tests/pg/test_workspace.py:30`, `backend/tests/pg/conftest.py` | `async def test_…(pg_client[, other_client, pg_session])`; `sign_up_and_in` + `onboarding_payload` helpers; one behaviour per test |
| Frontend API | `frontend/lib/workspace-api.ts:36` | Typed functions over the shared `request` helper |
| Frontend pages | `frontend/app/(authenticated)/dashboard/page.tsx:22` | `"use client"`, `useLocale().t`, semantic Tailwind classes, loading / error / empty states |
| UI text | `frontend/lib/i18n.ts:15` | Every string in both dictionaries; test asserts both languages have each key |
| Tests (frontend) | `frontend/lib/i18n.test.ts:1` | `vitest`, plain-logic tests beside the module |
| Menus | `backend/docs/rbac-spec.yaml` (Dashboard entry) | One top-level entry per page, in the spec only |
| Run and test | `CLAUDE.md` "Run and Test After Every Change" | `scripts/devtest.sh start`, Playwright walk-through, `devtest.sh errors`, stop |

No existing pattern covers a provider interface or timed re-fetching; both are introduced here.

## Files to Change

| File | Action | Why |
|---|---|---|
| `backend/app/messaging/__init__.py` | CREATE | New module: provider interface and simulator |
| `backend/app/messaging/provider.py` | CREATE | `MessagingProvider` protocol, send result, provider lookup by `messagingaccount.provider` |
| `backend/app/messaging/simulator.py` | CREATE | Simulated WhatsApp sender (accepts, returns a provider id; applies the 24-hour rule) |
| `backend/app/messaging/phone.py` | CREATE | Phone number validation and normalisation |
| `backend/app/services/inbox.py` | CREATE | List, read, reply, resolve / reopen, mark read, unread summary |
| `backend/app/services/inbound.py` | CREATE | Receive an inbound message: find or create guest and conversation, store once |
| `backend/app/services/messaging_accounts.py` | CREATE | Find or create the property's WhatsApp account |
| `backend/app/services/onboarding.py` | UPDATE | New workspaces get their (simulated) WhatsApp account |
| `backend/app/schemas/inbox.py` | CREATE | Request and response shapes with validation |
| `backend/app/routers/inbox.py` | CREATE | `/api/conversations…`, `/api/inbox/summary` |
| `backend/app/routers/simulator.py` | CREATE | `POST /api/simulator/whatsapp/inbound`, registered only when the switch is on |
| `backend/app/config.py`, `.env.example`, `backend/.env` | UPDATE | `MESSAGING_SIMULATOR_ENABLED` |
| `backend/app/tenancy/business_settings.py` | UPDATE | `inbox_poll_seconds`, `thread_poll_seconds` (configurable, D1) |
| `backend/app/schemas/workspace.py`, `backend/app/services/workspace.py` | UPDATE | Workspace summary reports unread conversations and whether the simulator is on |
| `backend/app/main.py` | UPDATE | Register routers |
| `backend/docs/rbac-spec.yaml` | UPDATE | Inbox menu entry |
| `backend/tests/test_phone.py`, `backend/tests/test_messaging_simulator.py` | CREATE | Unit tests (no database) |
| `backend/tests/pg/test_inbound.py`, `test_inbox.py`, `test_inbox_isolation.py` | CREATE | Integration tests |
| `backend/tests/test_business_settings.py`, `backend/tests/pg/test_onboarding.py`, `test_workspace.py` | UPDATE | Cover the additions |
| `frontend/lib/inbox-api.ts` | CREATE | Typed inbox calls |
| `frontend/lib/inbox-format.ts` + `.test.ts` | CREATE | Preview trimming, relative time, message grouping by day |
| `frontend/lib/use-polling.ts` | CREATE | Re-fetch on an interval while the tab is visible |
| `frontend/app/(authenticated)/inbox/page.tsx` | CREATE | Two-pane inbox (list + thread); single pane on phones |
| `frontend/components/inbox/ConversationList.tsx`, `MessageThread.tsx`, `ReplyBox.tsx`, `SimulatorPanel.tsx` | CREATE | Page parts, each small and focused |
| `frontend/app/(authenticated)/dashboard/page.tsx` | UPDATE | Inbox card shows unread count and links to `/inbox` |
| `frontend/lib/i18n.ts`, `frontend/middleware.ts` | UPDATE | New strings; protect `/inbox` |
| `components-be.yaml`, `components-fe.yaml` | UPDATE | Register new artifacts |

## Tasks

Each task is test-first.

### Task 1: Phone numbers and the provider interface
- **Action**: Normalise numbers to `+<digits>` (accept `08…` Indonesian local form as `+628…`), reject anything else. Define `MessagingProvider` and the simulator; unknown provider names raise a clear error.
- **Mirror**: `backend/app/tenancy/business_settings.py` (small typed module, named error).
- **Validate**: `uv run pytest tests/test_phone.py tests/test_messaging_simulator.py -q`.

### Task 2: Messaging account per property
- **Action**: Onboarding creates a WhatsApp account (`provider = "simulator"`). A find-or-create function covers workspaces made before this milestone.
- **Mirror**: `backend/app/services/onboarding.py:124` (`_create_tenant_data`).
- **Validate**: onboarding test asserts one account; a workspace without one gets it on first inbox use.

### Task 3: Inbound messages
- **Action**: `receive_inbound(session, context, from_phone, guest_name, body, provider_message_id)`: match or create the guest by WhatsApp number; reuse the open conversation for that number or create one (D5); store the message; raise `unread_count`; set `last_message_at`, `last_inbound_at` and the 24-hour window. A repeated `provider_message_id` stores nothing and returns the first result.
- **Mirror**: `backend/app/services/onboarding.py:186` (lock-then-check for races).
- **Validate** (`tests/pg/test_inbound.py`): first message creates guest + conversation; second reuses both; duplicate id is ignored; message after resolve opens a new conversation; two simultaneous first messages from one number produce one conversation.

### Task 4: Inbox service and endpoints
- **Action**: `GET /api/conversations` (status filter, `limit` ≤ 50, cursor), `GET /api/conversations/{id}`, `GET /api/conversations/{id}/messages` (`after` for incremental fetch), `POST …/messages`, `POST …/read`, `POST …/resolve`, `POST …/reopen`, `GET /api/inbox/summary`. The list loads each conversation's last message in the same query (no query per row).
- **Mirror**: `backend/app/routers/workspace.py:38`; `backend/app/services/workspace.py:63`.
- **Validate** (`tests/pg/test_inbox.py`): ordering, paging, filter, unread cleared on read, reply stored with sender and `sent` state, empty and over-long bodies → 422, reply outside the 24-hour window → 409 with message (D4), reply to a resolved conversation → 409, unknown id → 404 with own detail, unauthenticated → 401.

### Task 5: Tenant isolation for the inbox
- **Action**: No new code; prove it.
- **Validate** (`tests/pg/test_inbox_isolation.py`): tenant B gets 404 for tenant A's conversation on every route (read, messages, reply, read, resolve); B's list and summary never include A's rows; an inbound for A never lands in B.

### Task 6: Simulator endpoint and switch
- **Action**: `POST /api/simulator/whatsapp/inbound` (signed-in member; guest phone, optional name, text) calls `receive_inbound` for the caller's own property. Router registered only when the setting is on. Workspace summary exposes the flag.
- **Mirror**: `backend/app/config.py:30`.
- **Validate**: endpoint works when on; app built with the switch off has no such route (404); cannot target another tenant.

### Task 7: Configurable polling intervals and workspace summary
- **Action**: Add the two intervals to `PropertySettings` (bounded 2 to 120 s); workspace summary returns `unread_conversations`.
- **Validate**: settings tests for defaults, override and bounds; workspace test for the count.

### Task 8: Frontend logic
- **Action**: `inbox-api.ts`, `inbox-format.ts`, `use-polling.ts` (pauses when the tab is hidden, never overlaps requests, stops on unmount), new i18n keys.
- **Mirror**: `frontend/lib/workspace-api.ts`; `frontend/lib/i18n.test.ts`.
- **Validate**: `npx vitest run` — formatting and key-coverage tests.

### Task 9: Inbox page
- **Action**: `/inbox`: conversation list (open / resolved tabs, unread badges, empty state), thread with day separators and sent / failed markers, reply box (Enter sends, Shift+Enter new line, disabled with explanation when the window is closed or the conversation is resolved), resolve / reopen button, simulator panel when enabled. Selected conversation kept in the URL (`/inbox?c=<id>`). Dashboard card shows unread count and links here. Menu entry "Inbox" after Dashboard.
- **Mirror**: `frontend/app/(authenticated)/dashboard/page.tsx`; `instructions/frontend.md`; `instructions/theme.md`.
- **Validate**: `npx tsc --noEmit && npm run lint`.

### Task 10: Run, browser test, review
- **Action**: Follow CLAUDE.md "Run and Test After Every Change": `scripts/devtest.sh start`; with Playwright sign up, onboard, open Inbox, send a simulated guest message, see it appear without reload, open it, reply, resolve, send again as the guest and see a new conversation; switch language; check console and `devtest.sh errors`; stop. Then code review and security review; fix critical and high findings. Update registers.
- **Validate**: flow works, log clean, reviews have no critical or high findings.

## Validation

```bash
cd backend
uv run ruff check app/messaging app/services app/routers/inbox.py app/routers/simulator.py app/schemas tests
uv run pytest -q
uv run pytest -q --cov=app/messaging --cov=app/services --cov=app/schemas --cov=app/tenancy --cov-report=term-missing
uv run alembic check

cd ../frontend
npx vitest run && npx tsc --noEmit && npm run lint

cd .. && bash scripts/devtest.sh start   # then Playwright walk-through, `bash scripts/devtest.sh errors`, `stop`
```

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Simulator hides real WhatsApp behaviour (delivery receipts, media, templates, webhook retries) | High | Inbound goes through one function with idempotency on the provider id; the 24-hour rule is enforced (D4); media and templates are explicitly out |
| Re-fetching every few seconds loads the server as tenants grow | Medium | Only while the tab is visible; incremental `after` fetch for threads; intervals are configurable per property; index `ix_conversation_inbox` already serves the list |
| List query fetches one "last message" per row | Medium | Single query with the last message joined; a test seeds 30 conversations and asserts the query count |
| Two inbound messages race and create two conversations | Medium | Lock on the guest/number before the check; test with simultaneous calls |
| Simulator endpoint left on in production | Low | Off by default; router not registered when off; test proves the 404 |
| Message text or phone numbers leak into logs | Medium | Log ids only; review checks it |
| Enforcing the 24-hour window frustrates testers | Medium | Clear on-screen explanation; a new guest message reopens the window; revisit when templates are built |
| No rate limiting on reply and simulator endpoints | Medium | Not in this milestone (no limiter in the stack yet); body size capped at 4 096 characters; record as follow-up before pilot |

## Out of this milestone

Real WhatsApp connection and webhooks, media and voice messages, message templates, AI drafting, assignment of conversations to staff, snooze, internal notes, search, live push, SLA / first-reply-time reporting (timestamps needed for it are stored), other channels.

## Acceptance
- [ ] All tasks complete
- [ ] Validation passes
- [ ] Patterns mirrored, not reinvented
- [ ] A simulated guest message appears in the inbox without a manual refresh, can be answered, and the conversation can be resolved
- [ ] Cross-tenant access to conversations and messages fails in tests
