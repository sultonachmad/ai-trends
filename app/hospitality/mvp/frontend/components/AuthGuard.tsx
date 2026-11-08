"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSessionState } from "@/components/SessionProvider";

/**
 * Wraps its children in a session-based auth check. Shows a loading spinner
 * while the session is being resolved, redirects to / when unauthenticated,
 * and renders the children once the session is confirmed.
 *
 * This is the auth-session variant — uses `useSessionState()` instead of
 * NextAuth's `useSession()`.
 */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loading } = useSessionState();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [loading, isAuthenticated, router]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div
          role="status"
          aria-label="Loading"
          className="h-8 w-8 animate-spin rounded-full border-2 border-gray-300 border-t-gray-900 dark:border-gray-700 dark:border-t-white"
        />
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}

export default AuthGuard;
