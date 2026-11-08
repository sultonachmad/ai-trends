"use client";

/**
 * Layout for all authenticated pages — rbac variant (overwrites auth-session's version).
 *
 * Only wraps with AuthGuard. Navigation is handled by `components/Sidebar.tsx`
 * (overwritten by rbac to read permission-filtered menus from /api/me). When
 * theme-ttest is installed, Sidebar is mounted in the root layout and covers
 * all pages. Without theme-ttest, mount Sidebar in your own root layout.
 *
 * Route group `(authenticated)` does not appear in the URL.
 */

import { AuthGuard } from "@/components/AuthGuard";

export default function AuthenticatedLayout({ children }: { children: React.ReactNode }) {
  return <AuthGuard>{children}</AuthGuard>;
}
