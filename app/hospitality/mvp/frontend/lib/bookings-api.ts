/**
 * Booking calls, staff side (backend: app/routers/bookings.py).
 */

import { request } from "@/lib/api-client";

export type BookingTab = "upcoming" | "staying" | "past" | "cancelled";
export type BookingSourceCode = "whatsapp" | "walk_in" | "phone" | "instagram" | "other";
export const STAFF_SOURCES: readonly BookingSourceCode[] = [
  "whatsapp",
  "walk_in",
  "phone",
  "instagram",
  "other",
];
export type PaymentState = "unpaid" | "partly_paid" | "paid" | "overpaid";
export type PaymentMethod = "cash" | "bank_transfer" | "card" | "qris" | "other";
export const PAYMENT_METHODS: readonly PaymentMethod[] = [
  "cash",
  "bank_transfer",
  "card",
  "qris",
  "other",
];

export interface Booking {
  id: string;
  number: string;
  status: "confirmed" | "cancelled" | "tentative" | "in_house" | "checked_out" | "no_show";
  arrival: string;
  departure: string;
  nights: number;
  room_type: { id: string; name: string };
  rate_plan: { id: string; name: string };
  units: number;
  /** Names of the rooms given to this booking so far. */
  assigned_rooms: string[];
  adults: number;
  children: number;
  guest: { id: string | null; name: string; phone: string | null };
  source: { code: string; name: string; is_direct: boolean };
  total_amount: string;
  paid_amount: string;
  balance_due: string;
  payment_state: PaymentState;
  /** Staff set the total by hand. */
  price_edited: boolean;
  /** A night of this stay has more sold than there are units. */
  overbooking_risk: boolean;
  /** Why this channel booking needs a person (overbooking_risk / unmapped_product / price_mismatch). */
  channel_attention: string | null;
  /** The channel's own booking id. */
  channel_reference: string | null;
  /** Held for an online payment until then. */
  hold_expires_at: string | null;
  /** The guest is owed money; staff refund outside the product. */
  refund_due: boolean;
  /** WhatsApp confirmation of a direct booking. */
  confirmation_status: "pending" | "sending" | "sent" | "failed" | null;
  notes: string | null;
  cancel_note: string | null;
  cancelled_at: string | null;
  created_at: string;
}

export interface BookingDetail extends Booking {
  /** The refund staff recorded as sent. */
  refund_done?: { amount: string; refunded_on: string; note: string | null } | null;
  nightly: { date: string; amount: string }[];
  payments: {
    id: string;
    amount: string;
    method: string;
    received_on: string;
    note: string | null;
    recorded_at: string;
    /** False for online payments, which staff cannot take back here. */
    removable: boolean;
  }[];
  terms: { non_refundable: boolean; free_cancellation_days: number | null } | null;
}

export interface BookingPage {
  items: Booking[];
  next_cursor: string | null;
}

export interface StayInput {
  arrival: string;
  departure: string;
  room_type_id: string;
  rate_plan_id: string;
  units: number;
  adults: number;
  children: number;
}

export interface BookingInput extends StayInput {
  guest_name: string;
  guest_phone?: string;
  source: BookingSourceCode;
  total_amount?: number;
  notes?: string;
  allow_overbooking?: boolean;
  conversation_id?: string;
}

export interface BookingQuote {
  nights: { date: string; amount: string; available: number; closed: boolean }[];
  total_amount: string;
  /** Nights without enough units for this booking. */
  short_dates: string[];
  closed_dates: string[];
  /** The arrival date's minimum stay, when this stay is shorter than it. */
  min_stay: number | null;
  max_guests: number;
}

/** The nights a refusal named as full, when the error is "not enough units". */
export function shortDatesOf(detail: unknown): string[] | null {
  const dates = (detail as { short_dates?: unknown } | undefined)?.short_dates;
  return Array.isArray(dates) && dates.every((date) => typeof date === "string") ? dates : null;
}

export interface PaymentInput {
  amount: number;
  method: PaymentMethod;
  received_on: string;
  note?: string;
}

const base = "/api/bookings";
const json = (method: string, body: unknown) => ({ method, body: JSON.stringify(body) });

export function fetchBookings(
  tab: BookingTab,
  query?: string,
  cursor?: string | null,
): Promise<BookingPage> {
  const params = new URLSearchParams({ tab });
  if (query) params.set("q", query);
  if (cursor) params.set("cursor", cursor);
  return request(`${base}?${params.toString()}`);
}

export const fetchBooking = (id: string) => request<BookingDetail>(`${base}/${id}`);
export const quoteBooking = (stay: StayInput, excludeBookingId?: string) =>
  request<BookingQuote>(
    `${base}/quote`,
    json("POST", { ...stay, ...(excludeBookingId ? { exclude_booking_id: excludeBookingId } : {}) }),
  );
export const createBooking = (input: BookingInput) =>
  request<BookingDetail>(base, json("POST", input));
/** A change may also clear the number (`null`) or go back to the calendar price. */
export type BookingChanges = Partial<Omit<BookingInput, "guest_phone">> & {
  guest_phone?: string | null;
  reset_price?: boolean;
};

export const updateBooking = (id: string, changes: BookingChanges) =>
  request<BookingDetail>(`${base}/${id}`, json("PATCH", changes));
export const cancelBooking = (id: string, reason?: string) =>
  request<BookingDetail>(`${base}/${id}/cancel`, json("POST", reason ? { reason } : {}));
export const recordPayment = (id: string, input: PaymentInput) =>
  request<BookingDetail>(`${base}/${id}/payments`, json("POST", input));
export const markRefundDone = (
  id: string,
  input: { amount: number | string; refunded_on: string; note?: string },
) => request<BookingDetail>(`${base}/${id}/refund-done`, json("POST", input));
export const removePayment = (id: string, paymentId: string) =>
  request<BookingDetail>(`${base}/${id}/payments/${paymentId}`, { method: "DELETE" });

export interface ChannelAttentionEntry {
  id: string;
  external_booking_id: string;
  version: number;
  kind: "new" | "modify" | "cancel";
  reason: string | null;
  reservation_id: string | null;
  connection_id: string;
  received_at: string;
}

export const fetchChannelAttention = () =>
  request<ChannelAttentionEntry[]>("/api/bookings/channel-attention");
