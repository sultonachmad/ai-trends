/** Pure helpers for the public booking pages. Dates are "YYYY-MM-DD" at the property. */

import { ApiError } from "@/lib/api-client";
import type { RateOption, StayQuery } from "@/lib/booking-page-api";

const DAY_MS = 86_400_000;
const utc = (iso: string) => Date.parse(`${iso}T00:00:00Z`);
const SLUG = /^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$/;

export const ERROR_CODES = [
  "not_found",
  "sold_out",
  "closed",
  "min_stay",
  "price_changed",
  "too_many_holds",
  "terms_required",
  "invalid_phone",
  "invalid_dates",
  "stay_too_long",
  "past_arrival",
  "too_far_ahead",
  "too_many_guests",
  "not_for_sale",
  "amount_out_of_range",
  "key_reused",
  "cannot_cancel",
  "accept_no_refund",
  "unknown",
] as const;

export function addDays(iso: string, days: number): string {
  return new Date(utc(iso) + days * DAY_MS).toISOString().slice(0, 10);
}

export function nightsBetween(arrival: string, departure: string): number {
  return Math.round((utc(departure) - utc(arrival)) / DAY_MS);
}

/** First and last day of the month containing `iso`. */
export function monthRange(iso: string): { from: string; to: string } {
  const [year, month] = iso.split("-").map(Number);
  const last = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const prefix = iso.slice(0, 7);
  return { from: `${prefix}-01`, to: `${prefix}-${String(last).padStart(2, "0")}` };
}

/** The first day of the month `delta` months away. */
export function shiftMonth(iso: string, delta: number): string {
  const [year, month] = iso.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1 + delta, 1)).toISOString().slice(0, 10);
}

/** Empty cells before the 1st in a Monday-first grid. */
export function leadingBlanks(firstOfMonth: string): number {
  return (new Date(utc(firstOfMonth)).getUTCDay() + 6) % 7;
}

/** "500rb", "1,2jt": short enough for a phone calendar cell. */
export function compactPrice(value: string | number): string {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return "";
  if (amount >= 1_000_000) {
    return `${(Math.round(amount / 100_000) / 10).toString().replace(".", ",")}jt`;
  }
  return `${Math.round(amount / 1000)}rb`;
}

const isDate = (value: string | null): value is string =>
  value !== null && /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(utc(value));

function count(value: string | null, min: number, max: number, fallback: number): number {
  const parsed = Number(value);
  return value !== null && Number.isInteger(parsed) && parsed >= min && parsed <= max
    ? parsed
    : fallback;
}

export interface DeepLink extends Partial<Pick<StayQuery, "arrival" | "departure">> {
  adults: number;
  children: number;
  room: string | null;
}

/** Dates, guests and room from a shared link; anything malformed is ignored. */
export function parseDeepLink(params: URLSearchParams): DeepLink {
  const arrival = params.get("arrival");
  const departure = params.get("departure");
  const valid = isDate(arrival) && isDate(departure) && utc(departure) > utc(arrival);
  return {
    ...(valid ? { arrival, departure } : {}),
    adults: count(params.get("adults"), 1, 50, 2),
    children: count(params.get("children"), 0, 50, 0),
    room: params.get("room"),
  };
}

export function bookingPageUrl(
  origin: string,
  slug: string,
  stay?: { arrival?: string; departure?: string; room?: string },
): string {
  const query = new URLSearchParams();
  if (stay?.arrival) query.set("arrival", stay.arrival);
  if (stay?.departure) query.set("departure", stay.departure);
  if (stay?.room) query.set("room", stay.room);
  const suffix = query.toString();
  return `${origin.replace(/\/+$/, "")}/book/${slug}${suffix ? `?${suffix}` : ""}`;
}

export const isValidSlug = (slug: string) => SLUG.test(slug);

export function errorCode(cause: unknown): (typeof ERROR_CODES)[number] {
  if (cause instanceof ApiError) {
    const code = (cause.detail as { code?: string } | undefined)?.code ?? cause.message;
    if ((ERROR_CODES as readonly string[]).includes(code)) {
      return code as (typeof ERROR_CODES)[number];
    }
  }
  return "unknown";
}

/** The new total the server reported when the price changed during checkout. */
export function changedTotal(cause: unknown): string | null {
  if (!(cause instanceof ApiError)) return null;
  const total = (cause.detail as { total?: unknown } | undefined)?.total;
  return typeof total === "string" ? total : null;
}

/** The last arrival date that still falls inside the free-cancellation period. */
export function freeCancelUntil(arrival: string, freeDays: number | null): string | null {
  return freeDays === null ? null : addDays(arrival, -freeDays);
}

export function termsKey(option: Pick<RateOption, "non_refundable">): string {
  return option.non_refundable ? "book.terms.nonRefundable" : "book.terms.free";
}

/** A stable illustration choice for a room, so its picture does not change between visits. */
export function plateVariant(id: string, count: number, order: readonly string[] = []): number {
  const position = order.indexOf(id);
  if (position >= 0) return position % count;
  const sum = Array.from(id).reduce((total, char) => total + char.charCodeAt(0), 0);
  return sum % count;
}

export function hasFreeCancellation(
  options: readonly Pick<RateOption, "non_refundable" | "free_cancellation_days">[],
): boolean {
  return options.some(
    (option) => !option.non_refundable && option.free_cancellation_days !== null,
  );
}

export function whatsappUrl(phone: string | null): string | null {
  const digits = phone?.replace(/\D/g, "") ?? "";
  return digits ? `https://wa.me/${digits}` : null;
}

const BOOKING_PATH_KEY = "booking-path:";

/**
 * Remember the guest's private page for this tab only. The pay link may be shared with
 * someone paying on the guest's behalf, so the server never hands it out from there.
 */
export function rememberBookingPath(payUrl: string, bookingPath: string): void {
  try {
    const token = payUrl.split("/").pop() ?? "";
    window.sessionStorage.setItem(`${BOOKING_PATH_KEY}${token}`, bookingPath);
  } catch {
    // Not remembered: the guest still gets the link in the WhatsApp confirmation.
  }
}

export function recallBookingPath(payToken: string): string | null {
  try {
    const path = window.sessionStorage.getItem(`${BOOKING_PATH_KEY}${payToken}`);
    return path?.startsWith("/booking/") ? path : null;
  } catch {
    return null;
  }
}

export function newCheckoutKey(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}
