/** Pure helpers for calendar links. */

import type { CalendarLink } from "@/lib/calendar-links-api";

export const IMPORT_ERROR_CODES = [
  "invalid_url",
  "unsafe_address",
  "unreachable",
  "timeout",
  "too_large",
  "bad_status",
  "too_many_redirects",
  "unreadable",
] as const;

/** i18n key of a stored import error; an unknown code reads as "could not be read". */
export function importErrorKey(code: string): string {
  const known = (IMPORT_ERROR_CODES as readonly string[]).includes(code);
  return `calendarLinks.error.${known ? code : "unreadable"}`;
}

export type CalendarLinkState = "export_only" | "waiting" | "ok" | "failing" | "at_risk";

export function linkState(link: CalendarLink): CalendarLinkState {
  const imported = link.imports;
  if (!imported) return "export_only";
  if (imported.at_risk) return "at_risk";
  if (imported.last_error) return "failing";
  return imported.last_synced_at ? "ok" : "waiting";
}

export function linkBadgeClass(state: CalendarLinkState): string {
  if (state === "ok") return "bg-primary text-primary-foreground";
  if (state === "failing" || state === "at_risk") return "bg-destructive/15 text-destructive";
  return "bg-muted text-muted-foreground ring-1 ring-border";
}

/** The full address to paste into the other site. */
export function exportUrl(apiBase: string, path: string): string {
  return `${apiBase.replace(/\/+$/, "")}${path}`;
}

/** Links with dates busy on the site that we have also sold. */
export function linksInConflict(links: CalendarLink[]): CalendarLink[] {
  return links.filter((link) => link.conflict_dates.length > 0);
}
