/**
 * Pure helpers for showing bookings: stay dates, labels and badge styles.
 * Dates are the property's local dates as "YYYY-MM-DD" strings.
 */

import type { Booking, PaymentState } from "@/lib/bookings-api";
import type { Locale } from "@/lib/i18n";

const LOCALE_TAGS: Record<Locale, string> = { id: "id-ID", en: "en-GB" };
const toUtc = (iso: string) => new Date(`${iso}T00:00:00Z`);

function part(iso: string, locale: Locale, options: Intl.DateTimeFormatOptions): string {
  return new Intl.DateTimeFormat(LOCALE_TAGS[locale], { ...options, timeZone: "UTC" }).format(
    toUtc(iso),
  );
}

/** "20 Nov 2026" */
export function shortDate(iso: string, locale: Locale): string {
  return part(iso, locale, { day: "numeric", month: "short", year: "numeric" });
}

/** "20–23 Nov 2026", "28 Nov – 2 Des 2026" or "30 Des 2026 – 2 Jan 2027". */
export function stayRange(arrival: string, departure: string, locale: Locale): string {
  const [fromYear, fromMonth] = arrival.split("-");
  const [toYear, toMonth] = departure.split("-");
  if (fromYear !== toYear) return `${shortDate(arrival, locale)} – ${shortDate(departure, locale)}`;
  if (fromMonth !== toMonth) {
    const from = part(arrival, locale, { day: "numeric", month: "short" });
    return `${from} – ${shortDate(departure, locale)}`;
  }
  const from = part(arrival, locale, { day: "numeric" });
  return `${from}–${shortDate(departure, locale)}`;
}

/** i18n key of a payment state label. */
export function paymentStateKey(state: PaymentState): string {
  return `bookings.payment.${state}`;
}

/** A cancelled booking is partly paid but owes nothing, so it shows no balance. */
export function hasBalanceToShow(state: PaymentState, balance: string): boolean {
  return state === "partly_paid" && Number(balance) > 0;
}

/** Tailwind classes for a payment state badge (semantic theme colours only). */
export function paymentBadgeClass(state: PaymentState): string {
  if (state === "paid") return "bg-primary text-primary-foreground";
  if (state === "partly_paid") return "bg-accent text-accent-foreground";
  if (state === "overpaid") return "bg-destructive/15 text-destructive";
  return "bg-muted text-muted-foreground ring-1 ring-border";
}

/** i18n key of a source name; unknown codes (channels, later) fall back to the stored name. */
export function sourceLabelKey(code: string): string {
  return `bookings.source.${code}`;
}

/** What is special about the stay today: arriving, leaving, or nothing. */
export function todayNote(
  booking: Pick<Booking, "arrival" | "departure" | "status">,
  today: string,
): "arriving" | "leaving" | null {
  if (booking.status !== "confirmed") return null;
  if (booking.arrival === today) return "arriving";
  return booking.departure === today ? "leaving" : null;
}

/** True when the booking can still be changed or cancelled. */
export function isOpen(booking: Pick<Booking, "status">): boolean {
  return booking.status === "confirmed";
}

/** i18n key of a channel attention reason. */
export function channelAttentionKey(reason: string): string {
  return `bookings.channel.attention.${reason}`;
}

/** i18n key of a channel event kind. */
export function channelKindKey(kind: string): string {
  return `bookings.channel.kind.${kind}`;
}
