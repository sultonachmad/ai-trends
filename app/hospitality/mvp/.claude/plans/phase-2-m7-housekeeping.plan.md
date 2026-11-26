# Plan: Housekeeping on phone (Phase 2, Milestone 7)

**Source PRD**: `.claude/prds/phase-2-pms-core.prd.md`
**Selected Milestone**: 7 — Housekeeping on phone
**Complexity**: Large

## Summary

Housekeepers sign in on their own phone, see the rooms they must clean today in priority order, and tap Start, Done or Problem. The room's status changes at once and the front desk sees it within seconds. Cleaning tasks are made from the front desk's own data (departures, stay-overs, room moves) and stay in step when it changes. A supervisor assigns rooms and, if the property wants it, inspects them before check-in. A big-button mode serves staff who find detailed screens hard. Owners add staff by sending them a join link, because today a workspace has only its owner.

## What already exists, and the gaps

| Need | Today | Gap this milestone closes |
|---|---|---|
| Room status | `unit.hk_status` (dirty, in_progress, clean, inspected), `fo_status`, `service_status`; the one writer `services/unit_status.py:43` logs each change to `unitstatuslog` | Only check-out and room moves change it; no one can mark a room clean; the log always says `staff`, never `mobile` |
| Cleaning tasks | `task` table (kind, unit, date, status, assigned staff, start and finish times, inspection result, notes) | Unused |
| Readiness at check-in | `is_ready` treats clean or inspected as ready; check-in warns on a room that is not ready | No property choice of clean versus inspected |
| Front desk rooms | Rooms tab shows status, loaded once | Does not refresh |
| Staff accounts | `tenantinvitation` (hashed token, roles, expiry) and `staffmember` exist; only onboarding creates a membership | An owner cannot add a housekeeper, and the manager role cannot reach `/admin` |

## Decisions (recommendation first; reply "yes" to accept all)

| # | Question | Recommendation |
|---|---|---|
| D1 | How staff get accounts | **Join link.** The owner (`staff:edit`) enters a name, email and role (Manager, Front desk or Housekeeper) and gets a link to send by WhatsApp. It is valid for 7 days, works once, and only for that email. The person signs up or signs in and joins. The owner can see, revoke and remove staff. No email sending (no new package or env var) |
| D2 | Roles | Three ready roles in `rbac-spec.yaml`: **manager** (all, as today), **front_desk** (bookings, front desk, bills, guest ID, APOA, end of day view), **housekeeper** (`housekeeping:view`, `housekeeping:edit`). The spec's note that narrower roles are not predefined is updated |
| D3 | Which tasks exist | Made from front desk data and kept in step: a **departure clean** for each room checked out or vacated by a room move; a **stay-over clean** for each occupied room not leaving today (property setting: every day, or only on request); a dirty vacant room always has a task. Undoing a check-out, or a move, cancels tasks not yet started. Yesterday's unfinished tasks move to today. Made in the same transaction as the front desk action, and once per day when the board first opens |
| D4 | Order on the phone | Rooms with a guest arriving today first (earliest booking first), then departures already out, then stay-overs, then the rest. Each shows the room, task, arriving or leaving guests, adults and children, and the booking's special requests |
| D5 | Phone flow | **Start** → task in progress, room in progress, time recorded. **Done** → room clean (or waiting for inspection, see D7). **Problem** → pick: do not disturb, guest refused, needs repair, room empty when it should be occupied, other; with an optional note. Do not disturb and refused end the task for today; every problem shows on the front desk. Needs repair is a note in M7 and becomes a maintenance request in M8 |
| D6 | Assignment | A supervisor (`housekeeping:manage`) assigns rooms to housekeepers by tap, or "split evenly". Unassigned rooms show to every housekeeper with a **Take** button, which suits small properties with one or two cleaners |
| D7 | Inspection | Property setting **Ready for check-in when**: clean (default) or inspected. With inspected, a supervisor passes the room (inspected) or fails it with a reason (dirty again, back to the same housekeeper). `is_ready` follows the setting |
| D8 | Front desk sees it at once | The front desk rooms tab and the housekeeping board refresh every 15 seconds while the page is open and on returning to it. The front desk can also change a room's status by hand (`housekeeping:edit`) |
| D9 | Phone versus desk | Each status change records `mobile` or `staff` from the device, for the PRD metric "updates made on a phone" |
| D10 | Big-button mode | A switch on the phone page, remembered on that phone: one room at a time, large Start, Done and Problem buttons with icons and colour, short words, Bahasa first |
| D11 | Permissions | `housekeeping:view` (board), `housekeeping:edit` (work tasks, change status), `housekeeping:manage` (assign, inspect, settings), `staff:view`, `staff:edit`. Manager role holds all |
| D12 | Where | A new **Housekeeping** group: **Rooms to clean** (`/housekeeping`, phone-first). A **Staff** entry under Settings (`/staff`). A public **join** page (`/join/[token]`). Problems appear on the front desk |

