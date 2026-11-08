<!-- Prefab: audit-evidence v0.1.0 -->

# Audit-Evidence Prefab — Agent Instructions

This prefab adds an append-only, hash-chained audit trail to the Next.js + FastAPI base. It
realises a DS-3 `audit_evidence_model` design: every audited action is written once, chained to
the entry before it, and never blanket-immutable — the one legitimate mutation is the erasure
workflow (right-to-erasure / GDPR-style requests), which is deliberately narrow and itself
produces an audit trail entry.

## Architecture & File Structure

```text
backend/
  app/audit/
    events.py     # Declarative event registry (id, subject_entity, origin, sensitivity)
                   #   import-time auto-seed pattern (as rbac does for permissions)
    models.py      # SQLModel table: AuditEntry (audit_entries) — the hash-chained ledger
    service.py     # append() — runs on its OWN connection/transaction, AUDIT_WRITE_MODE
    erasure.py      # anonymise() — the ONLY mutation surface — and verify()
    router.py       # query endpoint (audit_read_dep), verify endpoint, retention purge
```

## Threat model (verbatim — do not weaken when customising this prefab)

- The hash chain is **tamper-EVIDENT, not tamper-proof.**
- An actor with DB write access can recompute the chain.
- The HMAC is forgeable by whoever holds config + DB.
- `verify()` recomputes the chain over **pinned columns** — all columns EXCEPT `anonymised` and
  `subject_key` (see "Pinned columns" below).

Read that block again before changing `service.py`'s digest computation or `erasure.py`'s
pinned-column set — weakening either one silently defeats the tamper-evidence guarantee this
prefab exists to provide.

### Concurrency

`prev_hash` carries a `UNIQUE` constraint. Two concurrent `append()` calls both read the same
chain head; the first to commit wins, the second gets an `IntegrityError` and retries with the
updated head (up to `_MAX_CHAIN_RETRIES` times). This is the DB-enforced linearisation that
prevents false-positive tamper alarms from legitimate concurrent writes.

**Genesis-row caveat:** the linearisation relies on `UNIQUE(prev_hash)`, but PostgreSQL treats
NULLs as distinct by default (`NULLS DISTINCT`), so two concurrent appends to an *empty* table
both write `prev_hash=NULL` and both commit — the chain forks at row 1. This is a narrow
cold-start window (steady-state appends always carry a non-NULL `prev_hash` and are fully
covered). A production deployment that expects concurrent first writes should seed the table
with a genesis row before accepting traffic, or add a `NULLS NOT DISTINCT` qualifier to the
constraint (PostgreSQL 15+).


### What this DOES and does NOT protect against

- **Detects:** accidental corruption, naive row edits/deletes, and any tampering that does not
  also recompute the downstream chain and re-sign with the same HMAC key.
- **Does NOT detect:** a privileged actor (DB admin, anyone holding the app's `SECRET_KEY` plus
  DB write access) who rewrites the whole table and recomputes a consistent chain from scratch.
  There is no external anchor in v1 — periodic anchored digests (exporting the head hash to
  storage outside this database) are a named follow-up, not v1 scope.
- **HMAC key reuse:** this prefab signs both the entry chain and anonymisation records with the
  generated project's `settings.SECRET_KEY` (the same key auth-session uses to sign session
  cookies). Rotate that key and every existing entry's digest becomes unverifiable against a
  freshly-computed one — this is expected, not a bug, and mirrors the session-signing tradeoff
  auth-session already accepts.

## Write-path semantics — `AUDIT_WRITE_MODE`

Audit `append()` always runs on its own DB connection/transaction, separate from the caller's
business transaction — an audit entry never rides inside the same commit as the business write it
documents. `AUDIT_WRITE_MODE` (env-tunable, read once in `service.py`) controls what happens when
that separate append fails:

- **`fail_closed` (DEFAULT)** — the business request fails when the audit append fails. Audit
  writes are effectively on the critical path even though they use a separate connection: no
  audited action is allowed to succeed silently un-audited.
- **`spool`** — the business write completes; the append is retried from a local spool, and the
  failure surfaces loudly (logged, not swallowed) rather than blocking the caller. Use this only
  when the generated project has an explicit product decision that audit availability must not
  gate the business path.

If your project's own DS-3 `write_path` contract fixes different semantics, port those instead —
and record the deviation (and its source) in this file, in place of the paragraph above.

## Pinned columns — what `verify()` recomputes over

Every `AuditEntry` row's `entry_hash` is an HMAC-SHA256 digest over a **pinned column set**,
chained to the previous row's `entry_hash` (`prev_hash`). The pinned set is **all columns EXCEPT
`anonymised` and `subject_key`** — but "all columns" is pinned as an EXPLICIT tuple
(`service.PINNED_FIELDS`), not computed by introspecting the model and subtracting two names.

`PINNED_FIELDS` covers the DS-3 record's own columns: `event_id`, `actor_id`, `occurred_at`,
`payload`, `request_id`, `session_id`, `prev_hash`. It deliberately does NOT include the
`BaseEntity` bookkeeping columns (`id`, `created_at`, `updated_at`, `created_by`, `updated_by`):

- `id` is not known until after insert (autoincrement), so it cannot be part of a digest computed
  before the row exists;
- `updated_at` / `updated_by` are refreshed by SQLAlchemy's `onupdate` on ANY update to the row —
  including the erasure UPDATE. If either were in the pinned set, `verify()` would break on every
  erased row for exactly the same reason `anonymised`/`subject_key` are excluded. This is why the
  set is an explicit tuple rather than "every column except N names": "except" lists are easy to
  under-count when a mixin (here, `BaseEntity`) contributes columns that mutate for reasons
  unrelated to the ones you were thinking about when you wrote the exclusion list.

