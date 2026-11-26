# Plan: APOA reporting (Phase 2, Milestone 5)

**Source PRD**: `.claude/prds/phase-2-pms-core.prd.md`
**Selected Milestone**: 5 — APOA reporting
**Complexity**: Medium

## Summary

Every foreign guest who checks in must be reported to Imigrasi in the APOA app, and checked out in APOA when they leave. This milestone gives staff one list of who still needs reporting, the passport photo ready to upload into APOA, and a named, timed record each time they report. Overdue guests are flagged on the front desk. Staff still submit in the official APOA app; the product does not claim to submit for them.

## What APOA actually takes (checked 26 Nov 2026)

From the official APOA user guide for hotels (Imigrasi Yogyakarta, Sep 2025, by Bit Group) and the Imigrasi news release of 26 Mar 2025:

- **Check-in**: staff scan the guest's passport with the APOA phone app, which reads it, at the hotel (GPS within 50 m of the registered location). Or "Manual Check In": upload a passport photo or PDF (JPEG, PDF, PNG). **APOA reads the fields itself**: there is no form to type into.
- **Check-out**: in APOA, choose the guest under "On Going" and press Check Out.
- **No import, file format or API**: only the app, plus APOA's own export of its data.
- **Deadline: not stated** in either source. The legal basis cited is Law 6/2011 Art. 72 (as amended by Law 6/2024), with a sanction of up to 3 months' detention or a Rp25 million fine.

So the PRD's "data prepared in APOA's field order" does not fit how APOA works. What helps staff is a **worklist**, the **passport photo ready to upload** (from Milestone 4) and a **record of who reported what and when**. I update the PRD's scope line to say this.

## What already exists, and the gaps

| Need | Today | Gap this milestone closes |
|---|---|---|
| Report records | `foreignguestreport` (per guest on a booking: arrival / departure kind, method, status, due time, submitted at and by, reference, payload); `ix_foreignguestreport_due` | Unused |
| Foreign guests | Milestone 4: passports with nationality, visa, entry date; guests on a booking | Nobody sees who still needs reporting |
| Passport photo | Encrypted, kept 7 days after the stay, logged "show photo" | Not offered for APOA upload |
| Check-in and check-out times | `reservationunit.checked_in_at`, `checked_out_at` | Not used for deadlines |

## Decisions (recommendation first; reply "yes" to accept all)

| # | Question | Recommendation |
|---|---|---|
| D1 | Who must be reported | Every guest on an in-house or checked-out booking whose confirmed document is a **passport with a nationality other than Indonesia**. KTP holders and Indonesian passports are never listed. A booking with **fewer listed guests than its guest count** is flagged "guests not registered", since an unlisted foreigner cannot be reported |
| D2 | What is tracked | Two steps per guest: **checked in to APOA** after check-in, **checked out of APOA** after check-out. Each is marked by staff with an optional APOA receipt reference ("Surat Tanda Terima") and recorded with who and when |
| D3 | Deadline | **24 hours after check-in** (and after check-out), as a property setting, labelled **"not confirmed by Imigrasi"** because neither source states one (PRD open question). Overdue items are shown in red and counted on the front desk |
| D4 | The passport photo | A "Passport photo for APOA" button downloads the stored photo so staff can use APOA's Manual Check In. It needs `guestid:edit` and is **logged like any photo view**. Without a photo, staff scan the real passport in APOA |
| D5 | Not required, and mistakes | "Not required" with a reason (for example the guest left before check-in was finished) and "undo a mark" with a reason, both by `apoa:edit` and in the history. A guest added after check-in appears in the list at once |
| D6 | Where | A new **"Foreign guests (APOA)"** page under Reservations, phone-first, with tabs **To report**, **To check out** and **Done**. The front desk shows a banner when something is due or overdue |
| D7 | Permissions | New `apoa:view` (the list, masked numbers) and `apoa:edit` (mark, not required, undo). Both are in the manager role. The photo still needs `guestid:edit` |
| D8 | Register for inspection | A **CSV export of the APOA register** for a date range (guest, nationality, passport ••••last4, visa, stay dates, reported at and by, checked out at and by). Article 72 obliges the property to give this to an immigration officer on request. Full numbers are **not** in the export |
| D9 | Stored record | Each mark stores what was reported: name, nationality, doc type, last four digits, visa, entry date and room. Never the full number |

## Patterns to Mirror

| Category | Source | Pattern |
|---|---|---|
| Reads for a day's work | `backend/app/services/front_desk_reads.py:184` (`read_today`) | One read per tab, by property date |
| Refusals | `backend/app/services/guest_id_errors.py` | `FrontDeskError` subclass with a stable `code` the page translates |
| Permission routes | `backend/app/routers/guest_ids.py`, `routers/front_desk.py:46` | `require_permission`, `_guarded`, `no-store` for identity data |
| History | `backend/app/services/tenant_audit.py:50` | `record` inside the transaction |
| Settings | `backend/app/tenancy/business_settings.py` (`id_image_retention_days`) | A bounded business value |
| Logged photo | `backend/app/services/guest_id_reads.py` (`read_image`) | Log, commit, then return |
| Menu | `backend/docs/rbac-spec.yaml` (Reservations group) | A child entry with `permission:` |
| Tests | `backend/tests/pg/test_guest_ids.py`, `test_front_desk.py` | HTTP client, permission and tenant cases |
| Frontend | `frontend/app/(authenticated)/front-desk/page.tsx`, `components/guest-ids/*`, `lib/id-format.ts` | Tabs, cards, tested helpers, text in `lib/i18n.ts` |

