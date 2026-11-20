/**
 * Pure helpers for the plan's monthly payment-link limit: which state to show and
 * how to word it. The server decides the numbers and enforces the limit.
 */

import type { Locale } from "@/lib/i18n";
import type { Workspace } from "@/lib/workspace-api";

export type LinkUsage = Workspace["usage"];
export type QuotaState = "unlimited" | "ok" | "warning" | "reached" | "notInPlan";

const LOCALE_TAGS: Record<Locale, string> = { id: "id-ID", en: "en-GB" };
const FULL = 100;

export function quotaState(usage: LinkUsage): QuotaState {
  if (usage.payment_links_limit === null) return "unlimited";
  if (usage.payment_links_limit === 0) return "notInPlan";
  if (usage.payment_links_limit_reached) return "reached";
  return usage.payment_links_warning ? "warning" : "ok";
}

/** Share of the limit used, 0–100; null when there is no limit to measure against. */
export function quotaPercent(usage: LinkUsage): number | null {
  const limit = usage.payment_links_limit;
  if (limit === null || limit <= 0) return null;
  return Math.min(FULL, Math.round((usage.payment_links_used / limit) * FULL));
}

/** The day links can be created again ("1 Desember"), from the property's local date. */
export function resetDateLabel(resetsOn: string, locale: Locale): string {
  // The server already worked out the local calendar date; format it without shifting it.
  return new Intl.DateTimeFormat(LOCALE_TAGS[locale], {
    day: "numeric",
    month: "long",
    timeZone: "UTC",
  }).format(new Date(`${resetsOn}T00:00:00Z`));
}

/** i18n key for the one-line usage text. */
export function quotaTextKey(state: QuotaState): string {
  return `quota.${state}`;
}

/** True when a new link cannot be created now. */
export function isBlocked(state: QuotaState): boolean {
  return state === "reached" || state === "notInPlan";
}
