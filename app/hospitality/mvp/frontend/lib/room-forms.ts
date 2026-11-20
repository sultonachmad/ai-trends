/**
 * Pure checks for the room type and rate plan forms. Each returns an i18n key (with
 * values) describing the first problem, or the cleaned input when everything is fine.
 */

import { parseRupiah } from "@/lib/money";
import type { MealPlan, RatePlanInput } from "@/lib/rate-plans-api";
import type { RoomKind, RoomTypeInput } from "@/lib/rooms-api";

export const MAX_GUESTS = 50;
export const MAX_FREE_DAYS = 365;

export interface FormProblem {
  key: string;
  vars?: Record<string, string | number>;
}

export type Checked<T> = { ok: true; value: T } | { ok: false; problem: FormProblem };

const fail = (key: string, vars?: FormProblem["vars"]): Checked<never> => ({
  ok: false,
  problem: { key, vars },
});

/** A whole number within [min, max] from what a person typed, or null. */
export function parseWhole(input: string, min: number, max: number): number | null {
  if (!/^\d{1,6}$/.test(input.trim())) return null;
  const value = Number(input.trim());
  return value >= min && value <= max ? value : null;
}

export interface RoomTypeForm {
  name: string;
  kind: RoomKind;
  units: string;
  maxGuests: string;
}

export function checkRoomType(form: RoomTypeForm, maxUnits: number): Checked<RoomTypeInput> {
  const name = form.name.trim();
  if (name === "") return fail("rooms.form.needName");
  const units = parseWhole(form.units, 1, maxUnits);
  if (units === null) return fail("rooms.form.badUnits", { max: maxUnits });
  const maxGuests = parseWhole(form.maxGuests, 1, MAX_GUESTS);
  if (maxGuests === null) return fail("rooms.form.badGuests");
  return { ok: true, value: { name, kind: form.kind, units, max_guests: maxGuests } };
}

export interface RatePlanForm {
  name: string;
  mealPlan: MealPlan;
  nonRefundable: boolean;
  freeDays: string;
  /** Typed price per room type id; empty = not sold on this plan. */
  prices: Record<string, string>;
}

export interface PriceBounds {
  min: number;
  max: number;
}

export function checkRatePlan(
  form: RatePlanForm,
  rooms: { id: string; name: string }[],
  bounds: PriceBounds,
  formatAmount: (amount: number) => string,
): Checked<RatePlanInput> {
  const name = form.name.trim();
  if (name === "") return fail("rates.form.needName");
  const freeDays = form.nonRefundable ? null : parseWhole(form.freeDays, 0, MAX_FREE_DAYS);
  if (!form.nonRefundable && freeDays === null) return fail("rates.form.badDays");
  const prices: RatePlanInput["prices"] = [];
  for (const room of rooms) {
    const typed = (form.prices[room.id] ?? "").trim();
    if (typed === "") continue;
    const amount = parseRupiah(typed);
    if (amount === null || amount < bounds.min || amount > bounds.max) {
      return fail("rates.form.badPrice", {
        room: room.name,
        min: formatAmount(bounds.min),
        max: formatAmount(bounds.max),
      });
    }
    prices.push({ room_type_id: room.id, amount });
  }
  if (prices.length === 0) return fail("rates.form.needPrice");
  return {
    ok: true,
    value: {
      name,
      meal_plan: form.mealPlan,
      non_refundable: form.nonRefundable,
      ...(freeDays !== null ? { free_cancellation_days: freeDays } : {}),
      prices,
    },
  };
}

/** A numeric workspace setting, or the fallback when it is missing. */
export function numberSetting(settings: Record<string, unknown>, key: string, fallback: number): number {
  const value = settings[key];
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}
