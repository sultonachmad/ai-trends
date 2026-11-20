/**
 * Public pay page calls (backend: app/routers/checkout.py, simulator). No sign-in:
 * the link token in the path is the credential.
 */

import { request } from "@/lib/api-client";
import type { LinkState } from "@/lib/payment-link-format";

export interface PayInstructions {
  reference: string;
  method: "qris" | "virtual_account";
  qris_payload: string | null;
  va_bank: string | null;
  va_number: string | null;
}

export interface PublicLink {
  property_name: string;
  description: string | null;
  amount: string;
  total_amount: string | null;
  currency: string;
  expires_at: string;
  state: LinkState;
  paid_at: string | null;
  methods: string[];
  banks: string[];
  instructions: PayInstructions | null;
  simulator_enabled: boolean;
  /** Where to send a manual bank transfer; null when the property takes none. */
  manual_transfer: {
    bank_name: string;
    account_number: string;
    account_holder: string;
    max_upload_mb: number;
  } | null;
  /** The guest's latest transfer proof on this link, if any. */
  proof: { state: "checking" | "rejected"; reason: string | null } | null;
}

const path = (token: string) => `/api/pay/${encodeURIComponent(token)}`;

export const fetchPublicLink = (token: string) => request<PublicLink>(path(token));

export const startPayment = (token: string, method: string, bank?: string) =>
  request<PayInstructions>(`${path(token)}/payments`, {
    method: "POST",
    body: JSON.stringify(bank ? { method, bank } : { method }),
  });

/** Development only: report the attempt with `reference` (the one on screen) as paid. */
export const simulatePayment = (token: string, reference?: string) =>
  request<PublicLink>(`/api/simulator/payments/${encodeURIComponent(token)}/pay`, {
    method: "POST",
    body: JSON.stringify(reference ? { reference } : {}),
  });

/** Upload a transfer screenshot. `consent` is the guest's agreement to the storage notice. */
export function uploadProof(token: string, file: File, consent: boolean): Promise<PublicLink> {
  const body = new FormData();
  body.append("file", file);
  body.append("consent", consent ? "true" : "false");
  return request<PublicLink>(`${path(token)}/proofs`, { method: "POST", body });
}
