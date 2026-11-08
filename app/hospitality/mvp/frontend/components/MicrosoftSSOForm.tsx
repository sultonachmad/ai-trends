"use client";

import { signIn } from "next-auth/react";

export function MicrosoftSSOForm() {
  // The callback URL is read on click, not during render: the login page has
  // no <Suspense> boundary, and a render-time search-params hook fails static
  // generation of /login.
  const handleClick = () => {
    const callbackUrl =
      new URLSearchParams(window.location.search).get("callbackUrl") ??
      `${process.env.NEXT_PUBLIC_BASE_PATH ?? ""}/dashboard`;
    void signIn("microsoft-entra-id", { callbackUrl });
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      className="btn-secondary inline-flex items-center gap-3 rounded-md text-sm font-medium"
    >
      Sign in with Microsoft
    </button>
  );
}
