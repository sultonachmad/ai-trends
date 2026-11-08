"use client";

/**
 * Client provider root — rbac variant (overwrites auth-session's version).
 *
 * Nests RbacProvider inside SessionProvider so that:
 *   1. SessionProvider establishes the session context (auth state)
 *   2. RbacProvider fetches /api/me using the session cookie and stores
 *      the user's roles, permissions, and nav menus
 *
 * RbacProvider is only useful inside authenticated pages — it will get a 401
 * from /api/me on public pages, which it handles gracefully (sets loading=false,
 * permissions=[], menus=[]).
 */

import type { ReactNode } from "react";
import { SessionProvider } from "@/components/SessionProvider";
import { RbacProvider } from "@/lib/rbac-store";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <SessionProvider>
      <RbacProvider>{children}</RbacProvider>
    </SessionProvider>
  );
}