## Patterns to Mirror

| Category | Source | Pattern |
|---|---|---|
| Room status writer | `backend/app/services/unit_status.py:43` | One writer, logs every change |
| Front desk actions | `backend/app/services/front_desk.py:148,255,298,323`, `room_assignment.py:182` | Lock property, then booking; status change in the same transaction |
| Refusals | `backend/app/services/end_of_day_errors.py` | `FrontDeskError` subclasses with a stable `code` |
| Staff lookup | `backend/app/services/cash_drawers.py:156` | Staff names by id within the tenant |
| Membership and roles | `backend/app/services/onboarding.py:212`, `workspace_access.grant_manager` | Membership with `staff_member_id`; RBAC role grant |
| Tests | `backend/tests/pg/test_cash_drawers.py`, `test_day_close.py` | HTTP client, permissions, tenant separation |
| Frontend | `frontend/app/(authenticated)/end-of-day/page.tsx`, `components/cash-drawer/CashDrawerDialog.tsx` | Tested helpers, text in `lib/i18n.ts` |

## Files to Change

| File | Action | Why |
|---|---|---|
| `backend/migrations/versions/0020_housekeeping.py` | CREATE | One open task per room, kind and day; tasks by day and by person; invitations by tenant; the readiness and stay-over settings |
| `backend/app/services/housekeeping_tasks.py`, `housekeeping_board.py`, `housekeeping_errors.py` | CREATE | Keep tasks in step, order, start, done, problem, assign, take, inspect |
| `backend/app/services/unit_status.py` | UPDATE | Source (`mobile` or `staff`), task link, readiness setting |
| `backend/app/services/front_desk.py`, `room_assignment.py` | UPDATE | Make or cancel tasks with check-out, move and undo |
| `backend/app/services/staff_invites.py`, `staff_errors.py` | CREATE | Invite, join, list, revoke, remove |
| `backend/app/schemas/housekeeping.py`, `staff.py`, `routers/housekeeping.py`, `routers/staff.py`, `app/main.py` | CREATE / UPDATE | `/api/housekeeping/...`, `/api/staff/...`, `/api/join/...` |
| `backend/docs/rbac-spec.yaml` | UPDATE | New codes, three roles, menu entries |
| `backend/tests/pg/test_housekeeping.py`, `test_staff_invites.py` | CREATE | See Tasks |
| `frontend/app/(authenticated)/housekeeping/page.tsx`, `components/housekeeping/*`, `lib/housekeeping-api.ts`, `lib/housekeeping-format.ts` + test | CREATE | Phone board, big-button mode, supervisor view |
| `frontend/app/(authenticated)/staff/page.tsx`, `app/join/[token]/page.tsx`, `lib/staff-api.ts` | CREATE | Staff list, invite and join |
| `frontend/app/(authenticated)/front-desk/page.tsx`, `components/front-desk/RoomsToday.tsx`, `middleware.ts`, `lib/i18n.ts` | UPDATE | Refresh, problems, change status by hand, routes, `id` + `en` text |
| `components-be.yaml`, `components-fe.yaml`, the PRD | UPDATE | Registers and milestone status |

## Tasks

Each backend task is test-first. Work on `feat/phase-2-m7-housekeeping`, branched from `feat/phase-2-m6-end-of-day`.

### Task 1: Staff join links
- **Action**: Invite with name, email and role; link token shown once and stored hashed; 7 days; one use; the signed-in email must match; joining makes the staff member, the membership and the role; revoke and remove (removal ends access and keeps history). Tests: wrong email, expired, used, revoked, a user who already has a workspace, permissions, tenant separation.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_staff_invites.py -q`

### Task 2: Tasks kept in step
- **Action**: Tasks from check-out, moves, stay-overs and dirty rooms; undo cancels; carry-over from yesterday; stay-over setting. Tests: each front desk action makes or cancels the right task; making tasks twice makes no duplicates; a started task is never cancelled.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_housekeeping.py tests/pg/test_front_desk.py -q`

