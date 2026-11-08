"use client";

/**
 * /admin/roles/[id] — role detail with a full permission-assignment matrix.
 *
 * Loads the role + all available permissions + currently assigned permissions.
 * Renders a checkbox grid grouped by permission type (api / menu / button).
 * Saving replaces the role's permission set via PUT /api/roles/{id}/permissions.
 *
 * Permission guards:
 *   - Page view: roles:view
 *   - Save button: roles:edit
 */

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { RbacGuard } from "@/components/RbacGuard";
import { useRbac } from "@/lib/rbac-store";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Role {
  id: number;
  name: string;
  description: string | null;
}

interface Permission {
  id: number;
  code: string;
  description: string | null;
  type: string;
}

export default function RoleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { can } = useRbac();

  const [role, setRole] = useState<Role | null>(null);
  const [allPermissions, setAllPermissions] = useState<Permission[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      const [roleRes, allPermsRes, rolePermsRes] = await Promise.all([
        fetch(`${API_URL}/api/roles/${id}`, { credentials: "include" }),
        fetch(`${API_URL}/api/permissions`, { credentials: "include" }),
        fetch(`${API_URL}/api/roles/${id}/permissions`, {
          credentials: "include",
        }),
      ]);
      if (!roleRes.ok) {
        router.push("/admin/roles");
        return;
      }
      const [roleData, allPermsData, rolePermsData] = await Promise.all([
        roleRes.json(),
        allPermsRes.ok ? allPermsRes.json() : [],
        rolePermsRes.ok ? rolePermsRes.json() : [],
      ]);
      setRole(roleData);
      setAllPermissions(allPermsData);
      setSelected(new Set((rolePermsData as Permission[]).map((p) => p.id)));
      setLoading(false);
    };
    load();
  }, [id, router]);

  const toggle = (permId: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(permId) ? next.delete(permId) : next.add(permId);
      return next;
    });
  };

  const save = async () => {
    setSaving(true);
    await fetch(`${API_URL}/api/roles/${id}/permissions`, {
      method: "PUT",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify([...selected]),
    });
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  if (!can("roles:view")) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-red-700">
        Access denied — you need the <code>roles:view</code> permission.
      </div>
    );
  }

  if (loading) return <p className="text-gray-500">Loading…</p>;
  if (!role) return null;

  const byType = allPermissions.reduce(
    (acc, p) => {
      const group = p.type ?? "api";
      return { ...acc, [group]: [...(acc[group] ?? []), p] };
    },
    {} as Record<string, Permission[]>,
  );

  return (
    <div className="max-w-2xl p-8">
      <div className="mb-6 flex items-center gap-4">
        <button
          onClick={() => router.push("/admin/roles")}
          className="text-sm text-indigo-600 hover:underline"
        >
          ← Roles
        </button>
        <h1 className="text-2xl font-bold text-gray-900">{role.name}</h1>
        {role.description && (
          <span className="text-sm text-gray-500">{role.description}</span>
        )}
      </div>

      <div className="space-y-6">
        {Object.entries(byType).map(([type, perms]) => (
          <div
            key={type}
            className="rounded-lg border border-gray-200 bg-white p-4"
          >
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
              {type}
            </h2>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {perms.map((perm) => (
                <label
                  key={perm.id}
                  className="flex cursor-pointer items-start gap-2 rounded-md p-2 hover:bg-gray-50"
                >
                  <input
                    type="checkbox"
                    checked={selected.has(perm.id)}
                    onChange={() => toggle(perm.id)}
                    disabled={!can("roles:edit")}
                    className="mt-0.5 h-4 w-4 rounded border-gray-300 text-indigo-600"
                  />
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-900">
                      {perm.code}
                    </p>
                    {perm.description && (
                      <p className="truncate text-xs text-gray-400">
                        {perm.description}
                      </p>
                    )}
                  </div>
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-6 flex items-center gap-3">
        <RbacGuard permission="roles:edit">
          <button
            onClick={save}
            disabled={saving}
            className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save permissions"}
          </button>
        </RbacGuard>
        {saved && <span className="text-sm text-green-600">✓ Saved</span>}
      </div>
    </div>
  );
}
