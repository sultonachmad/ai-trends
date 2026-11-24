/** Pure helpers for the front desk page. */

import { ApiError } from "@/lib/api-client";
import type { DeskEntry } from "@/lib/front-desk-api";

export const DESK_TABS = ["arrivals", "in_house", "departures", "rooms"] as const;
export type DeskTab = (typeof DESK_TABS)[number];
export const HK_STATUSES = ["dirty", "in_progress", "clean", "inspected"] as const;
export const DESK_ERROR_CODES = [
  "not_found",
  "not_confirmed",
  "outside_stay",
  "rooms_missing",
  "room_out_of_order",
  "room_occupied",
  "room_not_ready",
  "not_in_house",
  "early_choice_needed",
  "cannot_no_show",
  "undo_not_allowed",
  "no_rooms_left",
  "room_taken",
  "wrong_room",
  "room_locked",
  "room_required",
  "not_assignable",
  "price_permission",
] as const;

export const allRoomsAssigned = (entry: Pick<DeskEntry, "rooms">) =>
  entry.rooms.every((room) => room.unit_id !== null);

export const leavesEarly = (entry: Pick<DeskEntry, "departure">, today: string) =>
  today < entry.departure;

export const owesMoney = (entry: Pick<DeskEntry, "balance_due">) =>
  Number(entry.balance_due) > 0;

function refusal(cause: unknown): { code?: string; rooms?: string[] } | null {
  if (!(cause instanceof ApiError) || typeof cause.detail !== "object" || !cause.detail) {
    return null;
  }
  return cause.detail as { code?: string; rooms?: string[] };
}

/** i18n key of a front desk refusal; null for anything else. */
export function deskErrorKey(cause: unknown): string | null {
  const code = refusal(cause)?.code;
  return code && (DESK_ERROR_CODES as readonly string[]).includes(code)
    ? `frontdesk.error.${code}`
    : null;
}

export function isRefusedAs(cause: unknown, code: string): boolean {
  return refusal(cause)?.code === code;
}

export const refusedRooms = (cause: unknown): string[] => refusal(cause)?.rooms ?? [];
