"use client";

import { useSessionState } from "@/components/SessionProvider";

/**
 * Drop this into any header, nav bar, or account menu that needs a way to
 * end the current session. Requires the tree to be wrapped in
 * `<SessionProvider>` (already wired into `frontend/app/layout.tsx` at
 * install time) — see `AGENTS.md`.
 */
export function LogoutButton() {
  const { logout } = useSessionState();

  return (
    <button
      type="button"
      onClick={() => {
        void logout();
      }}
      className="inline-flex items-center px-4 py-2 rounded-md bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 text-sm font-medium hover:bg-gray-50 dark:hover:bg-gray-600"
    >
      Log out
    </button>
  );
}

export default LogoutButton;
