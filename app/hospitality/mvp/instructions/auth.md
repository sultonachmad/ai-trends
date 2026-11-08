<!-- Prefab: auth-session v0.2.0 -->

# Auth Session Prefab — Agent Instructions

This prefab adds server-side, DB-backed session management to the base Next.js +
FastAPI skeleton: a FastAPI middleware + store + router on the backend, and a
`SessionProvider` + `LogoutButton` on the frontend. Requires `base-nextjs-fastapi`
to be installed first. This prefab is independent of `auth-oauth2` — either can
be used to identify a user, but this one manages the session lifecycle
(creation, lookup, invalidation) once a user is identified.

## Where Things Live

```
frontend/
  lib/session.ts                     # fetchSession() / logout() — talk to the backend, never touch the cookie directly
  components/SessionProvider.tsx     # React context provider exposing session state to the tree
  components/LogoutButton.tsx        # Drop-in "Log out" button — calls useSessionState().logout()
  components/LoginForm.tsx           # THE email/password form — add login fields here, not in auth-credentials
  app/login/page.tsx                 # Owns the login page + its PREFAB:login-imports / PREFAB:login-extra markers
  middleware.ts                      # Edge middleware — 302-redirects `/` to `/login` (see Page Routing)
backend/
  app/session/middleware.py          # ASGI middleware — resolves session cookie -> request.state.user
  app/session/store.py                # SessionStore class (create/get/touch/delete)
  app/session/router.py               # GET /session/me, POST /session/logout
```

`backend/app/main.py` is integrated at install time (see `integrate/`, marker
`PREFAB:auth-session`) to build the `SessionStore`, publish it on
`app.state.session_store`, register `SessionMiddleware`, and register
`session_router`. Do not duplicate that wiring.

## Session Middleware and Store

`app/session/middleware.py` runs on every request: it reads the session cookie,
loads the session record via `SessionStore`, and attaches the result to
`request.state.user` (`None` if absent/invalid/expired). `app/session/store.py`
owns all reads/writes to session data — never touch the underlying storage
directly from a route handler, and never instantiate a second `SessionStore()`
(it would be a disconnected, empty in-memory dict). Reach the real instance
via `request.app.state.session_store`.

The middleware re-checks session validity *after* the route handler runs, not
just before — otherwise a route that deletes the session mid-request (logout)
would have its cookie re-stamped as "still valid" on the same response.

The session cookie is httpOnly by design (see Rules below) — not readable or
writable from frontend JavaScript. Frontend code must go through
`frontend/lib/session.ts`'s backend calls, never `document.cookie`.

## Session Lifecycle Endpoints (already provided)

`app/session/router.py` ships two working endpoints — you do not need to
write these yourself:

| Method | Path             | Behavior                                              |
|--------|------------------|--------------------------------------------------------|
| GET    | `/session/me`    | Current session's user data, or 401 if none            |
| POST   | `/session/logout`| Deletes the session record and clears the cookie, 204   |

What this prefab does *not* provide is login — it manages session lifecycle
once a user is identified, but identifying the user (checking a password,
verifying an OAuth token, etc.) is the other prefab's or your own job. After
you've verified who the user is, create their session like this:

```python
from fastapi import APIRouter, Request, Response

from app.session.middleware import DEFAULT_COOKIE_NAME, DEFAULT_COOKIE_PATH

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response):
    user = await authenticate(body.email, body.password)  # your own logic
    session_id = await request.app.state.session_store.create(
        user_id=user.id, data={"email": user.email}
    )
    response.set_cookie(
        key=DEFAULT_COOKIE_NAME,
        value=session_id,
        path=DEFAULT_COOKIE_PATH,
        httponly=True,
        secure=False,  # must match the `secure=` SessionMiddleware was registered with
        samesite="lax",
    )
    return {"user_id": user.id}
```

Import `DEFAULT_COOKIE_NAME` / `DEFAULT_COOKIE_PATH` from `app.session.middleware`
rather than retyping the literals. `secure`/`httponly`/`samesite` aren't
exported as constants — keep those in sync with
`integrate/main-session-middleware.py` by hand.

## Page Routing — Public vs Authenticated

