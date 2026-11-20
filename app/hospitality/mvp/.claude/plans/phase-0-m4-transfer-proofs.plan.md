# Plan: Phase 0 — Milestone 4: Transfer-Proof Verification

**Source PRD**: `.claude/prds/phase-0-whatsapp-wedge.prd.md`
**Selected Milestone**: 4 — Transfer-proof verification
**Complexity**: Large

## Summary

A guest who paid by manual bank transfer uploads the screenshot ("bukti transfer") on the pay page, or staff upload one a guest sent in chat. Staff open a review queue, see the image next to the expected amount, and approve or reject with a reason; approval marks the link paid, rejection is shown to the guest. Reused screenshots are flagged, large amounts need a second approver, and images are deleted 90 days after the decision. Staff can also record a transfer that had no link.

This is the first feature that stores files and accepts an upload from someone who is not signed in. One database migration; no new packages.

## Decisions needed before coding

| # | Decision | Recommendation | Why it matters |
|---|---|---|---|
| D1 | Where the guest transfers to | A small owner-only "Bank account" form (bank, account number, account holder) in a new Settings page; when filled in, the pay page offers "Manual bank transfer" and shows those details | Without it the pay page can accept a screenshot but cannot tell the guest where to send money. Today staff type account details into chat by hand |
| D2 | The second-approver rule cannot be exercised yet | Build and test the rule now (proofs above Rp 5.000.000 need two different staff; the owner may approve alone). Until staff can be invited, every workspace has only its owner, so the owner always approves alone | There is no "invite staff" feature in the PRD. The rule is tested with a second member created directly in the test database. Say if you want invitations added to this phase |
| D3 | Approving after the link has expired | Allowed: staff may approve a proof while the link is pending or expired, not when it is cancelled or already paid | Guests upload before the deadline and staff check later. Refusing would force staff to create a second link for money already received |
| D4 | How the guest learns of a rejection | The pay page shows "not accepted" with the reason and lets them upload again; if the link came from a conversation that can still be replied to, a chat message is also sent | The PRD says rejection tells the guest; the page always works, the chat message is best effort (24-hour window) |
| D5 | A screenshot that was already used | Flag it clearly to the reviewer ("this image was already submitted for …") and let them decide; do not block the upload | A guest may honestly resend the same image; a blocked upload gives staff nothing to look at |
| D6 | What files are accepted | JPEG, PNG or WebP, at most 5 MB, checked by content not by file name; at most 3 screenshots awaiting review per link. Size and count are configurable | Limits what an anonymous visitor can store, and keeps anything that is not an image out |
| D7 | Deleting images after 90 days | A clean-up step that runs when the app starts and can be run by hand or by a scheduler; no built-in timer | The app has no background scheduler. The image file is deleted and the record kept, as the PRD decided |
| D8 | Screenshots sent in chat | Staff save the image from WhatsApp and upload it from the conversation ("Record transfer proof") | WhatsApp is simulated and carries no images yet. Automatic intake comes with the real connection |
| D9 | Where files live | On the server's disk, one folder per tenant, behind the existing storage interface | Matches the upload prefab; object storage can replace it later without changing the feature |

## Requirements restated

- Pay page: when the property has bank details, the guest can choose manual transfer, see the details and amount, tick nothing extra, and upload a screenshot beside the agreed consent wording. Afterwards the page says the proof is being checked; later it shows paid or not accepted (with the reason and a way to upload again).
- Staff: a "Transfer proofs" page listing proofs waiting for review first, each with the image, expected amount, guest, link and any duplicate warning. Approve or reject with a required reason.
- Approval: marks the link paid (method "bank transfer"), records who approved and when. Above the threshold a non-owner's approval is a first approval; a different staff member (or the owner) completes it.
- Rejection: recorded with reason; the link stays payable; the guest is told (D4).
- Staff upload from a conversation, against one of that guest's pending links or with no link.
- No link: staff enter amount and what it was for, attach the screenshot, and the payment is recorded for review and approval like any other.
- Duplicate images within a tenant are flagged on every later use.
- Images are viewable only by staff of the owning tenant; never by link or guess.
- Images are deleted 90 days after the decision (configurable); the payment record stays.
- Staff screens and guest page in Bahasa Indonesia with an English switch.

