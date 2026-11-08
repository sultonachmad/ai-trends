"use client";

import { signIn } from "next-auth/react";

export function GoogleSSOForm() {
  // The callback URL is read on click, not during render: the login page has
  // no <Suspense> boundary, and a render-time search-params hook fails static
  // generation of /login. `/` redirects to `/login`, so default to the dashboard.
  const handleClick = () => {
    const callbackUrl =
      new URLSearchParams(window.location.search).get("callbackUrl") ??
      `${process.env.NEXT_PUBLIC_BASE_PATH ?? ""}/dashboard`;
    void signIn("google", { callbackUrl });
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      className="btn-secondary inline-flex items-center gap-3 rounded-md text-sm font-medium"
    >
      <svg className="h-5 w-5" viewBox="0 0 24 24" aria-hidden="true">
        <path
          fill="#4285F4"
          d="M23.49 12.27c0-.79-.07-1.54-.19-2.27H12v4.51h6.47c-.29 1.48-1.14 2.73-2.4 3.58v3h3.86c2.26-2.09 3.56-5.17 3.56-8.82z"
        />
        <path
          fill="#34A853"
          d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.86-3c-1.08.72-2.45 1.16-4.07 1.16-3.13 0-5.78-2.11-6.73-4.96H1.29v3.09C3.26 21.3 7.31 24 12 24z"
        />
        <path
          fill="#FBBC05"
          d="M5.27 14.29a7.2 7.2 0 0 1 0-4.58V6.62H1.29a12 12 0 0 0 0 10.76z"
        />
        <path
          fill="#EA4335"
          d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.94 1.19 15.24 0 12 0 7.31 0 3.26 2.7 1.29 6.62l3.98 3.09C6.22 6.86 8.87 4.75 12 4.75z"
        />
      </svg>
      Sign in with Google
    </button>
  );
}
