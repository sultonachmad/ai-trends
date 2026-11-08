"use client";

/**
 * /admin/users — user list with inline role assignment.
 *
 * Lists all users returned by GET /api/users. For each user, shows their
 * current roles and (if the viewer has users:edit) lets them reassign roles
 * via PUT /api/users/{id}/roles.
 *
 * Permission guards:
 *   - Viewing the page: users:view (page-level, shows "Access denied" if absent)
 *   - Role assignment UI: users:edit (button-level, hidden if absent)
 */

import { useEffect, useState } from "react";
import { RbacGuard } from "@/components/RbacGuard";
import { useRbac } from "@/lib/rbac-store";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface User {
  id: number;
  email: string;
  roles: string[];
}

interface Role {
  id: number;
  name: string;
  description: string | null;
}

function AssignRolesModal({
  user,
  allRoles,
  onClose,
  onSaved,
}: {
  user: User;
  allRoles: Role[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const currentRoleIds = new Set(
      allRoles.filter((r) => user.roles.includes(r.name)).map((r) => r.id),
    );
    setSelected(currentRoleIds);
  }, [user, allRoles]);

  const toggle = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const save = async () => {
    setSaving(true);
    await fetch(`${API_URL}/api/users/${user.id}/roles`, {
      method: "PUT",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify([...selected]),
    });
    setSaving(false);
    onSaved();
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-sm rounded-lg bg-card text-card-foreground p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-semibold">
          Assign roles — {user.email}
        </h2>
        <div className="mb-4 space-y-2">
          {allRoles.map((role) => (
            <label key={role.id} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={selected.has(role.id)}
                onChange={() => toggle(role.id)}
                className="h-4 w-4 rounded border-gray-300"
              />
              <span className="font-medium">{role.name}</span>
              {role.description && (
                <span className="text-gray-400">— {role.description}</span>
              )}
            </label>
          ))}
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

export default function UsersPage() {
  const { can } = useRbac();
  const [users, setUsers] = useState<User[]>([]);
  const [allRoles, setAllRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [editUser, setEditUser] = useState<User | null>(null);

  const load = async () => {
    setLoading(true);
    const [usersRes, rolesRes] = await Promise.all([
      fetch(`${API_URL}/api/users`, { credentials: "include" }),
      fetch(`${API_URL}/api/roles`, { credentials: "include" }),
    ]);
    setUsers(usersRes.ok ? await usersRes.json() : []);
    setAllRoles(rolesRes.ok ? await rolesRes.json() : []);
    setLoading(false);
  };

  useEffect(() => {
    load();
  }, []);

  if (!can("users:view")) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-red-700">
        Access denied — you need the <code>users:view</code> permission.
      </div>
    );
  }

  return (
    <div className="p-8">
      <h1 className="mb-6 text-2xl font-bold text-gray-900">Users</h1>

      {loading ? (
        <p className="text-gray-500">Loading…</p>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                  ID
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                  Email
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                  Roles
                </th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm text-gray-500">{u.id}</td>
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">
                    {u.email}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {u.roles.length === 0 ? (
                        <span className="text-xs text-gray-400">No roles</span>
                      ) : (
                        u.roles.map((r) => (
                          <span
                            key={r}
                            className="rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700"
                          >
                            {r}
                          </span>
                        ))
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <RbacGuard permission="users:edit">
                      <button
                        onClick={() => setEditUser(u)}
                        className="rounded-md bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-100"
                      >
                        Assign roles
                      </button>
                    </RbacGuard>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editUser && (
        <AssignRolesModal
          user={editUser}
          allRoles={allRoles}
          onClose={() => setEditUser(null)}
          onSaved={load}
        />
      )}
    </div>
  );
}