## Patterns to Mirror

| Category | Source | Pattern |
|---|---|---|
| Naming | `backend/app/routers/payment_links.py:1`, `backend/app/services/payment_links.py:1`, `backend/app/schemas/payment_links.py:1` | router / service / schema triple per feature |
| Public, token-scoped routes | `backend/app/tenancy/public.py:44` (`get_public_link_scope`), `backend/app/routers/checkout.py:1` | Token resolves to a tenant-scoped session; identical 404 for any bad token |
| Token-path headers | `backend/app/security/token_paths.py:1` | No-store / no-referrer / noindex on every response under the prefix |
| Marking a link paid | `backend/app/services/gateway_events.py` (`handle_gateway_event`, `_capture`) | Lock the link first, then payments; capture; set link paid; cancel other open attempts; never apply twice |
| Money for a closed link | `backend/app/services/payment_links.py` (`NEEDS_REFUND_FLAG`, `_related`) | Recorded and surfaced to staff, not silently dropped |
| File storage | `backend/app/upload/storage.py:44` (`StorageBackend`), `:59` (`LocalStorage`), `:28` (`sanitize_filename`) | Storage behind a protocol; server-generated names; client file names never used on disk |
| Sending a chat message | `backend/app/services/inbox.py` (`send_reply`); `backend/app/services/payment_links.py` (`_send_to_chat`) | Best effort; refusals and faults reported, never raised past the caller |
| Errors | `backend/app/routers/payment_links.py:34` (`_guarded`) | Named service exceptions mapped to HTTP answers with their own `detail` |
| Configurable values | `backend/app/tenancy/business_settings.py` (`PropertySettings`) | New values with defaults and bounds; existing `second_approver_threshold_idr`, `proof_retention_days` |
| Startup steps | `backend/app/main.py` (lifespan: `assert_safe_configuration`, `assert_database_migrated`) | Small awaited step in the lifespan, failures logged clearly |
| Migration | `backend/migrations/versions/0005_payment_links.py` | Columns + tenant-safe FKs + model and design-SQL kept in step |
| Tests (backend) | `backend/tests/pg/test_payment_links.py`, `test_checkout.py`, `test_payment_review_fixes.py`, `conftest.py` helpers | One behaviour per test; signed-out `guest` client; second tenant client; scope probe |
| Frontend API / logic | `frontend/lib/checkout-api.ts`, `payment-links-api.ts`, `money.ts`, `payment-link-format.ts` (+ tests) | Typed calls; pure helpers with tests |
| Frontend screens | `frontend/app/(authenticated)/payment-links/page.tsx`, `frontend/app/pay/[token]/page.tsx`, `frontend/components/payments/*` | Small components; all text through `lib/i18n.ts`; timed re-fetch with stale-result guards |
| Upload widget | `frontend/components/UploadZone.tsx:7` | Shared drag-and-drop component (`onUpload`, `accept`) |
| Dialogs | `frontend/components/Dialog.tsx:33` | Shared `Dialog` for review and forms |

No existing pattern covers multipart upload through the shared `request` helper, image content checks, or a settings form; these are introduced here. The prefab's `/api/uploads` routes are not tenant-scoped and are not used.

## Files to Change

