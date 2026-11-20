/**
 * Calendar calls (backend: app/routers/calendar.py).
 */

import { request } from "@/lib/api-client";

export interface DayPrice {
  rate_plan_id: string;
  amount: string;
  /** False = the rate plan's base price. */
  is_override: boolean;
}

export interface CalendarDay {
  date: string;
  available: number;
  closed: boolean;
  /** Minimum nights for guests arriving this date. */
  min_stay: number | null;
  prices: DayPrice[];
}

export interface CalendarRoomType {
  id: string;
  name: string;
  units: number;
  rate_plans: { id: string; name: string }[];
  days: CalendarDay[];
}

export interface Calendar {
  start: string;
  end: string;
  /** Today at the property (YYYY-MM-DD). */
  today: string;
  last_editable_date: string;
  room_types: CalendarRoomType[];
}

export type CalendarChange =
  | { kind: "set_price"; rate_plan_id: string; amount: number }
  | { kind: "clear_price"; rate_plan_id: string }
  | { kind: "close" }
  | { kind: "open" }
  | { kind: "set_min_stay"; nights: number }
  | { kind: "clear_min_stay" };

export interface CalendarChangeInput {
  start: string;
  end: string;
  /** 0 = Monday … 6 = Sunday; omitted = every day. */
  weekdays?: number[];
  room_type_ids: string[];
  change: CalendarChange;
}

const base = "/api/calendar";

export function fetchCalendar(from: string, to: string): Promise<Calendar> {
  return request(`${base}?${new URLSearchParams({ from, to }).toString()}`);
}

export const changeCalendar = (input: CalendarChangeInput) =>
  request<{ dates: number; room_types: number }>(`${base}/changes`, {
    method: "POST",
    body: JSON.stringify(input),
  });
