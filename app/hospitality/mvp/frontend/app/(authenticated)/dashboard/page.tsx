"use client";

import { useEffect, useState } from "react";
import { useSessionState } from "@/components/SessionProvider";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface DashboardData {
  greeting: string;
  items_count: number;
}

/**
 * Sample authenticated page — no individual auth check needed.
 *
 * This page lives inside the `(authenticated)` route group, so the
 * layout.tsx already handles the auth guard. It is reachable at `/dashboard`.
 *
 * Delete this page once you've built your own — it exists only as a
 * working reference.
 */
export default function DashboardPage() {
  const { user } = useSessionState();
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/protected/dashboard-data`, { credentials: "include" })
      .then(async (res) => {
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        return res.json();
      })
      .then(setData)
      .catch((err) => setError(String(err)));
  }, []);

  return (
    <div className="mx-auto max-w-xl p-8">
      <h1 className="mb-4 text-2xl font-bold">Dashboard</h1>
      <p className="mb-6 text-sm text-gray-500">
        Welcome, {typeof user?.email === "string" ? user.email : "user"}. This page is only visible to authenticated users.
      </p>

      {error && <p className="text-red-600">Failed to load: {error}</p>}

      {!error && !data && <p className="text-gray-500">Loading...</p>}

      {data && (
        <div>
          <p className="text-lg">{data.greeting}</p>
          <p className="mt-2 text-sm text-gray-600">
            You have <strong>{data.items_count}</strong> items.
          </p>
        </div>
      )}
    </div>
  );
}