Pages are split into two groups by folder:

```
frontend/app/
  page.tsx                          # / — unreachable while middleware.ts redirects / -> /login
  about/page.tsx                    # /about — public
  login/page.tsx                    # /login — public
  (authenticated)/                  # route group — ALL children require auth
    layout.tsx                      # wraps children in <AuthGuard>
    dashboard/page.tsx              # /dashboard — requires login
    settings/page.tsx               # /settings — requires login
```

**To create a page that requires login**: put it inside `app/(authenticated)/`.
The `(authenticated)` folder is a Next.js route group — it does NOT appear in
the URL. A file at `app/(authenticated)/orders/page.tsx` is reachable at
`/orders`.

**To create a public page**: put it directly in `app/` (outside the group).

**`/` redirects to `/login`**: `frontend/middleware.ts` (matcher `["/"]`)
302-redirects `/` before `app/page.tsx` renders. If the spec has a screen at
route `/`, delete `middleware.ts` and build that screen in `app/page.tsx`.
After sign-in, `LoginForm` sends the user to `callbackUrl`, or to `/dashboard`
when there is none.

The `(authenticated)/layout.tsx` wraps all children in `<AuthGuard>`, which
checks `useSessionState()` and redirects unauthenticated users to `/login`.
Individual pages inside the group do NOT need their own auth check.

### Creating a New Authenticated Page

1. Create the page file inside `app/(authenticated)/`:

```tsx
// app/(authenticated)/orders/page.tsx
"use client";

import { useSessionState } from "@/components/SessionProvider";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function OrdersPage() {
  const { user } = useSessionState();

  // user is guaranteed non-null — AuthGuard in the layout already
  // verified the session before this component renders.

  return <h1>Welcome, {typeof user?.email === "string" ? user.email : "user"}</h1>;
}
```

That's it — no `<AuthGuard>` wrapper needed in the page itself.

## Using SessionProvider in the Frontend

`SessionProvider` is wired into `frontend/app/providers.tsx` at install time.
Consume it from any Client Component:

```tsx
"use client";
import { useSessionState } from "@/components/SessionProvider";

function AccountBadge() {
  const { user, loading } = useSessionState();
  if (loading) return null;
  return <span>{user?.user_id ?? "Guest"}</span>;
}
```

For a logout control, drop in the ready-made component:

```tsx
import { LogoutButton } from "@/components/LogoutButton";

<LogoutButton />
```

## Rules

### DO
- Put every page that requires login inside `app/(authenticated)/` — the layout handles auth
- Put public pages directly in `app/` — outside the `(authenticated)` group
- Use `request.app.state.session_store` to reach the shared `SessionStore`
  from a route handler — never construct a new `SessionStore()`
- Invalidate the session (`await store.delete(session_id)`) on logout, and
  clear the session cookie in the same response — `POST /session/logout`
  already does both; reuse it instead of writing a second logout route
- Set `Secure`, `HttpOnly`, and `SameSite=Lax` (or stricter) on the session
  cookie in every environment, including local dev over HTTPS-terminated proxies
- Re-validate `request.state.user` on every protected endpoint — do not
  cache the result across requests
- Rotate the session identifier on privilege changes (e.g. login, role change)

### DO NOT
- Do not put authenticated pages directly in `app/` — always use `app/(authenticated)/`
- Do not wrap individual pages in `<AuthGuard>` — the `(authenticated)/layout.tsx` already does it
- Do not store sensitive data (passwords, tokens, PII beyond a user id) inside
  the session record — store a reference (user id) and look up the rest from
  the database
- Do not trust client-supplied session data (headers, request body) as a
  substitute for the server-resolved `request.state.user`
- Do not read or write the session cookie manually in route handlers — go
  through `app/session/middleware.py` and `app/session/store.py`
- Do not try to read, set, or clear the session cookie from frontend
  JavaScript (`document.cookie`) — it's httpOnly and invisible to JS by
  design; use `frontend/lib/session.ts`'s backend calls instead
- Do not extend session lifetime indefinitely on every request without an
  absolute expiry — always cap total session lifetime, not just idle timeout

---

<!-- Prefab: auth-oauth2 v0.3.0 -->

