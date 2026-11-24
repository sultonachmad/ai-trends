# Plan: Guest ID (Phase 2, Milestone 4)

**Source PRD**: `.claude/prds/phase-2-pms-core.prd.md`
**Selected Milestone**: 4 — Guest ID
**Complexity**: Large

## Summary

At check-in staff photograph or upload a guest's KTP or passport. A reader fills in the fields, and staff check and confirm every one before saving. Document numbers and images are encrypted, numbers are shown masked, every full view is logged, and images are deleted soon after check-out. Check-in then needs a confirmed ID for the main guest. This also gives Milestone 5 (APOA) the passport data it needs.

**Two things need your approval under the project rules** (D2): using the `cryptography` package, which is already installed as part of `python-jose` but not listed in the package register, and one new environment variable for the encryption key.

## What already exists, and the gaps

| Need | Today | Gap this milestone closes |
|---|---|---|
| ID records | `guestdocument` (KTP, passport, KITAS, KITAP, visa…; `doc_number_encrypted`, `doc_number_hash`, expiry, visa type, entry stamp, `verified_by`, `retention_until`) | Unused |
| Guests on a booking | `reservationguest` (primary flag, age category, registration status) | Unused; bookings only know the person who booked |
| Guest details | `guest.nationality`, `birth_date`, `gender` | Never filled |
| Images | `document` (kind `identity_scan`, classification `identity`, `retention_until`, `purged_at`), tenant-scoped file storage, the transfer-proof purge job | Files are stored unencrypted |
| Encryption | Nothing in the app; `cryptography` is installed but not in the package register | Needs approval and a key (D2) |
| Reader | Nothing | Simulated reader behind a switch, like the WhatsApp, payment and channel simulators |
| Check-in | Milestone 1 rules | No ID check |

## Decisions (recommendation first; reply "yes" to accept all)

| # | Question | Recommendation |
|---|---|---|
| D1 | Whose ID? | Every adult on the booking can have one. **Check-in needs a confirmed ID for the main guest.** For foreign guests every adult should have a passport; Milestone 5 flags anyone missing before APOA reporting |
| D2 | **Encryption (needs your approval)** | Use `cryptography` (already installed with `python-jose`; added to `packages-be.yaml`) to encrypt document numbers and images with AES-GCM. A keyed hash allows "this ID was seen before" without decrypting. **New variable `PREFAB_IDENTITY_KEY`**: a random 32-byte key in base64. In development the app derives one from `PREFAB_SECRET_KEY` and prints a loud warning, as it does for the default secret; **a real key must be set before the pilot**, and losing it makes stored numbers unreadable |
| D3 | The reader | A **simulated reader**, on only when `PREFAB_ID_READER_SIMULATOR_ENABLED` is set (development), returns clearly labelled sample fields. With it off, staff type the fields. A real provider plugs in later (PRD open question). **Every field is shown for staff to check, and saving needs an explicit "I have checked this against the document"** |
| D4 | Fields | KTP: NIK (16 digits with its built-in region and birth-date check), name, date of birth, gender. Passport: number, name, nationality, date of birth, gender, expiry (refused if expired), visa type (visa-free, VoA, B211A, KITAS, KITAP, other), entry date. Name, nationality and date of birth are copied to the guest's profile |
| D5 | Who sees what | New `guestid:view` (masked numbers like `3171••••••••0001`, no images) and `guestid:edit` (capture, confirm, **show full number or image, each view logged with who and when**). Both are in the manager role |
| D6 | Keeping images | Images are deleted **7 days after check-out** (time to fix mistakes) and the numbers stay. Images from cancelled or no-show bookings are deleted after 7 days too. Numbers and fields are kept until a retention date, **2 years after check-out by default, configurable, pending legal review** |
| D7 | Uploads | Phone camera or file, JPEG, PNG or WebP up to 5 MB, the same checks as transfer proofs |
| D8 | Seen before | A returning guest's existing confirmed ID is offered instead of a new scan, matched by the keyed hash |
| D9 | Where | A "Guests and ID" step in the front desk check-in, and on the booking detail. No new menu entry |

## Patterns to Mirror

| Category | Source | Pattern |
|---|---|---|
| Image upload | `backend/app/services/transfer_proofs.py:151` (`_check_upload`), `app/documents/images.py` | Type sniffing, size cap, content hash |
| File storage | `backend/app/documents/storage.py` | Tenant-folder keys, no path tricks |
| Purge job | `backend/app/services/proof_retention.py` | Tenant by tenant, stamps `purged_at`, keeps rows |
| Simulator switch | `backend/app/config.py:34-40`, start-up warnings in `app/main.py` | `*_SIMULATOR_ENABLED`, loud warning |
| Secret start-up check | `backend/app/security/startup_checks.py:27` | Refuse unsafe production settings |
| Refusals | `backend/app/services/front_desk_errors.py` | Stable codes |
| Tests | `backend/tests/pg/test_proof_upload_public.py`, `test_proof_retention.py`, `test_proof_isolation.py`, `test_front_desk.py` | Upload, permission, isolation, retention |

## Files to Change

