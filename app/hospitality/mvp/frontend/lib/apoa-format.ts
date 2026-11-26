/** Pure helpers for the APOA page: deadlines, form checks and refusal messages. */

import { ApiError } from "@/lib/api-client";
import { guestIdErrorKey } from "@/lib/id-format";

export const APOA_TABS = ["to_report", "to_check_out", "done"] as const;
export type ApoaTab = (typeof APOA_TABS)[number];
export const APOA_ERROR_CODES = [
  "guest_not_on_booking",
  "not_foreign",
  "not_checked_in",
  "not_checked_out",
  "already_marked",
  "arrival_first",
  "departure_first",
  "not_marked",
  "register_range",
  "arrival_skipped",
  "apoa_marked",
  "register_too_large",
] as const;

const HOUR_MS = 60 * 60 * 1000;
const REFERENCE_MAX = 80;
const REASON_MIN = 3;
const REASON_MAX = 300;
// Same rule as the server: no markup, control characters, line separators or direction tricks.
const UNSAFE = /[<>\u0000-\u001f\u007f-\u009f\u2028\u2029\u202a-\u202e\u2066-\u2069]/;

/** "Due in 5 h" or "Late by 1 h", rounded up to whole hours; null without a deadline. */
export function dueLabel(dueAt: string | null, now: Date = new Date()) {
  if (!dueAt) return null;
  const left = new Date(dueAt).getTime() - now.getTime();
  const hours = Math.max(1, Math.ceil(Math.abs(left) / HOUR_MS));
  return left >= 0 ? { key: "apoa.dueIn", hours } : { key: "apoa.lateBy", hours };
}

type Checked<T> = { ok: true; value: T } | { ok: false; key: string };

export function checkReference(text: string): Checked<string | null> {
  const value = text.trim();
  if (!value) return { ok: true, value: null };
  if (value.length > REFERENCE_MAX || UNSAFE.test(value)) return { ok: false, key: "apoa.badReference" };
  return { ok: true, value };
}

export function checkReason(text: string): Checked<string> {
  const value = text.trim();
  if (value.length < REASON_MIN || value.length > REASON_MAX || UNSAFE.test(value)) {
    return { ok: false, key: "apoa.needReason" };
  }
  return { ok: true, value };
}

/** The register's dates: this month by default, start before end. */
export function registerRange(today: string, from: string, to: string): Checked<{ from: string; to: string }> {
  const start = from || `${today.slice(0, 7)}-01`;
  const end = to || today;
  return start <= end ? { ok: true, value: { from: start, to: end } } : { ok: false, key: "apoa.badRange" };
}

/** i18n key of an APOA, guest ID or front desk refusal; null for anything else. */
export function apoaErrorKey(cause: unknown): string | null {
  if (cause instanceof ApiError && typeof cause.detail === "object" && cause.detail) {
    const code = (cause.detail as { code?: string }).code;
    if (code && (APOA_ERROR_CODES as readonly string[]).includes(code)) return `apoa.error.${code}`;
  }
  return guestIdErrorKey(cause);
}
