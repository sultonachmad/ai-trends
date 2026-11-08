/**
 * Prefab-agnostic seam for attaching an auth token to outgoing API requests.
 *
 * The base skeleton ships a no-op provider, so API clients can always call
 * `getAuthToken()` regardless of whether any auth prefab is installed — when
 * none is, it returns `null` and no `Authorization` header is sent.
 *
 * An auth prefab (e.g. auth-oauth2) calls `setAuthTokenProvider(...)` once, at
 * startup on the client, to register a real provider that reads the current
 * session token. This keeps the CRUD/base API client decoupled from any
 * specific auth library: neither prefab imports the other — they meet here, in
 * a module both depend on transitively through the base skeleton.
 *
 * Contract for API clients: call `await getAuthToken()` and, when it returns a
 * non-null string, send it as `Authorization: Bearer <token>`.
 */

type TokenProvider = () => Promise<string | null> | string | null;

let provider: TokenProvider = () => null;

/** Register the provider that resolves the current auth token (client-side). */
export function setAuthTokenProvider(next: TokenProvider): void {
  provider = next;
}

/** Resolve the current auth token, or `null` when unauthenticated / no auth prefab. */
export async function getAuthToken(): Promise<string | null> {
  try {
    return (await provider()) ?? null;
  } catch {
    // A failing provider must never break an API call — degrade to anonymous.
    return null;
  }
}
