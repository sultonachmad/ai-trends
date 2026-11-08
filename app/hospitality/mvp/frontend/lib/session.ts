/**
 * Session helpers for the auth-session prefab.
 *
 * The session cookie is httpOnly (set by the backend's `SessionMiddleware`)
 * — intentionally invisible to and unwritable from JavaScript, so client
 * code can't read or forge it. These helpers ask the backend instead of
 * touching `document.cookie` directly, and pass `credentials: "include"` so
 * the cookie is sent across the frontend/backend origin split (see
 * `CORS_ORIGINS` + `allow_credentials=True` in the backend's `main.py`).
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface SessionUser {
  user_id: string;
  [key: string]: unknown;
}

/**
 * Fetch the current session's user data from the backend.
 * Returns `null` when there is no active session (backend responds 401) —
 * this is the expected, non-error "signed out" case, not a failure.
 */
export async function fetchSession(): Promise<SessionUser | null> {
  const response = await fetch(`${API_BASE_URL}/session/me`, {
    credentials: "include",
  });

  if (response.status === 401) {
        const bridgeResult = await (async (): Promise<SessionUser | null> => {
          try {
            const nextAuthRes = await fetch("/api/auth/session");
            if (!nextAuthRes.ok) return null;
            const session = await nextAuthRes.json();
            if (!session?.accessToken) return null;
            const bridgeRes = await fetch(`${API_BASE_URL}/auth/oauth-bridge`, {
              method: "POST",
              credentials: "include",
              headers: { Authorization: `Bearer ${session.accessToken}` },
            });
            if (!bridgeRes.ok) return null;
            return (await bridgeRes.json()) as SessionUser;
          } catch {
            return null;
          }
        })();
        if (bridgeResult) return bridgeResult;
    // PREFAB:session-fetch-bridge
    return null;
  }

  if (!response.ok) {
    throw new Error(`Failed to fetch session: ${response.status}`);
  }

  return (await response.json()) as SessionUser;
}

/**
 * End the current session: the backend deletes the session record and
 * clears the cookie. Resolves even if there was no active session.
 */
export async function logout(): Promise<void> {
  await fetch(`${API_BASE_URL}/session/logout`, {
    method: "POST",
    credentials: "include",
  });
    try {
      const csrfRes = await fetch("/api/auth/csrf");
      const { csrfToken } = await csrfRes.json();
      await fetch("/api/auth/signout", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ csrfToken }),
      });
    } catch {
      // NextAuth signout is best-effort — prefab_session is already cleared
    }
  // PREFAB:session-logout-extra
}