`anonymised` and `subject_key` are excluded from `PINNED_FIELDS` for the same underlying reason —
they are the two columns `erasure.anonymise()` is allowed to mutate. If you add a new domain
column to `AuditEntry`, add it to `PINNED_FIELDS` unless it is also something erasure (or some
other legitimate post-insert process) is meant to mutate — and if it is, re-read this section
before assuming excluding it is enough; check whether it drags in a mixin side effect too.

## Inherited limitation — `auth-session` is POC-grade

This prefab's `requires: [base-nextjs-fastapi, auth-session]` pulls in `auth-session`'s in-memory
session store (`template/backend/app/session/store.py` in that prefab) — sessions live in process
memory, are lost on restart, and are not shared across worker processes. `audit_read_dep` (see
below) authenticates the caller through that same session mechanism, so it inherits the same
POC-grade limitation: it is not a multi-worker-safe authorization boundary until the generated
project swaps `auth-session`'s store for a shared backing store (Redis, as that prefab's own
AGENTS.md documents).

## `audit_read_dep` — auto-wiring to `rbac`

`router.py` builds `audit_read_dep` once, at import time:

- **If `app.rbac.dependencies` is importable** (the `rbac` prefab is installed in this project),
  `audit_read_dep` is `require_permission("audit:read", ...)` — real permission-gated access,
  with the admin-role bypass rbac already provides.
- **Otherwise**, `audit_read_dep` falls back to `get_current_user` — any authenticated session can
  read the audit trail. This fallback is intentionally permissive (fail-open on
  *authorization*, fail-closed on *authentication*): a generated project running without `rbac`
  gets audit read access gated by login only, not by an audit-specific permission. Install `rbac`
  before shipping if that authorization boundary matters for your project.

**⚠️ Purge fallback — destructive endpoint, same fail-open pattern.** The retention-purge endpoint
(`POST /retention/purge`) uses a second dependency, `audit_admin_dep`, built the same way over
`"audit:retention"`. Without `rbac`, ANY authenticated user can trigger `retention/purge` — which
anonymises rows irreversibly (PII shred). This is a much higher-impact fallback than the read side.
Install `rbac` before shipping if the purge authorization boundary matters for your project.

## Known limitations

- **`verify()` and `purge_expired()` are O(n) in memory.** Both load the full `audit_entries`
  table into a Python list (`list(result.all())`). At scale (10⁵+ rows), this risks OOM and long
  transaction locks. Production deployments should add cursor-based pagination or streaming before
  the table grows past a few hundred thousand rows.
- **Spool mode is in-process only.** `_SPOOL` is a plain Python list — entries queued in `spool`
  mode are lost on process restart and not shared across worker processes. Back it with a durable
  queue (Redis, SQS, etc.) for production use.
- **Retention requires an external scheduler.** The `POST /retention/purge` endpoint runs the
  purge synchronously when called — there is no built-in cron. Forget to wire a scheduler and PII
  may be retained indefinitely.
- **`occurred_at` is not indexed.** `purge_expired()` filters by `occurred_at` in Python after a
  full table scan. Add a DB index on `occurred_at` if retention purge performance matters.

## Not v1 scope (named follow-ups)

- Periodic anchored digests (head-hash export to external storage) — strengthens the
  tamper-evidence guarantee beyond "detects corruption inside this DB" toward "detects a
  privileged DB rewrite too."
- A frontend audit-log viewer page. This prefab is backend-only in v1; query the endpoints
  directly or build a viewer in the generated project.
- MFA / identity-lifecycle event emission — this prefab only stores and chains events; DS-4/DS-5
  concerns (who counts as authenticated, what counts as an identity-lifecycle event) live in the
  auth/rbac prefabs, not here.

## Workflow: adding a new audited event

1. Add an `AuditEventDef` to `app/audit/events.py` via `register_event(...)` — pick a stable `id`,
   the `subject_entity` it concerns, an `origin` (the module/service that raises it), and a
   `sensitivity` tier (`"standard" | "elevated" | "critical"`).
2. Call `audit_service.append(event_id=..., ...)` from the code path that performs the audited
   action, AFTER the business transaction has committed (or in parallel, per `AUDIT_WRITE_MODE` —
   `append()` opens its own session either way).
3. If the event carries per-scope retention different from the default, add its window to the
   `retention[]` policy the generated project configures (see `service.py`'s retention constants)
   — do not hardcode a one-off exception in `router.py`.

## Core guidelines

- **DO** treat `app/audit/erasure.py` as the only file allowed to mutate an `AuditEntry` row.
- **DO** keep `anonymised` and `subject_key` out of the pinned column set — see above.
- **DO** re-read the threat-model block before changing the digest algorithm.
- **DON'T** put personally-identifying data directly into `payload` — use `subject_key`
  (pseudonymised) for the subject reference, so erasure has something narrow to shred.
- **DON'T** put subject-identifying data into `anonymise(reason=...)` — the `reason` text is
  written into the erasure audit entry's `payload`, which is append-only and unshreddable. If the
  caller puts the subject's name in `reason`, PII re-enters the ledger on the very entry
  documenting its erasure.
- **DON'T** let a caller construct or update an `AuditEntry` row directly — always go through
  `service.append()` so the hash chain stays intact.
