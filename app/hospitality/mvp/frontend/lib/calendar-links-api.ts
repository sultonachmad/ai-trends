/**
 * Calendar link calls (backend: app/routers/calendar_links.py).
 */

import { request } from "@/lib/api-client";

export interface CalendarImportStatus {
  /** The site's host only: the full link is a secret. */
  url_hint: string;
  last_synced_at: string | null;
  /** A short code, see `importErrorKey`. */
  last_error: string | null;
  failing_since: string | null;
  at_risk: boolean;
  busy_dates: number;
}

export interface CalendarLink {
  id: string;
  label: string;
  room_type_id: string;
  room_type_name: string;
  imports: CalendarImportStatus | null;
  /** Busy on the site on a date we have nothing left for. */
  conflict_dates: string[];
}

/** Only these answers carry the private link; it cannot be shown again. */
export interface CalendarLinkCreated extends CalendarLink {
  export_path: string;
}

const base = "/api/calendar-links";
const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const fetchCalendarLinks = () => request<CalendarLink[]>(base);
export const createCalendarLink = (body: {
  room_type_id: string;
  label: string;
  import_url?: string;
}) => request<CalendarLinkCreated>(base, json("POST", body));
export const updateCalendarLink = (
  id: string,
  body: { label?: string; import_url?: string | null },
) => request<CalendarLink>(`${base}/${id}`, json("PATCH", body));
export const replaceCalendarToken = (id: string) =>
  request<CalendarLinkCreated>(`${base}/${id}/token`, { method: "POST" });
export const syncCalendarLink = (id: string) =>
  request<CalendarLink>(`${base}/${id}/sync`, { method: "POST" });
export const removeCalendarLink = (id: string) =>
  request<void>(`${base}/${id}`, { method: "DELETE" });
