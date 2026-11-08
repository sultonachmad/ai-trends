/**
 * Server-side auth helpers.
 *
 * The NextAuth instance itself is defined in the NextAuth config file
 * (`lib/nextauth.ts`); this module re-exports the
 * server-side pieces so Server Components, Route Handlers, and Server
 * Actions have a single, conventional import path (`@/lib/auth`).
 */
import { redirect } from "next/navigation";

import { auth as nextAuthSession } from "@/lib/nextauth";

/** Returns the current session, or `null` when unauthenticated. */
export const auth = nextAuthSession;

/**
 * Backward-compatible alias for code migrated from NextAuth v4's
 * `getServerSession()`. Prefer `auth()` in new code.
 */
export async function getServerSession() {
  return nextAuthSession();
}

/**
 * Server Component / Server Action guard. Redirects to /login when there is
 * no active session; otherwise returns the session's user. Prefer this over
 * `AuthGuard` for Server Components — it redirects before any render
 * happens, avoiding a flash of protected content.
 */
export async function requireAuth() {
  const session = await nextAuthSession();
  if (!session?.user) {
    redirect("/login");
  }
  return session.user;
}
