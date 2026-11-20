/**
 * Transfer proof calls, staff side (backend: app/routers/transfer_proofs.py).
 */

import { request, requestBlob } from "@/lib/api-client";

export type ProofState = "awaiting" | "awaiting_second" | "approved" | "rejected";
export type ProofFilter = "awaiting" | "approved" | "rejected";

export interface Proof {
  id: string;
  state: ProofState;
  amount: string | null;
  description: string | null;
  guest: { id: string | null; name: string; phone: string | null } | null;
  payment_link_id: string | null;
  conversation_id: string | null;
  submitted_by_guest: boolean;
  uploaded_by_name: string | null;
  created_at: string;
  needs_second_approval: boolean;
  first_approved_by_name: string | null;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  rejection_reason: string | null;
  duplicate_of: { id: string; description: string | null; created_at: string } | null;
  image_available: boolean;
}

export interface ProofPage {
  items: Proof[];
  next_cursor: string | null;
}

/** Either a pay link, or an amount and what it was for (a transfer that had no link). */
export type ProofTarget =
  | { payment_link_id: string }
  | { amount: number; description: string; conversation_id?: string };

const base = "/api/transfer-proofs";

export function fetchProofs(state: ProofFilter, cursor?: string | null): Promise<ProofPage> {
  const params = new URLSearchParams({ state });
  if (cursor) params.set("cursor", cursor);
  return request(`${base}?${params.toString()}`);
}

export function uploadStaffProof(file: File, target: ProofTarget): Promise<Proof> {
  const body = new FormData();
  body.append("file", file);
  for (const [key, value] of Object.entries(target)) {
    if (value !== undefined) body.append(key, String(value));
  }
  return request<Proof>(base, { method: "POST", body });
}

export const fetchProofImage = (id: string) => requestBlob(`${base}/${id}/image`);
export const approveProof = (id: string) =>
  request<Proof>(`${base}/${id}/approve`, { method: "POST" });
export const rejectProof = (id: string, reason: string) =>
  request<Proof>(`${base}/${id}/reject`, { method: "POST", body: JSON.stringify({ reason }) });
