# Plan: Maintenance and tax export (Phase 2, Milestone 8)

**Source PRD**: `.claude/prds/phase-2-pms-core.prd.md`
**Selected Milestone**: 8 — Maintenance and tax export
**Complexity**: Large

## Summary

Two parts. **Maintenance:** any staff member reports a repair from their phone (room or place, what is wrong, how urgent, a photo). A housekeeper's "needs repair" problem becomes a request by itself. A supervisor gives it to someone, and can take the room off sale for some nights. Channels and the front desk stop selling it, and it comes back, needing a clean, when the repair is done. **Tax export:** the owner picks a month and sees the service charge and PBJT due from the same numbers the guest bills use, day by day and booking by booking. They download it as a spreadsheet file for the regional tax return or their accountant.

## What already exists, and the gaps

| Need | Today | Gap this milestone closes |
|---|---|---|
| Repair requests | `workorder` table (number, room or place, category, priority, open → assigned → in progress → waiting parts → on hold → completed → verified → cancelled, reporter, assignee, guest-impacting, costs, photos) | Unused; "needs repair" from housekeeping is only a note |
| Room off sale | `unitblock` (room, out of order or out of service, from–until, reason, work order, active/released); `unit.service_status`; inventory `blocked` count per night, already used by imported calendars; the channel queue | Nothing writes them; check-in and room assignment already refuse a room out of order |
| Photos | The document store with image checks (transfer proofs, guest IDs) | Not used for repairs |
| Tax numbers | Every bill splits each night and line into base, service charge and PBJT by the rule of its own date (`services/bill_taxes.py`) | No month view or export (deferred here by Milestone 3) |
| Closed days | Milestone 6 closes days and freezes their money | The export does not say whether the month is closed |

## Decisions (recommendation first; reply "yes" to accept all)

### Maintenance

| # | Question | Recommendation |
|---|---|---|
| M1 | Who reports | Anyone with `maintenance:edit`. Housekeeper and front desk ready-made roles get it, so the people who find problems can report them |
| M2 | What a request holds | Room (or a place, such as "pool" or "lobby", as text), category (air conditioning, plumbing, electrical, furniture, TV and Wi-Fi, door and lock, other), **urgent** or normal, what is wrong, and **one optional photo** (image only, size limit as for ID photos) |
| M3 | From housekeeping | "Needs repair" on a cleaning task makes a request by itself, linked to the room and the task, so nothing is typed twice |
| M4 | Steps | Simplified on screen: **Open → Being fixed → Waiting (parts or outside help, with a note) → Fixed**, or **Cancelled** with a reason. Stored with the existing statuses. Numbered per property (MT-0001) |
| M5 | Who fixes it | A supervisor (`maintenance:manage`) gives it to a staff member, or writes the name of an outside repairer as text. No vendor accounts |
| M6 | Room off sale | From a request, a supervisor takes the room **off sale** for chosen nights (default today and tomorrow, can be extended). It is refused if a guest is in or booked into that room on those nights (move them first), or if selling would go below zero for any night (the refusal lists the nights). While off sale the room is out of order, the nights are blocked for the room type, and channels are told. **Back on sale** happens when the request is fixed, by hand, or when the last night passes. The room then needs a clean, which appears on the housekeeping board |
| M7 | Front desk | Urgent requests and rooms off sale show on the front desk until fixed. Rooms off sale show on the rooms tab |
| M8 | Cost | An optional cost and note when fixing it, for the owner's records. Charging a guest or owner for damage is deferred |
| M9 | Not now | Due times and escalation, recurring-problem detection, planned maintenance and equipment lists, vendor access codes (all later phases) |

### Tax export

| # | Question | Recommendation |
|---|---|---|
| T1 | Which numbers | The **same split the guest bills use**: each room night by its stay date and each extra by its date, with the tax rule of that date and the booking's price mode (nett or ++). Bookings that earn (confirmed, in house, checked out), as in the channel report. Untaxed extras are listed but carry no tax |
| T2 | Bookings paid through channels | Bills leave their tax out, because the channel collected the money. The summary **includes them in a separate column**, with tax worked out inside the price (as nett), marked "check with your tax office whether you or the channel reports these". Owners can then report either way **[verify per region]** |
| T3 | When a night counts | In the month it is stayed (or the extra is posted). PBJT may legally be due on payments received instead **[verify per region]**. The file says which basis it uses |
| T4 | Month status | The page shows how many days of the month are closed (Milestone 6). Until every day is closed, the file and the page say **DRAFT** |
| T5 | Format | Two downloads (UTF-8 spreadsheet files, safe against formulas): **by day** (date, room nights sold, room base, extras base, service charge, PBJT, total; channel column; month totals) and **by booking** (booking number, dates, source, price mode, base, service, PBJT; no guest names). Each regional return format (e-SPTPD) differs and is not public in a usable form, so this is a general layout to verify per region. Export to Jurnal or Accurate is deferred |
| T6 | Who and where | New `taxes:view` permission: owner and manager only (not front desk). A **Monthly tax** page under Reports. Every download is in the history (who, which month) |