| File | Action | Why |
|---|---|---|
| `backend/migrations/versions/0006_transfer_proofs.py` | CREATE | `transferproof`: link, guest, conversation, amount, purpose, rejection reason, first approval, duplicate-of, consent time; `document.purged_at`; indexes |
| `.ttest/contexts/schema-tenant.sql` | UPDATE | Keep the design schema in step |
| `backend/app/models/tenant/payments/transfer_proof.py`, `organisation/document.py` | UPDATE | New columns |
| `backend/app/documents/__init__.py`, `storage.py`, `images.py` | CREATE | Tenant-folder storage; image type detection from content |
| `backend/app/services/transfer_proofs.py` | CREATE | Submit (guest / staff), list, read, approve, reject, duplicate check |
| `backend/app/services/proof_retention.py` | CREATE | Delete images past retention |
| `backend/app/services/property_settings.py` | CREATE | Read and update the bank account details |
| `backend/app/services/checkout.py`, `payment_links.py` | UPDATE | Manual transfer on the public view; proof state on a link |
| `backend/app/schemas/transfer_proofs.py`, `settings.py` | CREATE | Shapes with validation |
| `backend/app/routers/transfer_proofs.py` | CREATE | Staff: list, read, image, upload, approve, reject |
| `backend/app/routers/checkout.py` | UPDATE | Public: `POST /api/pay/{token}/proofs` |
| `backend/app/routers/settings.py` | CREATE | `GET` / `PUT /api/settings/bank-account` (owner only for `PUT`) |
| `backend/app/tenancy/business_settings.py` | UPDATE | Bank account details, max upload size, max proofs awaiting review |
| `backend/app/main.py`, `backend/docs/rbac-spec.yaml` | UPDATE | Routers, start-up clean-up, menu entries |
| `backend/tests/test_image_detection.py`, `test_document_storage.py` | CREATE | Unit tests |
| `backend/tests/pg/test_transfer_proofs.py`, `test_proof_upload_public.py`, `test_proof_approval.py`, `test_proof_isolation.py`, `test_proof_retention.py`, `test_bank_settings.py` | CREATE | Integration tests |
| `backend/tests/pg/conftest.py`, `backend/tests/test_business_settings.py`, `test_hospitality_models.py` | UPDATE | Helpers, additions |
| `frontend/lib/transfer-proofs-api.ts`, `settings-api.ts`, `proof-format.ts` (+ test) | CREATE | Typed calls and helpers |
| `frontend/lib/api-client.ts`, `checkout-api.ts` | UPDATE | Multipart upload through the shared helper; public proof upload |
| `frontend/components/proofs/ProofReviewDialog.tsx`, `ProofList.tsx`, `ProofUploadForm.tsx`, `ProofImage.tsx` | CREATE | Page parts |
| `frontend/app/(authenticated)/transfer-proofs/page.tsx` | CREATE | Review queue |
| `frontend/app/(authenticated)/settings/page.tsx` | CREATE | Bank account form |
| `frontend/app/pay/[token]/page.tsx`, `components/payments/PaymentInstructions.tsx` | UPDATE | Manual transfer details, upload with consent, checking / rejected states |
| `frontend/app/(authenticated)/inbox/page.tsx`, `dashboard/page.tsx`, `payment-links/…` | UPDATE | "Record transfer proof" in a thread; counts and links |
| `frontend/lib/i18n.ts`, `frontend/middleware.ts` | UPDATE | Strings; protect the new pages |
| `components-be.yaml`, `components-fe.yaml` | UPDATE | Register new artifacts |

## Tasks

Each task is test-first.

### Task 1: Migration 0006 and models
- **Action**: Add the columns and indexes; update models and design SQL. No constraint value changes are needed (`pending`, `manually_confirmed`, `rejected`, `staff_upload`, `portal` already exist).
- **Mirror**: `backend/migrations/versions/0005_payment_links.py`.
- **Validate**: upgrade → downgrade → upgrade on an empty database; `alembic check` clean; design SQL applies.

### Task 2: Files — storage and image checks
- **Action**: Tenant-folder storage on the existing protocol (random names, path kept inside the tenant folder). Detect JPEG / PNG / WebP from the first bytes; reject everything else, empty files and oversize files; SHA-256 of the content.
- **Mirror**: `backend/app/upload/storage.py:59`.
- **Validate**: unit tests — each accepted type, a renamed non-image, an HTML or SVG file posing as an image, empty, oversize, traversal attempts in the file name.

### Task 3: Bank account settings
- **Action**: Bank name, account number (digits, bounded length), holder name in `PropertySettings`; `GET /api/settings/bank-account` for members, `PUT` for the owner only; the public link view exposes them only when complete.
- **Mirror**: `backend/app/tenancy/business_settings.py` (`with_property_overrides`).
- **Validate**: owner saves and reads back; non-owner `PUT` → 403; invalid account number → 422; pay page shows manual transfer only when configured.

