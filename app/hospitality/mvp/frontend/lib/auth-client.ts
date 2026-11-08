"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { signIn, signOut, useSession } from "next-auth/react";

export { signIn, signOut, useSession };

/**
 * Client-side auth guard hook. Redirects to /login when the session is
 * confirmed unauthenticated; while the session is loading it does nothing.
 *
 * Usage:
 *   const { session, isLoading } = useRequireAuth();
 */
export function useRequireAuth() {
  const { data: session, status } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/login");
    }
  }, [status, router]);

  return { session, status, isLoading: status === "loading" };
}
