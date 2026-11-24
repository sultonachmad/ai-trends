/** Guest bill calls (backend: app/routers/bills.py). */

import { request } from "@/lib/api-client";
import type { PaymentInput } from "@/lib/bookings-api";

export const CHARGE_CATEGORIES = [
  "food_drinks",
  "laundry",
  "minibar",
  "transport",
  "extra_bed",
  "late_checkout",
  "other",
] as const;
export type ChargeCategory = (typeof CHARGE_CATEGORIES)[number];
export type LineCategory = ChargeCategory | "discount" | "correction";

export interface BillLine {
  id: string;
  category: LineCategory;
  description: string;
  quantity: string;
  unit_price: string | null;
  amount: string;
  business_date: string;
  posted_at: string;
  voided: boolean;
  void_reason: string | null;
  can_void: boolean;
}

export interface BillPayment {
  id: string;
  amount: string;
  method: string;
  received_on: string;
  note: string | null;
}

export interface ReceiptSummary {
  id: string;
  number: string;
  issued_at: string;
  total: string;
  /** A later check-out issued a newer receipt. */
  replaced: boolean;
}

export interface Bill {
  booking_id: string;
  number: string;
  status: string;
  guest_name: string;
  arrival: string;
  departure: string;
  closed: boolean;
  paid_to_channel: boolean;
  left_unpaid: boolean;
  room_type: string;
  room_nights: { date: string; amount: string }[];
  room_total: string;
  lines: BillLine[];
  extras_total: string;
  payments: BillPayment[];
  paid: string;
  balance: string;
  receipts: ReceiptSummary[];
}

export interface Receipt {
  id: string;
  number: string;
  issued_at: string;
  business_date: string | null;
  issuer_name: string;
  issuer_tax_id: string | null;
  property_name: string;
  booking_number: string;
  guest_name: string;
  arrival: string;
  departure: string;
  paid_to_channel: boolean;
  lines: { description: string; quantity: string; unit_price: string; amount: string; is_room: boolean }[];
  total: string;
  paid: string;
  balance: string;
}

export interface ChargeInput {
  category: ChargeCategory;
  description: string;
  quantity: number;
  unit_price: number;
}

const base = "/api/bills";
const json = (method: string, body: unknown) => ({ method, body: JSON.stringify(body) });

export const fetchBill = (bookingId: string) => request<Bill>(`${base}/${bookingId}`);
export const fetchReceipt = (receiptId: string) => request<Receipt>(`${base}/receipts/${receiptId}`);
export const postCharge = (bookingId: string, input: ChargeInput) =>
  request<Bill>(`${base}/${bookingId}/charges`, json("POST", input));
export const giveDiscount = (bookingId: string, amount: number, reason: string) =>
  request<Bill>(`${base}/${bookingId}/discounts`, json("POST", { amount, reason }));
export const postCorrection = (bookingId: string, amount: number, reason: string) =>
  request<Bill>(`${base}/${bookingId}/corrections`, json("POST", { amount, reason }));
export const voidLine = (bookingId: string, lineId: string, reason: string) =>
  request<Bill>(`${base}/${bookingId}/lines/${lineId}/void`, json("POST", { reason }));
export const payBill = (bookingId: string, input: PaymentInput) =>
  request<Bill>(`${base}/${bookingId}/payments`, json("POST", input));