## Files to Change

| File | Action | Why |
|---|---|---|
| `backend/app/services/apoa.py` | CREATE | Who needs reporting, deadlines, mark / not required / undo, register export |
| `backend/app/services/apoa_errors.py`, `schemas/apoa.py`, `routers/apoa.py`, `app/main.py` | CREATE / UPDATE | `/api/apoa/...` |
| `backend/app/tenancy/business_settings.py` | UPDATE | `apoa_deadline_hours` (default 24, 1–72) |
| `backend/app/services/front_desk_reads.py`, `schemas/front_desk.py` | UPDATE | APOA due and overdue counts for the banner |
| `backend/docs/rbac-spec.yaml` | UPDATE | `apoa:view`, `apoa:edit`, menu entry |
| `backend/tests/pg/test_apoa.py` | CREATE | See Tasks |
| `frontend/app/(authenticated)/apoa/page.tsx`, `components/apoa/*`, `lib/apoa-api.ts`, `lib/apoa-format.ts` + test | CREATE | Page, cards, helpers |
| `frontend/app/(authenticated)/front-desk/page.tsx`, `lib/i18n.ts` | UPDATE | Banner, `id` + `en` text |
| `components-be.yaml`, `components-fe.yaml`, the PRD | UPDATE | Registers, scope line, milestone status |

Migration `0018_apoa_indexes` was added after the database review (see below).

## Tasks

Each backend task is test-first. Work on `feat/phase-2-m5-apoa`, branched from `feat/phase-2-m4-guest-id`.

### Task 1: The worklist
- **Action**: For the property, list foreign guests on in-house and recently checked-out bookings with their APOA check-in and check-out state, due time and overdue flag; bookings with unlisted guests. Tests: KTP and Indonesian passports never listed; a companion added later appears; due = check-in + setting; overdue after it; checked-out guests move to "to check out"; cancelled and no-show bookings never listed; tenant and property separation.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_apoa.py -q`

### Task 2: Marking and the register
- **Action**: Mark checked in / checked out in APOA (optional reference), not required with a reason, undo with a reason; each in the history with what was reported (no full number). Checked out only after checked in (or not required). The passport-photo download reuses the logged image read. CSV register by date range, masked. Tests: double marks refused, order enforced, undo restores, permissions (`apoa:view`, `apoa:edit`, photo needs `guestid:edit`), the register holds no full numbers.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_apoa.py -q`

### Task 3: Front desk banner
- **Action**: Today's desk shows counts of APOA items due and overdue, linking to the page.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_front_desk.py tests/pg/test_apoa.py -q`

### Task 4: Frontend
- **Action**: Phone-first page with the three tabs, overdue in red, "Passport photo for APOA", mark buttons with optional reference, not required and undo with reasons, register download; front desk banner; "deadline not confirmed by Imigrasi" note; both languages.
- **Validate**: `npx vitest run && npx tsc --noEmit && npm run lint`

### Task 5: Run, browser test, review
- **Action**: Full suites. Browser at phone width: check in a foreign guest, see it due and then overdue (setting lowered), download the photo, mark checked in with a reference, check out at the desk, mark checked out in APOA, undo one mark, export the register; both languages; `devtest.sh errors`. Code, security and database review; fix critical and high findings. Update registers, the PRD scope line and mark the milestone complete. A backend restart is needed to see the new menu entry.

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
| The real deadline differs from 24 hours | High | A setting, labelled unverified; **confirm with Imigrasi before the pilot** |
| Staff mark "reported" without doing it in APOA | Medium | Named and timed record, optional APOA receipt reference, the page says submission happens in APOA |
| A foreign guest is never entered, so never listed | Medium | "Guests not registered" flag when listed guests are fewer than the guest count |
| The passport photo spreads further | Medium | Same `guestid:edit` gate and view log as Milestone 4; never in the export |
| APOA changes its flow | Low | Only marks are stored; no dependency on APOA fields |

## Acceptance

- [x] Staff see which foreign guests still need checking in or out of APOA, with overdue flagged
- [x] Each step is marked with who, when and an optional APOA reference, and can be undone with a reason
- [x] The passport photo can be downloaded for APOA, logged
- [x] The front desk shows what is due or overdue
- [x] A masked register can be exported for an immigration officer
- [x] Access needs `apoa:view` or `apoa:edit`; tenants stay separate
- [x] Both languages and phone width work
- [x] All tasks complete, validation passes, coverage at least 80%
- [x] Patterns mirrored, not reinvented

## Changes after review

- **Front desk undo** of a check-in or check-out is refused while an APOA step is recorded ("undo it on the APOA page first"); taking back a check-in clears pending APOA records. Otherwise the records would no longer match the stay.
- **A skipped (not required) APOA check-in needs no APOA check-out**; trying gives a clear message.
- **Front desk counts** are computed only for staff with `apoa:view`, from a lighter set of queries, and a fault there never breaks the front desk.
- **The list** shows in-house stays first and newest first, up to 1,000 stays, and says so when it is cut short.
- **The register** download is recorded in the history, capped at 20,000 guests, uses property local times and a UTF-8 marker for spreadsheets, and makes formula-like cells plain text.
- **Retention**: when an ID number is cleared, the passport details (last four digits, visa, entry date) are also removed from that guest's APOA records.
- Reasons and receipt numbers refuse text-direction and line-separator characters.
- Migration `0018_apoa_indexes`: open and recent stays; reports by guest and by document.