### Task 3: Phone actions, assignment and inspection
- **Action**: Order (D4), start, done, problem, take, assign, split evenly, inspect pass and fail, readiness setting; status log with `mobile` or `staff`. Tests: a housekeeper sees only their rooms and unassigned ones; cannot work someone else's task; done makes the room ready (or waiting for inspection); check-in readiness follows the setting; problems reach the front desk read.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_housekeeping.py -q`

### Task 4: Frontend
- **Action**: Phone board with My rooms and All rooms, big-button mode, problem sheet, supervisor assignment and inspection, settings; staff page and join page; front desk refresh, problem list and change status by hand; both languages; phone width.
- **Validate**: `npx vitest run && npx tsc --noEmit && npm run lint`

### Task 5: Run, browser test, review
- **Action**: Full suites, migration up/down/up. Browser: the owner invites a housekeeper; the housekeeper signs up and joins on a phone-sized window; check a guest out at the desk; the room appears for the housekeeper; Start, Done, a Problem in big-button mode; the front desk sees the change without reloading; inspection on. Both languages, `devtest.sh errors`. Code, security and database review; fix critical and high findings. Update registers and mark the milestone complete. A backend restart is needed to see the new menu entries.

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
| Housekeepers do not adopt the phone | Medium | Big-button mode, Bahasa first, Take button so no planning is needed; watched at pilot |
| Tasks drift from the front desk | Medium | Made in the same transaction as each front desk action, plus a daily pass; tests per action |
| A join link is forwarded to the wrong person | Medium | One use, 7 days, the email must match, revocable; the owner sees who joined |
| Refreshing every 15 seconds loads the server | Low | Small reads by property; only while the page is visible |
| Inspection slows check-in | Low | Off by default; the front desk can still check in a room that is not ready, as today |

## Acceptance

- [x] An owner adds a housekeeper with a join link, and the housekeeper signs in on their own phone
- [x] Housekeepers see their rooms in priority order and use Start, Done and Problem, including in big-button mode
- [x] Tasks follow check-outs, moves, stay-overs and undo without duplicates
- [x] The front desk sees status changes and problems within seconds, and can change status by hand
- [x] A supervisor assigns and, when the property wants it, inspects; check-in readiness follows the setting
- [x] Each status change records phone or desk
- [x] Access needs the new permissions; tenants stay separate
- [x] Both languages and phone width work
- [x] All tasks complete, validation passes, coverage at least 80%
- [x] Patterns mirrored, not reinvented

## Changes during build and review

- **Tasks follow the rooms, not each front desk action.** Instead of hooking every check-out, move and undo, the board brings today's tasks in line with the rooms each time it is read (at most every 15 seconds while a phone or the desk is open). Check-outs, moves, undo and room status changes all follow without extra code paths. The sync takes the property lock, reads fresh rows and locks the tasks, so a task a phone has just started is never overruled.
- **Earlier days.** Unfinished tasks move to today when the room still needs them, or when someone started or asked for them. A requested stay-over is dropped once the guest has left; tasks made automatically and not started are cancelled when no longer needed.
- **Same-day turnovers.** Only unfinished cleans count towards "one per room and day", so a room let and left twice in a day is cleaned twice.
- **Big buttons are saved on the staff profile**, so they follow the person to any phone.
- **Supervisor-only actions.** Marking a room inspected by hand needs `housekeeping:manage`. Clearing a problem needs `frontdesk:edit` or `housekeeping:manage`. Only the owner or a manager can give the manager role.
- **Guest details.** Housekeepers see the guest's name and requests only for their own rooms and rooms nobody has taken; supervisors and the front desk see all.
- **Sign-in redirects** accept only paths inside the app (this fixes an open redirect in the sign-in forms that the join link now relies on).
- **Join links** are one per email at a time (database index), so two clicks cannot make two links.
- **Known limits:** no email verification, so the join link is the real secret (one use, 7 days); no rate limits; the staff routes use the unscoped session like onboarding, filtering by tenant in every query; a housekeeper signing in normally lands on the dashboard, not the rooms page.