### Task 4: Guest upload
- **Action**: `POST /api/pay/{token}/proofs` (multipart: file, `consent=true`). Refused unless the link is pending, consent is given and fewer than the allowed number are awaiting review. Stores the file, a `document` (kind `transfer_proof`, classification `financial`), a payment awaiting verification and the proof with consent time. The public view reports the latest proof's state and, when rejected, its reason.
- **Mirror**: `backend/app/routers/checkout.py`; `backend/app/services/checkout.py` (`start_payment`).
- **Validate** (`test_proof_upload_public.py`): happy path without sign-in; missing consent → 422; non-image, oversize, empty → 422; fourth pending upload → 429; paid / expired / cancelled link → 409; bad token → the same 404; response reveals no ids, file paths or other proofs; privacy headers present.

### Task 5: Staff upload and transfers without a link
- **Action**: `POST /api/transfer-proofs` (multipart) with either a pending `payment_link_id`, or `amount` + `description` (optionally a `conversation_id`) for a transfer that had no link.
- **Mirror**: `backend/app/services/payment_links.py` (`create_link` validation).
- **Validate**: against a link; without a link (amount limits apply); unknown or foreign link / conversation → 404; both or neither of link and amount → 422.

### Task 6: Review queue and image access
- **Action**: `GET /api/transfer-proofs` (state filter: awaiting, approved, rejected; paged, awaiting first), `GET /{id}`, `GET /{id}/image` (staff of the tenant only; correct content type, `nosniff`, no caching; 410 with its own message once purged). Each item carries expected amount, guest, link, who uploaded, first approval if any, and duplicate warning.
- **Mirror**: `backend/app/services/payment_links.py` (`list_links`, `_related`).
- **Validate**: ordering, paging, filter; image bytes round-trip; image of another tenant → 404; unauthenticated → 401; constant query count for a page.

### Task 7: Approve and reject
- **Action**: `POST /{id}/approve`, `POST /{id}/reject` (reason required). Approval under the link lock: threshold and approver rules (D2), then capture the payment as bank transfer, mark the link paid, cancel other open attempts, set the image's deletion date. Link already paid or cancelled → refused with its own message. Rejection: reason stored, payment closed, link untouched, guest told (D4). Both are final and cannot be repeated.
- **Mirror**: `backend/app/services/gateway_events.py` (lock order, `_capture`).
- **Validate** (`test_proof_approval.py`): approve marks link paid with "Bank transfer"; expired link can still be approved (D3); already-paid and cancelled links refuse; above threshold — staff then different staff completes, same staff twice refused, owner alone completes; at exactly the threshold one approval suffices; reject keeps link pending and shows the reason on the pay page; chat notice sent when possible and its failure does not fail the rejection; approving or rejecting twice → 409; two simultaneous approvals pay once; proof with no link is approved into a captured payment.

### Task 8: Duplicates, isolation, retention
- **Action**: Duplicate = same content hash already on another proof in the tenant; flagged on every later one. Retention: `purge_expired_proofs()` deletes image files whose deletion date has passed and stamps `purged_at`; runs at start-up (errors logged, never blocking start) and as `python -m app.jobs.purge_proofs`.
- **Validate**: second use of an image is flagged, first is not, another tenant's identical image is not; cross-tenant 404 on every staff route and the image route; scope probes; purge removes only due files, keeps records, is safe to run twice, and a missing file does not stop the run.

### Task 9: Frontend logic
- **Action**: Multipart support in the shared request helper (no JSON content type for form data); API modules; `proof-format.ts` (state label, needs-second-approval text, file checks before upload); i18n keys in both languages including the agreed consent wording.
- **Validate**: `npx vitest run`.

