/**
 * Route protection middleware — runs on the server (Edge runtime) before
 * any page renders.
 *
 * Only pages inside the `(authenticated)` route group are protected.
 * Public pages (`/about`, `/login`) are accessible without auth.
 * The `(authenticated)` folder is a Next.js route group — it does not
 * appear in the URL path, so protected pages are matched by their
 * actual paths (e.g. `/dashboard`, `/settings`).
 *
 * To protect a new page: place it inside `app/(authenticated)/`.
 * To keep a page public: place it directly in `app/`.
 *
 * `/` 302-redirects to `/login` on the ORIGINAL request (basePath already
 * stripped by Next.js). Other matched paths are delegated to NextAuth's
 * `auth()`, which runs the `authorized` callback in `auth.config.ts`.
 *
 * This file replaces auth-session's `middleware.ts` (manifest
 * `mode: overwrite`), so it carries that redirect too. If the spec has a
 * screen at route `/`, remove `"/"` from `matcher` and the redirect branch
 * below, then build that screen in `app/page.tsx`.
 *
 * Deliberately built from `authConfig` (no providers), NOT from the `auth`
 * export in `lib/nextauth.ts` — that full config holds the providers the
 * provider prefabs splice in, which pull in `openid-client` (Node.js-only APIs
 * that throw at the edge).
 */
import NextAuth from "next-auth";
import { NextResponse } from "next/server";
import type { NextFetchEvent, NextMiddleware, NextRequest } from "next/server";

import { authConfig } from "@/auth.config";

const { auth } = NextAuth(authConfig);
const redirectTo = "/login";

export default function middleware(request: NextRequest, event: NextFetchEvent) {
  if (request.nextUrl.pathname === "/") {
    // clone() keeps basePath + query string on the redirect target.
    const url = request.nextUrl.clone();
    url.pathname = redirectTo;
    return NextResponse.redirect(url, 302);
  }
  // Delegate to NextAuth for auth-protected paths.
  return (auth as unknown as NextMiddleware)(request, event);
}

export const config = {
  // `/` is matched for the redirect above; the rest are the (authenticated)
  // group. Add new protected path prefixes here as you create them.
  matcher: ["/", "/dashboard/:path*", "/settings/:path*", "/protected/:path*"],
};
