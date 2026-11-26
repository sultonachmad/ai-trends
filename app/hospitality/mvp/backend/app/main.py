from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401 — registers all SQLModel table metadata
import app.rbac.models  # noqa: F401 — registers RBAC table metadata for Alembic
from app.config import settings
from app.database import create_db_and_tables

# PREFAB:module-imports


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await create_db_and_tables()
    # ============================================================================
    # PREFAB:rbac — startup seed
    # ============================================================================
    # Upserts RBAC permission rows and the admin role on every startup. The admin
    # user is opt-in: seeded only when RBAC_SEED_ADMIN is true and
    # RBAC_ADMIN_PASSWORD is set (see app/rbac/seed.py).
    # The seed is idempotent — safe to call repeatedly.
    #
    # Runs after `create_db_and_tables()` so all tables exist before inserting.

    from app.database import async_session_factory as _rbac_session_factory
    from app.rbac.seed import seed_rbac

    async with _rbac_session_factory() as _rbac_db:
        await seed_rbac(_rbac_db)

    # The workspace's own access model: the manager role (all application permissions)
    # and, for owners who signed up before roles existed, a one-time grant.
    from app.services.workspace_access import (
        backfill_owner_access,
        ensure_manager_role,
        ensure_staff_roles,
    )

    async with _rbac_session_factory() as _access_db:
        await ensure_manager_role(_access_db)
        await ensure_staff_roles(_access_db)
        await backfill_owner_access(_access_db)
    # ============================================================================
    # PREFAB:audit-evidence — startup check
    # ============================================================================
    # Logs the effective AUDIT_WRITE_MODE and the number of registered audit
    # events at startup, so operators can see the wiring at a glance.
    #
    # audit-evidence has no DB seed step (contrast rbac's seed_rbac()) —
    # AUDIT_EVENTS is a declarative in-code registry (app/audit/events.py), not a
    # database table, so there is nothing to upsert here.
    #
    # Retention purge is exposed as POST /api/audit/retention/purge (see
    # app/audit/router.py) rather than run as an internal scheduled task —
    # trigger it from the generated project's own scheduler (cron, k8s
    # CronJob, ...). In AUDIT_WRITE_MODE=spool, the retry spool is in-process and
    # empty on a cold start; a generated project relying on `spool` in
    # production should wire its own periodic call to
    # `app.audit.service.retry_spool()` rather than assume one exists here.

    import logging as _audit_logging

    from app.audit.events import AUDIT_EVENTS
    from app.audit.service import AUDIT_WRITE_MODE

    _audit_logging.getLogger(__name__).info(
        "audit-evidence ready: write_mode=%s events=%d",
        AUDIT_WRITE_MODE.value,
        len(AUDIT_EVENTS),
    )
    # Development-only switches must not be on in a production-like deployment.
    from app.security.startup_checks import assert_safe_configuration

    assert_safe_configuration(settings)

    # Fail fast, with a clear message, when the database is missing migrations.
    from app.database import engine as _engine
    from app.db_migrations import assert_database_migrated

    await assert_database_migrated(_engine)
    # Delete transfer-proof images past their retention period. Best effort: a failure
    # here is logged and must not stop the app from starting.
    from app.services.proof_retention import run_startup_purge

    await run_startup_purge(_engine)
    # Warn now, not at the first guest ID, when the identity key is not set.
    from app.security.identity_crypto import get_identity_cipher

    get_identity_cipher()

    # Keep connected channels up to date: every few seconds, push what changed.
    # A single process owns pushing (documented assumption until we run more than one).
    # The queue lives in PostgreSQL (a tenant table); the SQLite fallback used by the
    # unit-test app has no channels to keep up to date.
    import asyncio

    from app.services.channel_push import run_channel_pusher

    app.state.channel_pusher_task = None
    if _engine.dialect.name == "postgresql":
        app.state.channel_pusher_stop = asyncio.Event()
        app.state.channel_pusher_task = asyncio.create_task(
            run_channel_pusher(
                _rbac_session_factory,
                app.state.channel_pusher_stop,
                settings.CHANNEL_PUSH_INTERVAL_SECONDS,
            )
        )
    # Bookings made on connected channels: fetched and applied on a timer.
    from app.services.channel_booking_pull import run_booking_poller

    if _engine.dialect.name == "postgresql":
        app.state.booking_poller_stop = asyncio.Event()
        app.state.booking_poller_task = asyncio.create_task(
            run_booking_poller(
                _rbac_session_factory,
                app.state.booking_poller_stop,
                settings.CHANNEL_PUSH_INTERVAL_SECONDS * 2,
            )
        )
    else:
        app.state.booking_poller_task = None
    # Calendars of linked sites (Airbnb and the like): read on a timer.
    from app.services.calendar_link_sync import run_calendar_sync

    app.state.calendar_sync_task = None
    if _engine.dialect.name == "postgresql":
        app.state.calendar_sync_stop = asyncio.Event()
        app.state.calendar_sync_task = asyncio.create_task(
            run_calendar_sync(
                _rbac_session_factory,
                app.state.calendar_sync_stop,
                settings.CALENDAR_SYNC_TICK_SECONDS,
            )
        )
    # Direct bookings: release unpaid holds and send WhatsApp confirmations.
    from app.services.booking_holds import run_hold_loop

    app.state.hold_loop_task = None
    if _engine.dialect.name == "postgresql":
        app.state.hold_loop_stop = asyncio.Event()
        app.state.hold_loop_task = asyncio.create_task(
            run_hold_loop(_rbac_session_factory, app.state.hold_loop_stop, 15)
        )
    # Guest ID photos after the stay and ID numbers after retention: now, then hourly.
    from app.services.id_retention import run_id_purge_loop

    app.state.id_purge_task = None
    if _engine.dialect.name == "postgresql":
        app.state.id_purge_stop = asyncio.Event()
        app.state.id_purge_task = asyncio.create_task(
            run_id_purge_loop(_rbac_session_factory, app.state.id_purge_stop)
        )
    # PREFAB:startup-tasks
    yield

    # Stop the background loops before the app goes away.
    if app.state.id_purge_task is not None:
        app.state.id_purge_stop.set()
        await app.state.id_purge_task
    if app.state.hold_loop_task is not None:
        app.state.hold_loop_stop.set()
        await app.state.hold_loop_task
    if app.state.calendar_sync_task is not None:
        app.state.calendar_sync_stop.set()
        await app.state.calendar_sync_task
    if app.state.channel_pusher_task is not None:
        app.state.channel_pusher_stop.set()
        await app.state.channel_pusher_task
    if getattr(app.state, "booking_poller_task", None) is not None:
        app.state.booking_poller_stop.set()
        await app.state.booking_poller_task


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        lifespan=lifespan,
        root_path=settings.ROOT_PATH,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # CSRF defence for the cookie session: unsafe methods must come from a configured
    # frontend origin (or this API itself). See app/security/origin_check.py.
    from app.security.origin_check import OriginCheckMiddleware

    app.add_middleware(OriginCheckMiddleware, allowed_origins=settings.CORS_ORIGINS)

    # Pay-link addresses carry a secret token: never cached, never sent as a referrer.
    from app.security.token_paths import TokenPathHeadersMiddleware

    app.add_middleware(TokenPathHeadersMiddleware)

    # Image uploads: refuse an oversized body before it is parsed or spooled to disk.
    from app.security.upload_limit import UploadSizeLimitMiddleware

    app.add_middleware(UploadSizeLimitMiddleware)

    # ============================================================================
    # PREFAB:auth-oauth2 — auth router registration
    # ============================================================================
    # Added by the `auth-oauth2` prefab. This block is spliced into
    # `backend/app/main.py` by the prefab installer (mode: integrate), inside
    # `create_app()` and before `return app` — so `app` below refers to the
    # FastAPI instance under construction, and registering the router here is
    # safe (runs once, at import time, before the app serves any requests).

    from app.auth.oauth_bridge import router as oauth_bridge_router
    from app.auth.router import router as auth_router

    app.include_router(auth_router)
    app.include_router(oauth_bridge_router)
    # PREFAB:auth-oauth2
    # ============================================================================
    # PREFAB:auth-session — session middleware registration
    # ============================================================================
    # Added by the `auth-session` prefab. This block is spliced into
    # `backend/app/main.py` by the prefab installer (mode: integrate), inside
    # `create_app()` and before `return app` — so `app` below refers to the
    # FastAPI instance under construction, and registering middleware here is
    # safe (runs once, at import time, before the app serves any requests).
    #
    # What this does:
    #   1. Builds a `SessionStore` (in-memory POC — see app/session/store.py for
    #      production notes, e.g. swapping in a Redis-backed store).
    #   2. Registers `SessionMiddleware`, which resolves the `prefab_session`
    #      cookie into `request.state.user` on every request.
    #   3. Publishes the same `SessionStore` instance on `app.state.session_store`
    #      so route handlers (this prefab's own `session_router` below, or any
    #      hand-written login route) can create/delete sessions through it.
    #      Route handlers must reach it via `request.app.state.session_store` —
    #      never construct a second `SessionStore()`, which would have its own
    #      empty, disconnected in-memory session dict.
    #   4. Registers `session_router` (`GET /session/me`, `POST /session/logout`).
    #
    # Requires the `itsdangerous` package (added to this project's backend
    # dependencies by the prefab installer).
    #
    # `secure=False` below is a local-HTTP-development default. Set it to `True`
    # (or drop the kwarg to use the middleware's own secure-by-default) once the
    # app is served over HTTPS.
    #
    # NOTE: `settings` is NOT re-imported here — `backend/app/main.py` already
    # imports it at module level. A local `from app.config import settings`
    # inside this function would shadow that name for the *entire* function
    # body (Python decides a name is local by scanning the whole function for
    # any assignment to it, not by execution order), which breaks the earlier
    # `FastAPI(title=settings.APP_NAME, ...)` line with an UnboundLocalError.

    from app.session.middleware import SessionMiddleware
    from app.session.router import router as session_router
    from app.session.store import SessionStore

    _session_store = SessionStore(secret_key=settings.SECRET_KEY)
    app.state.session_store = _session_store

    app.add_middleware(
        SessionMiddleware,
        store=_session_store,
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=True,
    )

    app.include_router(session_router)
    # ============================================================================
    # PREFAB:auth-session — credentials (email/password) router registration
    # ============================================================================
    # Added by the `auth-session` prefab. This block is spliced into
    # `backend/app/main.py` by the prefab installer (mode: integrate), inside
    # `create_app()` and before `return app` — same insertion point auth-oauth2
    # uses, so `app` below refers to the FastAPI instance under construction.
    #
    # Registers POST /api/auth/signup and POST /api/auth/login — consumed by the
    # frontend's NextAuth Credentials provider, not called directly by users.

    from app.auth.credentials_router import router as credentials_router

    app.include_router(credentials_router)
    # PREFAB:auth-session

    @app.get("/api/health")
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    # ── Feature routers ──────────────────────────────────────────────────────
    from app.routers.sample_items import sample_items_router

    app.include_router(sample_items_router)

    # ============================================================================
    # PREFAB:rbac — router registration
    # ============================================================================
    # Registers the RBAC management routers (roles, permissions, users, menus)
    # and the /api/me endpoint into the FastAPI application.
    #
    # Importing these modules here also triggers require_permission() calls
    # throughout router.py and me.py, which populates _PERMISSION_REGISTRY before the
    # lifespan seed runs — that ordering is guaranteed because create_app()
    # completes before lifespan() fires.

    from app.rbac.me import me_router
    from app.rbac.router import rbac_router

    app.include_router(rbac_router)
    app.include_router(me_router)
    from app.contact.router import router as contact_router

    app.include_router(contact_router)
    # ============================================================================
    # PREFAB:audit-evidence — router registration
    # ============================================================================
    # Registers the audit query/verify/retention-purge router into the FastAPI
    # application.
    #
    # Importing this module also imports app.audit.models (via app.audit.router
    # -> app.audit.erasure -> app.audit.models), which registers AuditEntry's
    # table metadata before create_db_and_tables() runs in lifespan() below —
    # no separate module-imports snippet is needed for that, unlike rbac's models.

    from app.audit.router import audit_router

    app.include_router(audit_router)
    # PREFAB:feature-routers
    # Mount every feature/entity router here, e.g.:
    #     from app.routers.widgets import widgets_router
    #     app.include_router(widgets_router)
    # Routers created with `create_crud_router(...)` already carry their own
    # `prefix` and `tags`; import the router object and include it as-is.
    # Custom (non-CRUD) action endpoints must be attached to that same router
    # object BEFORE it is included — see crud-scaffold AGENTS-be.md → "Custom
    # action endpoints" for the ordering rule that avoids `/{id}` collisions.

    # ============================================================================
    # PREFAB:llm-call — LLM router registration
    # ============================================================================
    # Added by the `llm-call` prefab. Registers POST /api/llm/chat — a
    # litellm-backed chat completion endpoint guarded by app.access
    # (features:use). Importing the router also registers the permission code
    # with rbac before the lifespan seed runs.

    from app.llm.router import router as llm_router

    app.include_router(llm_router)
    # PREFAB:llm-call

    # ============================================================================
    # PREFAB:rag-base — RAG router registration
    # ============================================================================
    # Added by the `rag-base` prefab. Registers the RAG endpoints (upload,
    # search, ask, deletes) guarded by app.access (features:use /
    # features:delete). The Qdrant client connects lazily on first use — no
    # Qdrant server is contacted at import or startup time.

    from app.rag.router import router as rag_router

    app.include_router(rag_router)
    # PREFAB:rag-base

    # Phase 0 wedge — property workspace
    from app.routers.onboarding import onboarding_router
    from app.routers.workspace import workspace_router

    app.include_router(onboarding_router)
    app.include_router(workspace_router)

    # Phase 0 wedge — WhatsApp inbox (simulator routes answer 404 unless enabled)
    from app.routers.inbox import inbox_router
    from app.routers.simulator import simulator_router

    app.include_router(inbox_router)
    app.include_router(simulator_router)

    # Phase 0 wedge — payment links (staff), public pay page, payment simulator
    from app.routers.checkout import checkout_router
    from app.routers.payment_links import payment_links_router
    from app.routers.simulator import payment_simulator_router

    app.include_router(payment_links_router)
    app.include_router(checkout_router)
    app.include_router(payment_simulator_router)

    # Phase 0 wedge — transfer proofs and property settings
    from app.routers.settings import settings_router
    from app.routers.transfer_proofs import transfer_proofs_router

    app.include_router(transfer_proofs_router)
    app.include_router(settings_router)

    # Phase 1 — rooms, prices and availability
    from app.routers.bookings import bookings_router
    from app.routers.calendar import calendar_router
    from app.routers.rate_plans import rate_plans_router
    from app.routers.rooms import rooms_router

    app.include_router(rooms_router)
    app.include_router(rate_plans_router)
    app.include_router(calendar_router)
    app.include_router(bookings_router)

    # Phase 1 — channel connections (the simulated agency stands in for certified ones)
    from app.channels import simulator as _channel_simulator  # noqa: F401 — registers it
    from app.routers.channel_simulator import channel_simulator_router
    from app.routers.channels import channels_router, connections_router

    app.include_router(channels_router)
    from app.routers.apoa import apoa_router
    from app.routers.cash_drawers import cash_drawers_router
    from app.routers.end_of_day import end_of_day_router
    from app.routers.housekeeping import housekeeping_router
    from app.routers.staff import join_router, staff_router
    from app.routers.bills import bills_router
    from app.routers.front_desk import front_desk_router
    from app.routers.guest_ids import guest_ids_router
    from app.routers.reports import reports_router

    app.include_router(apoa_router)
    app.include_router(cash_drawers_router)
    app.include_router(end_of_day_router)
    app.include_router(housekeeping_router)
    app.include_router(staff_router)
    app.include_router(join_router)
    app.include_router(bills_router)
    app.include_router(guest_ids_router)
    app.include_router(front_desk_router)
    app.include_router(reports_router)
    from app.routers.booking_page import (
        booking_page_router,
        guest_booking_router,
        public_book_router,
    )

    app.include_router(booking_page_router)
    app.include_router(public_book_router)
    app.include_router(guest_booking_router)
    from app.routers.calendar_links import calendar_links_router, ical_router

    app.include_router(calendar_links_router)
    app.include_router(ical_router)
    app.include_router(connections_router)
    app.include_router(channel_simulator_router)

    return app


