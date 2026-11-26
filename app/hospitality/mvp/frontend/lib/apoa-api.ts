/** Foreign guests and APOA reporting (backend: app/routers/apoa.py). */

import { requestBlob, request } from "@/lib/api-client";

export type ApoaStep = "arrival" | "departure";
export type StepStatus = "pending" | "submitted" | "not_required";

export interface StepState {
  status: StepStatus;
  at: string | null;
  by: string | null;
  reference: string | null;
  reason: string | null;
}

export interface ApoaItem {
  booking_id: string;
  booking_number: string;
  guest_id: string;
  document_id: string;
  full_name: string;
  nationality: string;
  /** "••••4567"; null once the number was deleted after retention. */
  masked_number: string | null;
  visa_type: string | null;
  room: string | null;
  checked_in_at: string;
  checked_out_at: string | null;
  /** What is due next; null when both steps are done. */
  step: ApoaStep | null;
  due_at: string | null;
  overdue: boolean;
  has_image: boolean;
  arrival: StepState;
  departure: StepState;
}

export interface Unregistered {
  booking_id: string;
  booking_number: string;
  guest_name: string;
  listed: number;
  expected: number;
}

export interface ApoaList {
  date: string;
  deadline_hours: number;
  to_report: ApoaItem[];
  to_check_out: ApoaItem[];
  done: ApoaItem[];
  unregistered: Unregistered[];
  /** More stays than the list shows; the oldest check-outs are left out. */
  truncated: boolean;
}

interface StepInput {
  booking_id: string;
  guest_id: string;
  step: ApoaStep;
}

const base = "/api/apoa";
const json = (method: string, body: unknown) => ({ method, body: JSON.stringify(body) });

export const fetchApoa = () => request<ApoaList>(base);
export const markApoa = (input: StepInput, reference: string | null) =>
  request<ApoaList>(`${base}/marks`, json("POST", { ...input, reference }));
export const apoaNotRequired = (input: StepInput, reason: string) =>
  request<ApoaList>(`${base}/not-required`, json("POST", { ...input, reason }));
export const undoApoa = (input: StepInput, reason: string) =>
  request<ApoaList>(`${base}/undo`, json("POST", { ...input, reason }));
export const fetchRegister = (from: string, to: string) =>
  requestBlob(`${base}/register?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`);