# Auth OAuth2 Prefab — Agent Instructions

This prefab is the OAuth2 core: it adds the NextAuth.js instance, the route
handlers, route protection and JWT validation, and it registers no sign-in
provider of its own. It sits on the auth-session prefab and bridges
into auth-session's cookie-based session system — after a successful OAuth
sign-in, a `prefab_session` cookie is created automatically so all existing
`useSessionState()` / `GET /session/me` flows work unchanged.

Requires `base-nextjs-fastapi` and `auth-session` to be installed first.

**Install it together with a provider prefab** (`auth-oauth2-google`,
`auth-oauth2-microsoft`). On its own the core registers no NextAuth provider
outside test mode, so the login page offers only auth-session's email/password
form and no SSO button. Each provider prefab splices its own NextAuth provider,
its sign-in button and its env placeholders into the files this prefab installs.

## Where Things Live

```
frontend/
  auth.config.ts                        # Edge-safe config (NO providers) — session check for middleware.ts
  lib/nextauth.ts                       # FULL config (providers + callbacks) — Node.js runtime only
  app/api/auth/[...nextauth]/route.ts   # Route handlers only: re-exports GET and POST from lib/nextauth.ts
  app/providers.tsx                     # Wraps both NextAuth + auth-session providers + OAuth bridge
  lib/auth.ts                           # Server-side helper: getServerSession(), requireAuth()
  lib/auth-client.ts                    # Client-side helper: useSession(), signIn(), signOut()
  middleware.ts                         # Redirects / and unauthenticated requests to /login (see below)
backend/
  app/auth/router.py                    # /auth routes: current-user lookup, standalone token verification
  app/auth/jwt.py                       # JWT encode/decode/verify
  app/auth/dependencies.py              # get_current_user FastAPI dependency (JWT Bearer)
  app/auth/oauth_bridge.py              # POST /auth/oauth-bridge — JWT → prefab_session
```

`backend/app/main.py` is integrated at install time (see `integrate/`, marker
`PREFAB:auth-oauth2`) to register the auth router and the oauth bridge router.
Each provider prefab adds its own client id / secret placeholders to
`frontend/.env.local`. `NEXTAUTH_SECRET` is written when the workspace is
created. Do not duplicate that wiring.

## How OAuth Bridges into auth-session

This prefab does NOT replace auth-session's UI components (`AuthGuard`, `Nav`,
`Sidebar`, `LogoutButton`, `SessionProvider`, `providers.tsx`, dashboard page).
Instead it integrates into auth-session's `lib/session.ts` via markers:

1. After an OAuth sign-in, NextAuth creates a JWT session cookie
   (`next-auth.session-token`) and redirects to the app.
2. auth-session's `SessionProvider` calls `fetchSession()` which hits
   `GET /session/me` — returns 401 (no `prefab_session` yet).
3. The bridge code (spliced at `PREFAB:session-fetch-bridge`) detects this,
   fetches the NextAuth session from `/api/auth/session`, and POSTs the
   `accessToken` to `POST /auth/oauth-bridge`.
4. The backend verifies the JWT via `app/auth/jwt.py` and creates a
   `prefab_session` record in auth-session's `SessionStore`.
5. `fetchSession()` returns the user data — the rest of the app sees a normal
   authenticated session.
6. On logout, auth-session clears the `prefab_session` cookie, and the bridge
   code (spliced at `PREFAB:session-logout-extra`) also signs out of NextAuth
   by calling `/api/auth/signout`.

## Two Configs, on Purpose: auth.config.ts vs. lib/nextauth.ts

`middleware.ts` runs in the Edge runtime; `lib/nextauth.ts` runs on
Node.js. The OAuth providers pull in `openid-client`, which needs
Node.js-only APIs — importing them into Edge code throws at runtime, not at
build time, so this split is easy to reintroduce a regression against without
noticing:

- `auth.config.ts` — `providers: []`, only `pages` + the `authorized` callback.
  This is the ONLY config `middleware.ts` may build a NextAuth instance from.
  The `authorized` callback allows both NextAuth sessions AND `prefab_session`
  cookies — so both OAuth and username/password users pass through.
