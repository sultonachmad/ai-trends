const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Home() {
  return (
    <div className="flex flex-col gap-8">
      {/* Header */}
      <div className="flex flex-col gap-2">
        <span
          className="inline-flex w-fit items-center rounded-full px-3 py-1 text-xs font-medium"
          style={{
            backgroundColor: "var(--sd-primary-soft, #eef2ff)",
            color: "var(--primary-color)",
          }}
        >
          Powered by Ttest
        </span>
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl text-foreground">
          Welcome back
        </h1>
        <p className="text-secondary">
          Your application dashboard. Edit this page to get started.
        </p>
      </div>

      {/* Quick actions */}
      <div className="flex flex-wrap gap-3">
        <a
          href={`${API_URL}/health`}
          target="_blank"
          rel="noopener noreferrer"
          className="bg-buton rounded-lg text-sm font-semibold"
          style={{ padding: "0.625rem 1.25rem" }}
        >
          Check API Health
        </a>
        <a
          href={`${API_URL}/docs`}
          target="_blank"
          rel="noopener noreferrer"
          className="btn-secondary rounded-lg text-sm font-semibold"
        >
          API Docs
        </a>
      </div>

      {/* Stats cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="bg-sub-section rounded-xl p-6">
          <div className="flex items-center gap-3">
            <div
              className="flex h-10 w-10 items-center justify-center rounded-lg"
              style={{
                backgroundColor: "var(--sd-primary-soft, #eef2ff)",
                color: "var(--primary-color)",
              }}
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
                className="h-5 w-5"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M17.25 6.75 22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3-4.5 16.5"
                />
              </svg>
            </div>
            <div>
              <p className="text-sm text-secondary-color">Stack</p>
              <p className="text-lg font-semibold text-main-color">
                Next.js + FastAPI
              </p>
            </div>
          </div>
        </div>

        <div className="bg-sub-section rounded-xl p-6">
          <div className="flex items-center gap-3">
            <div
              className="flex h-10 w-10 items-center justify-center rounded-lg"
              style={{
                backgroundColor: "var(--sd-primary-soft, #eef2ff)",
                color: "var(--primary-color)",
              }}
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
                className="h-5 w-5"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M9.53 16.122a3 3 0 0 0-5.78 1.128 2.25 2.25 0 0 1-2.4 2.245 4.5 4.5 0 0 0 8.4-2.245c0-.399-.078-.78-.22-1.128Zm0 0a15.998 15.998 0 0 0 3.388-1.62m-5.043-.025a15.994 15.994 0 0 1 1.622-3.395m3.42 3.42a15.995 15.995 0 0 0 4.764-4.648l3.876-5.814a1.151 1.151 0 0 0-1.597-1.597L14.146 6.32a15.996 15.996 0 0 0-4.649 4.763m3.42 3.42a6.776 6.776 0 0 0-3.42-3.42"
                />
              </svg>
            </div>
            <div>
              <p className="text-sm text-secondary-color">Styling</p>
              <p className="text-lg font-semibold text-main-color">
                Tailwind CSS
              </p>
            </div>
          </div>
        </div>

        <div className="bg-sub-section rounded-xl p-6">
          <div className="flex items-center gap-3">
            <div
              className="flex h-10 w-10 items-center justify-center rounded-lg"
              style={{
                backgroundColor: "var(--sd-primary-soft, #eef2ff)",
                color: "var(--primary-color)",
              }}
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
                className="h-5 w-5"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z"
                />
              </svg>
            </div>
            <div>
              <p className="text-sm text-secondary-color">Status</p>
              <p className="text-lg font-semibold text-main-color">
                Ready to Ship
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Getting started */}
      <div className="bg-sub-section rounded-xl p-6">
        <h2 className="text-lg font-semibold text-main-color">Get Started</h2>
        <p className="mt-2 text-sm text-secondary-color">
          Edit{" "}
          <code
            className="rounded px-1.5 py-0.5 font-mono text-xs"
            style={{ backgroundColor: "var(--sub-sub-section-bg)" }}
          >
            app/page.tsx
          </code>{" "}
          to customize this dashboard. The sidebar navigation is in{" "}
          <code
            className="rounded px-1.5 py-0.5 font-mono text-xs"
            style={{ backgroundColor: "var(--sub-sub-section-bg)" }}
          >
            components/Sidebar.tsx
          </code>
          .
        </p>
      </div>
    </div>
  );
}