### Permissions

`maintenance:view`, `maintenance:edit`, `maintenance:manage`, `taxes:view`. Manager holds all. Front desk and housekeeper get `maintenance:view` and `maintenance:edit`.

## Patterns to Mirror

| Category | Source | Pattern |
|---|---|---|
| Blocking nights | `backend/app/services/inventory.py` (`block_units`, `unblock_units`), `calendar_links.py:182` | Block per night under the property lock, then queue channel updates |
| Room status | `backend/app/services/unit_status.py` | One writer, logged |
| Read-time upkeep | `backend/app/services/housekeeping_tasks.py` (`sync_day`) | Bring state in line when read, under the property lock |
| Photos | `backend/app/services/guest_ids.py`, document storage | Image checks, stored privately, served to permitted users |
| Tax split | `backend/app/services/bill_taxes.py`, `tax_engine.py`, `tax_rules.py` | Rate of each date, price mode per booking |
| Safe spreadsheet file | `backend/app/services/apoa_register.py` (`plain`, `BOM`) | Formula-safe cells, UTF-8 BOM |
| Refusals and permissions | `housekeeping_errors.py`, `routers/housekeeping.py` | Stable codes; second permission in the route |
| Tests | `backend/tests/pg/test_housekeeping.py`, `test_channel_report.py` | HTTP client, permissions, tenant separation |
| Frontend | `app/(authenticated)/housekeeping/page.tsx`, `reports/page.tsx` | Phone-first lists, tested helpers, `id` + `en` text |

## Files to Change

| File | Action | Why |
|---|---|---|
| `backend/migrations/versions/0021_maintenance.py` | CREATE | Work order number per property, indexes for open requests and active blocks, task ↔ request link |
| `backend/app/services/maintenance.py`, `maintenance_blocks.py`, `maintenance_reads.py`, `maintenance_errors.py` | CREATE | Report, assign, steps, fix, cancel; off sale and back on sale; lists |
| `backend/app/services/housekeeping_work.py`, `housekeeping_tasks.py` | UPDATE | "Needs repair" makes a request; rooms come back on sale when their nights pass |
| `backend/app/services/tax_summary.py`, `tax_export.py` | CREATE | Month by day and by booking; spreadsheet files |
| `backend/app/schemas/maintenance.py`, `tax_summary.py`, `routers/maintenance.py`, `routers/tax_summary.py`, `app/main.py` | CREATE / UPDATE | `/api/maintenance/...`, `/api/tax-summary/...` |
| `backend/app/services/front_desk_reads.py`, `workspace_access.py`, `docs/rbac-spec.yaml` | UPDATE | Urgent requests on the desk; role codes; menu entries |
| `backend/tests/pg/test_maintenance.py`, `test_tax_summary.py` | CREATE | See Tasks |
| `frontend/app/(authenticated)/maintenance/page.tsx`, `components/maintenance/*`, `lib/maintenance-api.ts`, `lib/maintenance-format.ts` + test | CREATE | Report, list, steps, off sale |
| `frontend/app/(authenticated)/tax-summary/page.tsx`, `lib/tax-summary-api.ts`, `lib/tax-summary-format.ts` + test | CREATE | Month page and downloads |
| `frontend/app/(authenticated)/front-desk/page.tsx`, `components/housekeeping/*`, `middleware.ts`, `lib/i18n.ts` | UPDATE | Desk notices, "needs repair" link, routes, text |
| `components-be.yaml`, `components-fe.yaml`, the PRD | UPDATE | Registers and milestone status |

## Tasks

Each backend task is test-first. Work on `feat/phase-2-m8-maintenance-tax-export`, branched from `feat/phase-2-m7-housekeeping`.

