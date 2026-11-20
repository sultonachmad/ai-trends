/**
 * Payment link calls, staff side (backend: app/routers/payment_links.py).
 */

import { request } from "@/lib/api-client";
import type { LinkState } from "@/lib/payment-link-format";

export type LinkFilter = "all" | LinkState;
export type NotSentReason = "resolved" | "window_closed" | "send_failed";

export interface PaymentLink {
  id: string;
  state: LinkState;
  amount: string;
  total_amount: string | null;
  currency: string;
  description: string | null;
  expires_at: string;
  paid_at: string | null;
  paid_via: string | null;
  created_at: string;
  guest: { id: string | null; name: string; phone: string | null } | null;
  conversation_id: string | null;
  sent_to_chat: boolean;
  /** Money arrived after the link was paid, expired or cancelled; a person must refund it. */
  needs_refund_review: boolean;
}

export interface PaymentLinkPage {
  items: PaymentLink[];
  next_cursor: string | null;
}

export interface CreateLinkInput {
  amount: number;
  description: string;
  total_amount?: number;
  expires_in_hours?: number;
  conversation_id?: string;
}

/** `url` carries the secret token: it is returned once and cannot be fetched again. */
export interface CreatedLink {
  link: PaymentLink;
  url: string;
  sent_to_chat: boolean;
  not_sent_reason: NotSentReason | null;
}

const base = "/api/payment-links";

export function fetchPaymentLinks(
  state: LinkFilter,
  cursor?: string | null,
): Promise<PaymentLinkPage> {
  const params = new URLSearchParams({ state });
  if (cursor) params.set("cursor", cursor);
  return request(`${base}?${params.toString()}`);
}

export function createPaymentLink(input: CreateLinkInput): Promise<CreatedLink> {
  return request(base, { method: "POST", body: JSON.stringify(input) });
}

export function cancelPaymentLink(id: string): Promise<PaymentLink> {
  return request(`${base}/${id}/cancel`, { method: "POST" });
}
