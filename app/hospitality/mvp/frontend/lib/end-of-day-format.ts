/** Pure helpers for cash drawers and closing a day. */

import { ApiError } from "@/lib/api-client";
import type { DayCheck } from "@/lib/end-of-day-api";
import { deskErrorKey } from "@/lib/front-desk-format";
import { parseRupiah } from "@/lib/money";

export const END_OF_DAY_ERROR_CODES = [
  "no_staff_profile",
  "drawer_open",
  "no_drawer",
  "note_needed",
  "day_not_over",
  "day_blocked",
  "override_permission",
  "day_closed",
  "already_closed",
  "not_closed",
  "reopen_latest_first",
  "too_many_open_days",
  "before_first_day",
  "drawer_closed",
  "stale_drawer",
] as const;
export const CHECK_CODES = [
  "arrivals_pending",
  "departures_pending",
  "drawers_open",
  "proofs_waiting",
  "apoa_overdue",
  "left_unpaid",
] as const;

const DAY_MS = 24 * 60 * 60 * 1000;

/** "2026-11-30" for "2026-12-01". Dates are property dates as "YYYY-MM-DD". */
export function dayBefore(iso: string): string {
  return new Date(new Date(`${iso}T00:00:00Z`).getTime() - DAY_MS).toISOString().slice(0, 10);
}

type Counted = { ok: true; value: number; difference: number } | { ok: false; key: string };

/** A rupiah amount that may also be zero (an empty drawer, no float). */
export function parseCash(input: string): number | null {
  return /^\s*(rp\.?\s*)?0\s*$/i.test(input) ? 0 : parseRupiah(input);
}

/** The counted cash and its difference from what the drawer should hold. */
export function checkCount(counted: string, expected: string): Counted {
  const value = parseCash(counted);
  if (value === null) return { ok: false, key: "drawer.badAmount" };
  return { ok: true, value, difference: value - Number(expected) };
}

export const needsNote = (difference: number, note: string) =>
  difference !== 0 && note.trim().length === 0;

/** What went wrong, kept untranslated so a language switch shows it in the new language. */
export type Problem = { key: string } | { text: string };

export function problemOf(cause: unknown): Problem {
  const key = endOfDayErrorKey(cause);
  return key ? { key } : { text: cause instanceof Error ? cause.message : String(cause) };
}

export const blockingChecks = (checks: DayCheck[]) =>
  checks.filter((check) => check.level === "blocking");

/** i18n key of an end-of-day, drawer or front desk refusal; null for anything else. */
export function endOfDayErrorKey(cause: unknown): string | null {
  if (cause instanceof ApiError && typeof cause.detail === "object" && cause.detail) {
    const code = (cause.detail as { code?: string }).code;
    if (code && (END_OF_DAY_ERROR_CODES as readonly string[]).includes(code)) {
      return `endofday.error.${code}`;
    }
  }
  return deskErrorKey(cause);
}