- `lib/nextauth.ts` — spreads `authConfig` and adds the real `providers` array
  (empty here; the provider prefabs splice their `providers.push(...)` in at the
  `PREFAB:route-providers` marker and their import at `PREFAB:route-imports`)
  plus the `jwt`/`session` callbacks. This is the ONLY config allowed to list
  providers, and it must never be imported into `middleware.ts`.

Do not merge these back into one file, and do not import `auth` from
`lib/nextauth.ts` anywhere that might run at the edge.

## Page Routing — Public vs Authenticated

Follows the same pattern as auth-session — see its agent instructions.
Pages inside `app/(authenticated)/` are protected; pages directly in `app/`
are public. This prefab does NOT overwrite auth-session's AuthGuard, Nav,
Sidebar, LogoutButton, or dashboard page — those files belong to auth-session.

`frontend/middleware.ts` runs at the edge. `"/"` 302-redirects to `/login`;
`/dashboard/:path*`, `/settings/:path*` and `/protected/:path*` are delegated
to NextAuth's `auth()` for session checks. When you add a new top-level path
inside `(authenticated)/`, add it to the `matcher` array in `middleware.ts`
too — this prevents a flash of protected content before the client-side guard
kicks in.

This `middleware.ts` replaces auth-session's (manifest `mode: overwrite`) and
carries the same `/` -> `/login` redirect. The redirect runs on the original
Next.js request (basePath already stripped), then delegates other matched paths
to `auth()` (NextAuth's middleware). If the spec has a screen at route `/`,
remove `"/"` from `matcher` and the redirect branch in `middleware.ts`, then
build that screen in `app/page.tsx`.

After sign-in, `LoginForm` and the provider prefabs' buttons send the user to `callbackUrl`,
or to `/dashboard` when there is none.

## How the Token Reaches the Backend (end-to-end)

1. On sign-in, the NextAuth `jwt` callback (in
   `lib/nextauth.ts`) mints an **HS256 JWT signed with
   `NEXTAUTH_SECRET`** and stores it on the token.
2. The `session` callback exposes it as `session.accessToken`.
3. `fetchSession()` in `lib/session.ts` detects the 401 from `/session/me`,
   reads the NextAuth session via `/api/auth/session`, and sends the token to
   `POST /auth/oauth-bridge`, which creates a `prefab_session` cookie.
4. All subsequent requests use the `prefab_session` cookie — same as
   username/password login via auth-session.

**`NEXTAUTH_SECRET` MUST equal `PREFAB_SECRET_KEY`** — the token is signed with
one and verified with the other. If they differ, every authenticated call 401s.

## Logging Out

auth-session's `LogoutButton` calls `logout()` from `lib/session.ts`, which
clears the `prefab_session` cookie via `POST /session/logout`. The bridge code
(spliced at `PREFAB:session-logout-extra`) also calls NextAuth's
`/api/auth/signout` endpoint to clear the `next-auth.session-token` cookie.
Both sessions are cleaned up in a single `logout()` call.

## Creating a New Authenticated Page

Follow auth-session's instructions — create the page inside
`app/(authenticated)/` and use `useSessionState()` from
`@/components/SessionProvider`. The session data is the same regardless of
whether the user signed in via Google or username/password.

## Protecting Backend Endpoints

Use `get_current_user` from `app/session/dependencies.py` (auth-session's
cookie-based dependency) on routes that need auth. The `prefab_session` cookie
is set for both OAuth and credentials users.

For routes that specifically need JWT verification (e.g. external API
consumers), use `get_current_user` from `app/auth/dependencies.py` instead —
this reads the `Authorization: Bearer` header.

## Rules

### DO
- Put every page that requires login inside `app/(authenticated)/`
- Add new authenticated path prefixes to the `matcher` in `middleware.ts`
- Use `useSessionState()` from auth-session for UI auth state
- Keep `NEXTAUTH_SECRET` equal to the backend's `PREFAB_SECRET_KEY`

### DO NOT
- Do not overwrite auth-session's UI components (AuthGuard, Nav, Sidebar,
  LogoutButton, SessionProvider, dashboard page)
