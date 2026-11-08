from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import create_db_and_tables
import app.models  # noqa: F401 — registers all SQLModel table metadata
import app.rbac.models  # noqa: F401 — registers RBAC table metadata for Alembic
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

    from app.rbac.seed import seed_rbac
    from app.database import async_session_factory as _rbac_session_factory

    async with _rbac_session_factory() as _rbac_db:
        await seed_rbac(_rbac_db)
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
    # PREFAB:startup-tasks
    yield


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

    # ============================================================================
    # PREFAB:auth-oauth2 — auth router registration
    # ============================================================================
    # Added by the `auth-oauth2` prefab. This block is spliced into
    # `backend/app/main.py` by the prefab installer (mode: integrate), inside
    # `create_app()` and before `return app` — so `app` below refers to the
    # FastAPI instance under construction, and registering the router here is
    # safe (runs once, at import time, before the app serves any requests).

    from app.auth.router import router as auth_router
    from app.auth.oauth_bridge import router as oauth_bridge_router

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
        secure=False,
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

    from app.rbac.router import rbac_router
    from app.rbac.me import me_router

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