| File | Action | Why |
|---|---|---|
| `backend/app/security/identity_crypto.py` | CREATE | Encrypt and decrypt numbers and files; keyed hash; key loading and start-up check |
| `backend/app/services/id_validation.py` | CREATE | Pure checks: NIK structure, passport number, expiry, nationality |
| `backend/app/services/id_reader.py` | CREATE | Reader interface and the simulated reader |
| `backend/app/services/guest_ids.py` | CREATE | Scan, confirm, list, reveal (logged), reuse, guests on a booking |
| `backend/app/services/id_retention.py`, `app/jobs/purge_ids.py` | CREATE | Delete images 7 days after the stay; clear numbers after the retention date |
| `backend/app/services/front_desk.py` | UPDATE | Check-in needs a confirmed main-guest ID |
| `backend/app/schemas/guest_ids.py`, `routers/guest_ids.py`, `app/main.py`, `config.py`, `security/startup_checks.py` | CREATE / UPDATE | `/api/bookings/{id}/guests…`, settings, switches and the key check |
| `backend/docs/rbac-spec.yaml`, `packages-be.yaml` | UPDATE | Permissions; `cryptography` |
| `backend/tests/test_id_validation.py`, `test_identity_crypto.py`, `tests/pg/test_guest_ids.py`, `test_id_retention.py` | CREATE | See Tasks |
| `frontend/components/guest-ids/*`, `lib/guest-ids-api.ts`, `lib/id-format.ts` + test | CREATE | Capture with camera, review form, masked list, reveal |
| `frontend/components/front-desk/*`, `components/bookings/BookingDetailDialog.tsx`, `lib/i18n.ts` | UPDATE | Check-in step, booking detail, `id` + `en` text |
| `components-be.yaml`, `components-fe.yaml`, the PRD | UPDATE | Registers and milestone status |

Migration `0017_guest_id_indexes` was added after the database review (see below); the tables and columns already existed.

## Tasks

Each backend task is test-first. Work on `feat/phase-2-m4-guest-id`, branched from `feat/phase-2-m3-tax-pack`.

### Task 1: Encryption and checks
- **Action**: AES-GCM for numbers and files, keyed hash, key from `PREFAB_IDENTITY_KEY` with the development fallback and a production refusal. NIK and passport checks.
- **Validate**: `uv run pytest tests/test_identity_crypto.py tests/test_id_validation.py -q`

### Task 2: Capture and confirm
- **Action**: Upload, simulated read, confirm with the "checked" flag, guest profile update, guests on a booking, reuse by hash, masked reads, logged reveals of number and image. Tests: nothing readable in the database or on disk without the key; reader switch off; bad NIK, expired passport; permissions for view and edit; tenant separation; every reveal logged.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_guest_ids.py -q`

### Task 3: Check-in and retention
- **Action**: Check-in refuses without a confirmed main-guest ID; images purged 7 days after check-out or cancellation; numbers cleared after the retention date; the purge runs at start-up and by hand.
- **Validate**: `REQUIRE_PG_TESTS=1 uv run pytest tests/pg/test_id_retention.py tests/pg/test_front_desk.py -q`

### Task 4: Frontend
- **Action**: Camera or file capture on a phone, the review form with every field and the "checked" tick, "SIMULATED" label, masked list with "show" that warns it is logged, check-in step, booking detail section, read-only without `guestid:edit`.
- **Validate**: `npx vitest run && npx tsc --noEmit && npm run lint`

### Task 5: Run, browser test, review
- **Action**: Full suites. Browser at phone width: check-in blocked, capture a KTP and a passport with the simulated reader, fix a field, confirm, check in; reveal a number and see it in the history; returning guest reuse; both languages; `devtest.sh errors`. Code, security and database review; fix critical and high findings. Update registers and mark the milestone complete.

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
| Identity data leaked | Medium | Encrypted at rest, masked by default, logged reveals, restricted permissions, images deleted after 7 days |
| Encryption key lost or left at the development fallback | Medium | Production refuses to start without a real key; the key must be backed up outside the server |
| Staff confirm wrong or simulated data | Medium | Every field shown, explicit "checked" tick, "SIMULATED" label, simulator off by default |
| Retention period is wrong for Indonesian law | Medium | Configurable; **legal review needed before the pilot** |
| Check-in blocked when a guest has no document | Medium | A person with `bookings:edit` can check in without ID with a reason, recorded in the history |
| Images contain more than needed (photo, address) | Medium | Only the listed fields are stored; the image goes after 7 days |

## Acceptance

- [x] Staff capture, check and confirm KTP and passport details at check-in
- [x] Numbers and images are encrypted; numbers are masked; every full view is logged
- [x] Check-in needs a confirmed ID for the main guest (or a permitted override with a reason)
- [x] Images are deleted 7 days after the stay; numbers after the retention date
- [x] Access needs `guestid:view` or `guestid:edit`; tenants stay separate
- [x] Both languages and phone width work
- [x] All tasks complete, validation passes, coverage at least 80%
- [x] Patterns mirrored, not reinvented

## Changes after review

- **D8 narrowed.** A number never pulls in another guest's profile or photo, and the "seen before" lookup was removed: it let anyone with `guestid:edit` read another person's details by typing a number. A returning guest needs no new scan when the booking uses the same guest profile (matched by phone, as bookings already do). Merging duplicate profiles is left for later.
- **One document per guest and type** (unique index): a corrected or renewed number replaces the old one, so a mistyped number does not linger. Two guests on one booking cannot hold the same number.
- **Masking** shows the last four characters only (`••••0001`); only those are stored in clear.
- **Ciphertext** is bound to tenant and row. Photos must be confirmed by the person who took them; at most 20 unconfirmed photos per person per day.
- **Retention** runs hourly while the app runs, in batches, and never shortens a photo's life while the guest has another stay going on. Every ID answer is sent `no-store`; a revealed number or photo hides after a minute.
- Passport nationality is required.
