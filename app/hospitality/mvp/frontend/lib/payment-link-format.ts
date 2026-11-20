/**
 * Pure helpers for payment links: state labels and "time left" text.
 */

export type LinkState = "pending" | "paid" | "expired" | "cancelled";

export const LINK_STATES: readonly LinkState[] = ["pending", "paid", "expired", "cancelled"];

/** i18n key for a state name. */
export function stateLabelKey(state: string): string {
  return `links.state.${state}`;
}

/** Tailwind classes for a state badge (semantic theme colours only). */
export function stateBadgeClass(state: string): string {
  if (state === "paid") return "bg-primary text-primary-foreground";
  if (state === "pending") return "bg-accent text-accent-foreground";
  return "bg-muted text-muted-foreground";
}

export interface TimeLeft {
  unit: "minutes" | "hours" | "days";
  value: number;
}

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** How long until `expiresIso`, rounded down to a readable unit; null once passed. */
export function timeLeft(expiresIso: string, now: Date = new Date()): TimeLeft | null {
  const remaining = new Date(expiresIso).getTime() - now.getTime();
  if (!(remaining > 0)) return null;
  if (remaining >= 2 * DAY) return { unit: "days", value: Math.floor(remaining / DAY) };
  if (remaining >= 2 * HOUR) return { unit: "hours", value: Math.floor(remaining / HOUR) };
  return { unit: "minutes", value: Math.max(1, Math.floor(remaining / MINUTE)) };
}

/** i18n key + value for the "expires in …" text. */
export function timeLeftKey(left: TimeLeft): string {
  return `links.left.${left.unit}`;
}