- Do not put authenticated pages directly in `app/`
- Do not add auth middleware to public routes (`/` is matched only for the
  `/` -> `/login` redirect)
- Do not store tokens in `localStorage` or `sessionStorage`
- Do not add a new auth flow that bypasses `app/auth/jwt.py`

## Adding a New OAuth Provider

1. Add the provider package if it isn't a built-in NextAuth.js provider.
2. In `frontend/lib/nextauth.ts`, add the provider to the
   `providers` array with its client ID/secret pulled from env vars — never
   hardcode credentials. Follow the two provider prefabs: an import at
   `PREFAB:route-imports` and a `providers.push(...)` at `PREFAB:route-providers`.
3. Add the new env vars to `.env.example` at the project root with a comment
   noting where to obtain them.
4. If the provider needs custom claim mapping, extend the `jwt`/`session`
   callbacks in the same file — do not add a second callback pipeline.
   Pay attention to providers that return the email under non-standard claim
   names (the callback already falls back through `mail`, `upn` and
   `preferred_username`).
5. Add a corresponding sign-in button in `app/login/page.tsx` using
   `signIn("<provider-id>")` from `lib/auth-client.ts`.
6. Verify `backend/app/auth/jwt.py` validation still passes for tokens issued
   under the new provider (issuer/audience claims may differ).

## Testing Auth Flows (Mock IdP)

Real OAuth providers (Google, Microsoft Entra) require a human with console
access to configure client credentials, redirect URIs, and consent screens.
That makes end-to-end testing of the auth flow impossible in CI or automated
vibe-coding loops — unless you use a mock identity provider.

This workspace ships a **test-only CredentialsProvider** that exercises the
same NextAuth callback pipeline (jwt → mintBackendToken → session → OAuth
bridge) as the real providers, without requiring any external service.

### How it works

In `frontend/lib/nextauth.ts`, a `credentials-test`
provider is conditionally registered when `NODE_ENV === "test"`:

```typescript
if (process.env.NODE_ENV === "test") {
  const CredentialsProvider = (await import("next-auth/providers/credentials")).default;
  providers.push(
    CredentialsProvider({
      id: "credentials-test",
      name: "Test Login",
      credentials: {
        email: { label: "Email", type: "email" },
        name: { label: "Name", type: "text" },
      },
      async authorize(credentials) {
        if (!credentials?.email) return null;
        return {
          id: `test-${credentials.email}`,
          email: credentials.email as string,
          name: (credentials.name as string) || "Test User",
        };
      },
    }),
  );
}
```

This provider:
- Accepts any email/name and returns a mock profile
- Flows through the **same** `jwt` callback → `mintBackendToken()` → `session`
  callback chain as Google/Entra — testing all app-side session/token plumbing
- Triggers the OAuth bridge (`POST /auth/oauth-bridge`) — testing that
  `prefab_session` cookies are created correctly
- Does NOT test the real OAuth handshake with Google/Entra — that is a
  provider-console concern covered by `OAUTH_SETUP_REQUIRED.md`

### Using in E2E tests (Playwright)

```typescript
// Sign in via the test provider (no browser-based OAuth redirect)
await page.request.post("/api/auth/callback/credentials-test", {
  form: { email: "e2e@test.local", name: "E2E User" },
});
// The session cookies are now set — navigate to an authenticated page
await page.goto("/dashboard");
await expect(page.locator("text=E2E User")).toBeVisible();
```

### What this tests vs. what it does NOT test

| Covered by mock IdP | NOT covered (needs real provider) |
|---|---|
| NextAuth JWT callback + token minting | Google/Entra console redirect URI config |
| Session callback + accessToken exposure | Real OIDC handshake + consent screen |
| OAuth bridge (JWT → prefab_session) | Provider-specific claim mapping quirks |
| Middleware route protection | Token refresh with real refresh tokens |
| Logout (dual session cleanup) | Multi-tenant cookie isolation in prod |

### Rules

- NEVER enable `credentials-test` in production — it is guarded by
  `NODE_ENV === "test"` and must stay that way.
- When planning auth changes, verify the mock-IdP test suite still passes.
  If no mock-IdP E2E tests exist yet, flag that gap in the plan.
