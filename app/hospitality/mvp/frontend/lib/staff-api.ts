/** The team and join links (backend: app/routers/staff.py). */

import { request } from "@/lib/api-client";

export type StaffRole = "manager" | "front_desk" | "housekeeper";

export interface Invite {
  id: string;
  name: string | null;
  email: string;
  role: StaffRole;
  created_at: string;
  expires_at: string;
}

export interface Member {
  staff_id: string;
  name: string;
  email: string | null;
  role: StaffRole | "custom";
  is_owner: boolean;
  is_me: boolean;
  joined_at: string | null;
}

export interface Team {
  members: Member[];
  invites: Invite[];
}

export interface JoinPreview {
  workspace: string;
  name: string | null;
  email_hint: string;
  role: StaffRole;
  state: "open" | "expired" | "used" | "revoked";
}

const json = (method: string, body?: unknown) => ({
  method,
  ...(body === undefined ? {} : { body: JSON.stringify(body) }),
});

export const fetchTeam = () => request<Team>("/api/staff");
export const createInvite = (name: string, email: string, role: StaffRole) =>
  request<{ invite: Invite; token: string }>("/api/staff/invites", json("POST", { name, email, role }));
export const revokeInvite = (id: string) => request<Team>(`/api/staff/invites/${id}/revoke`, json("POST"));
export const changeRole = (staffId: string, role: StaffRole) =>
  request<Team>(`/api/staff/${staffId}/role`, json("PUT", { role }));
export const removeMember = (staffId: string) => request<Team>(`/api/staff/${staffId}/remove`, json("POST"));
export const previewJoin = (token: string) =>
  request<JoinPreview>(`/api/join/${encodeURIComponent(token)}`);
export const acceptJoin = (token: string) =>
  request<{ role: StaffRole }>(`/api/join/${encodeURIComponent(token)}`, json("POST"));
