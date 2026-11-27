/** Pure helpers for repair requests and the monthly tax page. */

import { ApiError } from "@/lib/api-client";
import type { Category, MaintBoard, MaintRequest } from "@/lib/maintenance-api";
import type { TaxAmounts } from "@/lib/tax-summary-api";

export const CATEGORIES: readonly Category[] = [
  "ac",
  "plumbing",
  "electrical",
  "furniture",
  "tv_wifi",
  "door_lock",
  "other",
];
export const LIVE = ["open", "assigned", "in_progress", "waiting_parts"] as const;
export const STEPS = [...LIVE, "completed", "cancelled"] as const;
export const MAX_OFF_SALE_NIGHTS = 90;

export const isLive = (request: MaintRequest) => (LIVE as readonly string[]).includes(request.status);

/** Open requests first (urgent, then oldest), then the finished ones, newest first. */
export function ordered(requests: MaintRequest[]): MaintRequest[] {
  const live = requests
    .filter(isLive)
    .sort((a, b) => Number(b.urgent) - Number(a.urgent) || a.reported_at.localeCompare(b.reported_at));
  const done = requests.filter((r) => !isLive(r)).sort((a, b) => b.reported_at.localeCompare(a.reported_at));
  return [...live, ...done];
}

export function mineOrFree(board: MaintBoard): MaintRequest[] {
  return ordered(board.requests).filter(
    (r) => isLive(r) && (r.mine || (r.assigned_staff_id === null && r.vendor_name === null)),
  );
}

/** What can be done next, for someone who may work the request. */
export function nextSteps(request: MaintRequest): ("start" | "wait" | "fix")[] {
  if (!isLive(request)) return [];
  if (request.status === "in_progress") return ["wait", "fix"];
  if (request.status === "waiting_parts") return ["start", "fix"];
  return ["start", "fix"];
}

export function addDays(iso: string, days: number): string {
  const date = new Date(`${iso}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

/** A problem with the chosen nights, as an i18n key; null when they are fine. */
export function nightsProblem(first: string, last: string, today: string): string | null {
  if (!first || !last || first < today) return "repair.offSale.fromToday";
  if (last < first) return "repair.offSale.order";
  if (last >= addDays(first, MAX_OFF_SALE_NIGHTS)) return "repair.offSale.tooLong";
  return null;
}

/** A cost typed as "150.000" or "150000"; null when empty; NaN when not a number. */
export function parseCost(raw: string): number | null {
  const cleaned = raw.replace(/[.\s]/g, "").replace(",", ".");
  if (!cleaned) return null;
  const value = Number(cleaned);
  return Number.isFinite(value) && value >= 0 ? value : Number.NaN;
}

export const REPAIR_ERROR_CODES = [
  "request_not_found",
  "where_needed",
  "request_closed",
  "not_your_request",
  "note_needed",
  "no_room",
  "bad_nights",
  "room_booked",
  "would_oversell",
  "not_off_sale",
  "bad_photo",
  "unknown_staff",
  "supervisor_needed",
  "already_off_sale",
] as const;

/** i18n key and the items (booking numbers or nights) of a repair refusal. */
export function repairError(cause: unknown): { key: string; items: string[] } | null {
  if (!(cause instanceof ApiError) || typeof cause.detail !== "object" || !cause.detail) return null;
  const detail = cause.detail as { code?: string; items?: string[] };
  if (!detail.code || !(REPAIR_ERROR_CODES as readonly string[]).includes(detail.code)) return null;
  return { key: `repair.error.${detail.code}`, items: detail.items ?? [] };
}

/** `YYYY-MM` of a date, and the month before or after. */
export const monthOf = (iso: string) => iso.slice(0, 7);
export function shiftMonth(month: string, by: number): string {
  const [year, number] = month.split("-").map(Number);
  const date = new Date(Date.UTC(year, number - 1 + by, 1));
  return date.toISOString().slice(0, 7);
}

export function taxTotal(amounts: TaxAmounts): number {
  return Number(amounts.service) + Number(amounts.pbjt);
}
