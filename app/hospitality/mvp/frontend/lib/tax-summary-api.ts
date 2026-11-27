/** The monthly tax summary (backend: app/routers/tax_summary.py). */

import { request, requestBlob } from "@/lib/api-client";

export interface TaxAmounts {
  room_nights: number;
  room_base: string;
  extras_base: string;
  service: string;
  pbjt: string;
  untaxed: string;
  channel_nights: number;
  channel_base: string;
  channel_service: string;
  channel_pbjt: string;
}

export interface TaxDay extends TaxAmounts {
  date: string;
}

export interface TaxBooking extends TaxAmounts {
  booking_id: string;
  number: string;
  arrival: string;
  departure: string;
  source: string;
  price_mode: string;
}

export interface TaxMonth {
  month: string;
  first_day: string;
  last_day: string;
  is_set: boolean;
  draft: boolean;
  closed_days: number;
  days_in_month: number;
  days: TaxDay[];
  bookings: TaxBooking[];
  totals: TaxAmounts;
}

export const fetchTaxMonth = (month: string) => request<TaxMonth>(`/api/tax-summary/${month}`);
export const downloadTaxFile = (month: string, kind: "days" | "bookings") =>
  requestBlob(`/api/tax-summary/${month}/${kind}.csv`);
