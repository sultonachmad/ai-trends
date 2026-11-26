/** Cash drawers and closing a day (backend: app/routers/cash_drawers.py, end_of_day.py). */

import { request } from "@/lib/api-client";

export interface MethodTotal {
  method: string;
  received: string;
  paid_out: string;
}

export interface Drawer {
  id: string;
  staff_name: string;
  business_date: string;
  opened_at: string;
  closed_at: string | null;
  status: "open" | "closed" | "reconciled";
  opening_float: string;
  cash_in: string;
  cash_out: string;
  paid_outs: string;
  expected_cash: string;
  counted_cash: string | null;
  variance: string | null;
  notes: string | null;
  by_method: MethodTotal[];
}

export interface CheckItem {
  booking_id: string | null;
  label: string;
}

export interface DayCheck {
  code: string;
  level: "blocking" | "warning";
  count: number;
  items: CheckItem[];
}

export interface DaySummary {
  rooms: {
    available: number;
    sold: number;
    occupancy_pct: string;
    revenue: string;
    adr: string;
    revpar: string;
  };
  movements: { arrivals: number; departures: number; no_shows: number; cancellations: number };
  extras: { category: string; amount: string }[];
  money: {
    received: { method: string; amount: string }[];
    received_total: string;
    online: string;
    deposits: string;
    paid_out: { kind: string; method: string; amount: string }[];
  };
  left_unpaid: { count: number; amount: string };
}

export interface DayRead {
  date: string;
  /** The property's date now. */
  today: string;
  status: "open" | "closed";
  closed_at: string | null;
  closed_by: string | null;
  can_close: boolean;
  checks: DayCheck[];
  summary: DaySummary;
  drawers: Drawer[];
}

const json = (method: string, body: unknown) => ({ method, body: JSON.stringify(body) });
const drawers = "/api/cash-drawers/mine";
const days = "/api/end-of-day/days";

export const fetchMyDrawer = () => request<{ drawer: Drawer | null }>(drawers);
export const openDrawer = (openingFloat: number) =>
  request<Drawer>(`${drawers}/open`, json("POST", { opening_float: openingFloat }));
export const recordPaidOut = (amount: number, reason: string) =>
  request<Drawer>(`${drawers}/paid-outs`, json("POST", { amount, reason }));
export const closeDrawer = (countedCash: number, note: string | null) =>
  request<Drawer>(`${drawers}/close`, json("POST", { counted_cash: countedCash, note }));

export const fetchDay = (date: string) => request<DayRead>(`${days}/${date}`);
export const closeDay = (date: string, overrideReason: string | null) =>
  request<DayRead>(
    `${days}/${date}/close`,
    json("POST", overrideReason ? { override_reason: overrideReason } : {}),
  );
export const reopenDay = (date: string, reason: string) =>
  request<DayRead>(`${days}/${date}/reopen`, json("POST", { reason }));