### Task 1: Repair requests
- **Action**: Report (with optional photo), number, assign, steps, fix with optional cost, cancel with reason; "needs repair" from housekeeping makes one; urgent ones on the front desk. Tests: each step and refusal, the housekeeping link, photo checks, permissions, tenant separation.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_maintenance.py tests/pg/test_housekeeping.py -q`

### Task 2: Off sale and back on sale
- **Action**: Block nights, room out of order, channel updates, refusals (guest in or booked into the room; would go below zero), extend, back on sale when fixed, by hand or when the nights pass, then a clean is needed. Tests: availability and the channel queue go down and up again; check-in and assignment refuse the room; the refusals list the right bookings and nights; the room appears on the cleaning board afterwards.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_maintenance.py tests/pg/test_room_assignment.py tests/pg/test_channel_push.py -q`

### Task 3: Monthly tax summary
- **Action**: By day and by booking from the bill tax split, channel column, untaxed extras, closed-day status, two spreadsheet files, history entry. Tests: totals equal the sum of the bills' service and PBJT for the month in nett and ++; a rate change mid-month splits correctly; nights across the month end land in the right month; channel bookings only in their column; cancelled bookings left out; formula-safe cells; permission (front desk refused); tenant separation.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_tax_summary.py tests/pg/test_bill_taxes.py -q`

### Task 4: Frontend
- **Action**: Maintenance page (report sheet with camera, my and all requests, steps, off-sale dialog), "needs repair" linked from the cleaning task, front desk notices, Monthly tax page with month picker, totals, DRAFT state and downloads; both languages; phone width.
- **Validate**: `npx vitest run && npx tsc --noEmit && npm run lint`

### Task 5: Run, browser test, review
- **Action**: Full suites, migration up/down/up. Browser: a housekeeper reports "needs repair" with a photo; the supervisor takes the room off sale; the front desk cannot give it to a guest; fixed brings it back needing a clean. The owner opens the month and downloads both files, then reads them back. Both languages, `devtest.sh errors`. Code, security and database review; fix critical and high findings. Update registers and mark the milestone complete. A backend restart is needed to see the new menu entries.

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
| Tax figures differ from what the tax office expects (basis, channel bookings, format) | High | Same numbers as the bills; basis and channel treatment stated in the file; DRAFT until the month is closed; verify per region before the pilot (PRD open question) |
| A room taken off sale strands a booked guest | Medium | Refused while a guest is in or booked into the room; the refusal names the bookings |
| Channels keep selling a broken room | Medium | Same block and channel queue as imported calendars; tested |
| A room stays off sale after the repair | Low | Back on sale when fixed, and when the nights pass |
| Photos hold guest belongings or faces | Low | Stored privately like other documents; only maintenance users see them |

## Acceptance

- [x] Staff report a repair from a phone, with a photo; "needs repair" from housekeeping becomes a request
- [x] A supervisor assigns it, takes the room off sale for chosen nights, and it comes back needing a clean
- [x] Channels, check-in and room assignment respect a room off sale
- [x] The front desk sees urgent requests and rooms off sale
- [x] The owner sees a month's service charge and PBJT by day and booking, matching the bills, and downloads both files; DRAFT until the month is closed
- [x] Access needs the new permissions; tenants stay separate; downloads are in the history
- [x] Both languages and phone width work
- [x] All tasks complete, validation passes, coverage at least 80%
- [x] Patterns mirrored, not reinvented

## Changes during build and review

- **Off sale is checked everywhere.** Room assignment, the free-rooms list and check-in refuse a room with an active block on any night of the stay, not only a room out of order today. A block's nights use the same check-in and check-out times as a stay. The room turns out of order once its first night has begun (14:00), and back when the last night has passed, the request is fixed or cancelled, or a supervisor puts it back.
- **One block per room.** A second request cannot take a room off sale on nights another request already holds; the refusal names that request. Choosing other nights for the same request keeps the room's cleaning status.
- **Supervisors put rooms back on sale.** A request whose room is off sale can only be marked fixed by a supervisor. A request given to an outside repairer is no longer free for anyone to work.
- **Uploads.** The repairs route now has the same upload size limit as the other photo routes, before the body is read; a photo whose request is not saved is removed.
- **Locks.** Anything that adds a repair request (reporting, "needs repair" from cleaning) takes the property lock first, in the same order as the cleaning task sync, so the two cannot deadlock.
- **Tax month equals the bills.** Voided lines are excluded whatever date the void has (voids are same-day today; this keeps the month right if that ever changes).
- **Known limits:** tax basis (stays vs payments) and channel-booking reporting must be verified per region; the files are a general layout, not a regional form; no due times or escalation for repairs; no damage recharge to guests or owners; repair photos are kept with no retention rule yet.
