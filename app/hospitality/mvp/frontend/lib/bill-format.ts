/** Pure helpers for the guest bill. */

import { ApiError } from "@/lib/api-client";
import type { ChargeCategory, ChargeInput, LineCategory } from "@/lib/bills-api";
import { deskErrorKey } from "@/lib/front-desk-format";
import { parseRupiah } from "@/lib/money";

export const BILL_ERROR_CODES = [
  "bill_closed",
  "discount_too_large",
  "already_voided",
  "void_too_late",
  "not_voidable",
  "zero_correction",
  "too_many_lines",
  "balance_owed",
  "unpaid_permission",
  "category_off",
  "price_permission",
] as const;
export const MAX_QUANTITY = 999;
export const REASON_MIN = 3;
export const TEXT_MAX = 200;

type Checked<T> = { ok: true; value: T } | { ok: false; key: string };
const fail = (key: string): { ok: false; key: string } => ({ ok: false, key });

export interface ChargeForm {
  category: ChargeCategory;
  description: string;
  quantity: string;
  unitPrice: string;
}

export function checkCharge(form: ChargeForm): Checked<ChargeInput> {
  const description = form.description.trim();
  if (!description) return fail("bills.charge.needDescription");
  const quantity = Number(form.quantity);
  if (!Number.isInteger(quantity) || quantity < 1 || quantity > MAX_QUANTITY) {
    return fail("bills.charge.badQuantity");
  }
  const price = parseRupiah(form.unitPrice);
  if (price === null) return fail("bookings.pay.badAmount");
  return { ok: true, value: { category: form.category, description, quantity, unit_price: price } };
}

/** A whole-rupiah amount that may start with a minus sign. */
export function checkCorrection(text: string): Checked<number> {
  const trimmed = text.trim();
  const negative = trimmed.startsWith("-");
  const amount = parseRupiah(negative ? trimmed.slice(1) : trimmed);
  if (amount === null || amount === 0) return fail("bills.correction.badAmount");
  return { ok: true, value: negative ? -amount : amount };
}

export function checkReason(text: string): Checked<string> {
  const reason = text.trim();
  return reason.length >= REASON_MIN ? { ok: true, value: reason } : fail("bills.needReason");
}

export const lineLabelKey = (category: LineCategory | string) => `bills.category.${category}`;

export function balanceState(balance: string): "owes" | "settled" | "refund" {
  const value = Number(balance);
  if (value > 0) return "owes";
  return value < 0 ? "refund" : "settled";
}

/** i18n key of a bill or front desk refusal; null for anything else. */
export function billErrorKey(cause: unknown): string | null {
  const desk = deskErrorKey(cause);
  if (desk) return desk;
  if (!(cause instanceof ApiError) || typeof cause.detail !== "object" || !cause.detail) {
    return null;
  }
  const code = (cause.detail as { code?: string }).code;
  if (code && (BILL_ERROR_CODES as readonly string[]).includes(code)) return `frontdesk.error.${code}`;
  return code === "day_closed" || code === "drawer_closed" || code === "stale_drawer"
    ? `endofday.error.${code}`
    : null;
}
