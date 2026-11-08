"use client";

/**
 * /admin/roles — role list with create, edit, delete, and permission drill-down.
 *
 * Permission guards:
 *   - Page view: roles:view
 *   - Create button: roles:add
 *   - Edit button: roles:edit
 *   - Delete button: roles:delete
 *   - Permission matrix link: roles:edit
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { RbacGuard } from "@/components/RbacGuard";
import { useRbac } from "@/lib/rbac-store";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Role {
  id: number;
  name: string;
  description: string | null;
}

function RoleFormModal({
  initial,
  onClose,
  onSaved,
}: {
  initial: Role | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    if (!name.trim()) return setError("Name is required");
    setSaving(true);
    setError(null);
    const res = await fetch(
      initial ? `${API_URL}/api/roles/${initial.id}` : `${API_URL}/api/roles`,
      {
        method: initial ? "PATCH" : "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          description: description || null,
        }),
      },
    );
    setSaving(false);
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      setError(data.detail ?? "Save failed");
      return;
    }
    onSaved();
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-sm rounded-lg bg-card text-card-foreground p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-semibold">
          {initial ? "Edit role" : "New role"}
        </h2>
        {error && (
          <p className="mb-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}
        <div className="mb-3">
          <label className="mb-1 block text-sm font-medium text-gray-700">
            Name
          </label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div className="mb-4">
          <label className="mb-1 block text-sm font-medium text-gray-700">
            Description
          </label>
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-md border px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={save}
            disabled={saving}
            className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function RolesPage() {
  const { can } = useRbac();
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState<"new" | Role | null>(null);

  const load = async () => {
    setLoading(true);
    const res = await fetch(`${API_URL}/api/roles`, { credentials: "include" });
    setRoles(res.ok ? await res.json() : []);
    setLoading(false);
  };

  const deleteRole = async (id: number) => {
    if (!confirm("Delete this role?")) return;
    await fetch(`${API_URL}/api/roles/${id}`, {
      method: "DELETE",
      credentials: "include",
    });
    load();
  };

  useEffect(() => {
    load();
  }, []);

  if (!can("roles:view")) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-red-700">
        Access denied — you need the <code>roles:view</code> permission.
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Roles</h1>
        <RbacGuard permission="roles:add">
          <button
            onClick={() => setModal("new")}
            className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
          >
            + New role
          </button>
        </RbacGuard>
      </div>

      {loading ? (
        <p className="text-gray-500">Loading…</p>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                  Name
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                  Description
                </th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {roles.map((role) => (
                <tr key={role.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">
                    {role.name}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {role.description ?? "—"}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-2">
                      <RbacGuard permission="roles:edit">
                        <Link
                          href={`/admin/roles/${role.id}`}
                          className="rounded-md bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-100"
                        >
                          Permissions
                        </Link>
                        <button
                          onClick={() => setModal(role)}
                          className="rounded-md bg-gray-50 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-100"
                        >
                          Edit
                        </button>
                      </RbacGuard>
                      <RbacGuard permission="roles:delete">
                        <button
                          onClick={() => deleteRole(role.id)}
                          className="rounded-md bg-red-50 px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-100"
                        >
                          Delete
                        </button>
                      </RbacGuard>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {modal !== null && (
        <RoleFormModal
          initial={modal === "new" ? null : modal}
          onClose={() => setModal(null)}
          onSaved={load}
        />
      )}
    </div>
  );
}
