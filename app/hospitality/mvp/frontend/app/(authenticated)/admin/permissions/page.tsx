"use client";

/**
 * /admin/permissions — read-only list of all registered permission codes.
 *
 * Permissions are auto-populated by the server at startup from the
 * `_PERMISSION_REGISTRY` (populated when routers call `require_permission()`).
 * There is no create/edit/delete UI here — permissions are managed by code,
 * not by admins. This page exists for visibility and auditing.
 *
 * Permission guard: permissions:view
 */

import { useEffect, useState } from "react";
import { useRbac } from "@/lib/rbac-store";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Permission {
  id: number;
  code: string;
  description: string | null;
  type: string;
}

const TYPE_COLORS: Record<string, string> = {
  api: "bg-blue-100 text-blue-700",
  menu: "bg-green-100 text-green-700",
  button: "bg-yellow-100 text-yellow-700",
};

export default function PermissionsPage() {
  const { can } = useRbac();
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      const res = await fetch(`${API_URL}/api/permissions`, {
        credentials: "include",
      });
      setPermissions(res.ok ? await res.json() : []);
      setLoading(false);
    };
    load();
  }, []);

  if (!can("permissions:view")) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-red-700">
        Access denied — you need the <code>permissions:view</code> permission.
      </div>
    );
  }

  const filtered = permissions.filter(
    (p) =>
      p.code.toLowerCase().includes(filter.toLowerCase()) ||
      (p.description ?? "").toLowerCase().includes(filter.toLowerCase()),
  );

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Permissions</h1>
          <p className="mt-1 text-sm text-gray-500">
            Auto-synced from backend route decorators at startup. Read-only.
          </p>
        </div>
        <span className="rounded-full bg-gray-100 px-3 py-1 text-sm font-medium text-gray-600">
          {permissions.length} total
        </span>
      </div>

      <div className="mb-4">
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter by code or description…"
          className="w-full max-w-md rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      {loading ? (
        <p className="text-gray-500">Loading…</p>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                  Code
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                  Description
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                  Type
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filtered.map((perm) => (
                <tr key={perm.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-sm text-gray-900">
                    {perm.code}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {perm.description ?? "—"}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${TYPE_COLORS[perm.type] ?? "bg-gray-100 text-gray-600"}`}
                    >
                      {perm.type}
                    </span>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td
                    colSpan={3}
                    className="px-4 py-8 text-center text-sm text-gray-400"
                  >
                    No permissions match the filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