app = create_app()

# ============================================================================
# PREFAB:auth-session-sample — sample protected routes
# ============================================================================
# Added by the `auth-session` prefab. Registers the sample protected router
# that demonstrates `Depends(get_current_user)` with session-based auth.
# Delete this block (and `app/routers/sample_protected.py`) once you've built
# your own protected routes.

from app.routers.sample_protected import router as sample_protected_router

app.include_router(sample_protected_router)


# ============================================================================
# PREFAB:file-upload — upload router registration
# ============================================================================
# Added by the `file-upload` prefab. This block is appended to the end of
# `backend/app/main.py` by the prefab installer (mode: integrate) and runs
# at import time, right after `app = create_app()` above — before the app has
# served any requests, so registering the router here is safe.
#
# What this does:
#   Registers the `/api/uploads` router (see app/upload/router.py), which
#   handles multipart upload, listing, download, and delete of files backed
#   by `app/upload/storage.py::LocalStorage`. `LocalStorage` also creates the
#   `uploads/` directory (relative to the backend process's working
#   directory) the first time it is instantiated.
#
# Requires the `python-multipart` and `aiofiles` packages (added to this
# project's backend dependencies by the prefab installer): `python-multipart`
# is required by FastAPI/Starlette to parse multipart form uploads;
# `aiofiles` backs `LocalStorage`'s non-blocking file I/O.

from app.upload.router import router as upload_router

app.include_router(upload_router)


# ============================================================================
# PREFAB:document-extract — extraction router registration
# ============================================================================
# Added by the `document-extract` prefab. This block is appended to the end
# of `backend/app/main.py` by the prefab installer (mode: integrate) and
# runs at import time, right after `app = create_app()` above.
#
# What this does:
#   Registers the extraction router, exposing:
#     POST /api/extract                        (direct file upload)
#     POST /api/extract/from-upload/{upload_id} (extract from stored upload)
#
# Requires the `file-upload` prefab to already be installed — the second
# route imports `app.upload.storage.get_upload_path` at module load time.
#
# Requires the `pdfplumber` and `python-docx` packages (added to this
# project's backend dependencies by the prefab installer).

from app.extract.router import router as extract_router

app.include_router(extract_router)