### Task 10: Staff screens
- **Action**: `/transfer-proofs`: queue with thumbnails, review dialog (image beside expected amount, guest, link, duplicate warning, first-approval note), approve / reject with reason; "Record transfer proof" in an inbox thread and on the page; `/settings` bank account form; dashboard shows proofs awaiting review; menu entries "Transfer proofs" and "Settings".
- **Mirror**: `frontend/app/(authenticated)/payment-links/page.tsx`; `frontend/components/UploadZone.tsx`; `frontend/components/Dialog.tsx`.
- **Validate**: `npx tsc --noEmit && npm run lint`.

### Task 11: Guest page
- **Action**: Manual transfer option with the bank details and amount (copy buttons); upload form with the consent wording beside the button; "being checked", "not accepted — reason — upload again" and paid states; phone width.
- **Mirror**: `frontend/app/pay/[token]/page.tsx`; `frontend/components/payments/PaymentInstructions.tsx`.
- **Validate**: `npx tsc --noEmit && npm run lint`.

### Task 12: Run, browser test, review
- **Action**: Per CLAUDE.md "Run and Test After Every Change": start with `scripts/devtest.sh`; with Playwright — save bank details, create a link, open it signed-out at phone width, choose manual transfer, upload an image, see "being checked"; as staff review and reject, see the reason on the guest page, upload again, approve, see paid on both sides; upload the same image for another link and see the duplicate warning; record a transfer with no link from a conversation; try a non-image; both languages; console and `devtest.sh errors` clean; stop. Then security review (file upload from an anonymous visitor, stored personal and financial images: mandatory) and code review; fix critical and high findings. Update registers; mark the milestone complete.
- **Validate**: flow works, log clean, reviews have no open critical or high findings.

## Validation

```bash
cd backend
uv run ruff check app/documents app/services app/routers app/schemas app/tenancy tests
uv run pytest -q
uv run pytest -q --cov=app/documents --cov=app/services --cov=app/schemas --cov=app/tenancy --cov-report=term-missing
uv run alembic upgrade head && uv run alembic check

cd ../frontend
npx vitest run && npx tsc --noEmit && npm run lint

cd .. && bash scripts/devtest.sh start   # Playwright walk-through, `bash scripts/devtest.sh errors`, `stop`
```

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Anonymous visitors use the upload to store or serve harmful files | Medium | Images only, detected from content; size and count limits; random server-side names; files never served publicly, only to signed-in staff of the tenant, with a fixed content type and `nosniff` |
| A screenshot is fake or edited and staff approve it | Medium | Expected amount shown beside the image; duplicate warning; approver recorded; second approver above the threshold. Automatic checks are out of scope (PRD) |
| The two-person rule gives false comfort while every workspace has one member | High | Stated in D2; the owner-alone path is the PRD's own rule; surfaced again in the summary |
| No rate limiting on a public upload | High | Per-link cap and size cap bound storage per link; the 256-bit token bounds who can upload at all; rate limiting stays the open follow-up, now the most pressing one |
| Personal and financial images kept longer than promised | Medium | Deletion date stamped at decision; clean-up at every start-up and runnable on a schedule; test proves due files are removed |
| Files on local disk are lost or not shared between servers | Medium | Acceptable for the pilot on one server; storage sits behind the existing interface for a later move to object storage |
| A proof is approved for a link already paid by QRIS / VA | Low | Approval refused with a clear message; staff reject the proof and handle the refund outside the product |
| Chat notice of a rejection fails | Medium | Best effort; the pay page always shows the reason |
| Settings page grows beyond bank details | Low | This milestone adds only the bank account form |

## Out of this milestone

Automatic reading of screenshots (amount, bank, date), tamper detection, bank-statement import and matching, images arriving through WhatsApp, refunds, inviting staff, editing other business settings, receipts, object storage, free-plan limit enforcement (milestone 5).

## Acceptance
- [ ] All tasks complete
- [ ] Validation passes
- [ ] Patterns mirrored, not reinvented
- [ ] A guest can upload a transfer screenshot without signing in; staff can reject it with a reason the guest sees, then approve a new one, and the link shows paid on both sides
- [ ] Images are reachable only by staff of the owning tenant, and are deleted after the retention period while the payment record stays