- The mock provider does NOT replace the human-verified
  `OAUTH_SETUP_REQUIRED.md` gate — both are required.

---

<!-- Prefab: auth-oauth2-google v0.1.0 -->

# Auth OAuth2 Google Prefab — Agent Instructions

This prefab adds Google sign-in to the `auth-oauth2` core. It requires
`auth-oauth2` (and, through it, `auth-session`); install it with the core and
nothing else is needed to get a working Google button.

## Where Things Live

```
frontend/
  components/GoogleSSOForm.tsx          # "Sign in with Google" button (reads the callback URL on click)
  lib/nextauth.ts                       # Google provider registered at PREFAB:route-providers (import at PREFAB:route-imports)
  app/login/page.tsx                    # <GoogleSSOForm /> spliced at PREFAB:login-extra
  .env.local                            # GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET placeholders (empty)
```

The provider is registered whether or not the keys are filled in. Sign-in
fails at the provider until a human puts a real `GOOGLE_CLIENT_ID` and
`GOOGLE_CLIENT_SECRET` into `frontend/.env.local`; follow
`OAUTH_SETUP_REQUIRED.md` (the Google section) and do not treat Google login as
working until the user acknowledges it.

## Rules

- Do not add a second Google provider or a second Google button; this prefab
  already put both in place.
- Do not read `useSearchParams()` in `GoogleSSOForm` while rendering: the login
  page has no `<Suspense>` boundary, so it would break static generation of
  `/login`. The button reads the callback URL inside its click handler.
- Never put the client id or secret in source files. They live in
  `frontend/.env.local` only.

---

<!-- Prefab: auth-oauth2-microsoft v0.1.0 -->

# Auth OAuth2 Microsoft Prefab — Agent Instructions

This prefab adds Microsoft Entra ID (formerly Azure AD) sign-in to the
`auth-oauth2` core. It requires `auth-oauth2` (and, through it, `auth-session`).

## Where Things Live

```
frontend/
  components/MicrosoftSSOForm.tsx       # "Sign in with Microsoft" button (reads the callback URL on click)
  lib/nextauth.ts                       # Entra ID provider registered at PREFAB:route-providers (import at PREFAB:route-imports)
  app/login/page.tsx                    # <MicrosoftSSOForm /> spliced at PREFAB:login-extra
  .env.local                            # AZURE_AD_CLIENT_ID / AZURE_AD_CLIENT_SECRET / AZURE_AD_TENANT_ID placeholders (empty)
```

The provider is registered whether or not the keys are filled in, and its
provider id is `microsoft-entra-id`. Sign-in fails at the provider until a human
fills in the three `AZURE_AD_*` keys in `frontend/.env.local`; follow
`OAUTH_SETUP_REQUIRED.md` (the Microsoft section) and do not treat Microsoft
login as working until the user acknowledges it.

## Rules

- Do not add a second Microsoft provider or a second Microsoft button.
- Do not read `useSearchParams()` in `MicrosoftSSOForm` while rendering: the login
  page has no `<Suspense>` boundary. The button reads the callback URL inside its
  click handler.
- Never put the client id, secret or tenant id in source files.

## Microsoft Entra ID Email Claim Handling

Microsoft Entra ID's OIDC implementation does not always return the `email`
claim in `profile.email`. Depending on the tenant configuration, the email
may appear under:
- `email` — standard OIDC (works when the optional `email` claim is configured)
- `mail` — Azure AD graph attribute (most common)
- `upn` — User Principal Name (looks like an email, e.g. `user@tenant.onmicrosoft.com`)
- `preferred_username` — fallback

The JWT callback in `lib/nextauth.ts` handles this automatically: if `profile.email`
is empty after the initial assignment, it falls back through `mail → upn →
preferred_username`. The backend's `oauth-bridge` endpoint requires a
non-empty `email` claim — if all fallbacks fail, the bridge returns 400 and
the user sees no session.

When troubleshooting Entra ID login issues, check:
1. The App Registration's Token Configuration → add the `email` optional claim
2. API Permissions → ensure `openid`, `profile`, and `email` are granted
3. If the user's `mail` attribute is empty in Entra, `upn` is the last resort
