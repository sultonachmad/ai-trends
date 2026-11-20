/**
 * Pure checks for the booking and payment forms. Each returns an i18n key (with values)
 * for the first problem, or the cleaned input when everything is fine.
 */

import type {
  BookingChanges,
  BookingInput,
  BookingSourceCode,
  PaymentInput,
  PaymentMethod,
  StayInput,
} from "@/lib/bookings-api";
import { daysBetween } from "@/lib/calendar-grid";
import { parseRupiah } from "@/lib/money";
import { parseWhole, type Checked } from "@/lib/room-forms";

export const MAX_UNITS = 100;
export const MAX_GUESTS = 500;
export const NAME_MAX = 120;
export const NOTES_MAX = 1000;
export const NOTE_MAX = 200;

const fail = (key: string, vars?: Record<string, string | number>): Checked<never> => ({
  ok: false,
  problem: { key, vars },
});

export interface BookingForm {
  arrival: string;
  departure: string;
  roomTypeId: string;
  ratePlanId: string;
  units: string;
  adults: string;
  children: string;
  guestName: string;
  guestPhone: string;
  source: BookingSourceCode;
  /** Typed total; empty = the calendar price. */
  total: string;
  notes: string;
}

/** The stay part of the form, when it is complete enough to ask for a price. */
export function stayOf(form: BookingForm): StayInput | null {
  const units = parseWhole(form.units, 1, MAX_UNITS);
  const adults = parseWhole(form.adults, 1, MAX_GUESTS);
  const children = parseWhole(form.children || "0", 0, MAX_GUESTS);
  if (!form.arrival || !form.departure || form.departure <= form.arrival) return null;
  if (!form.roomTypeId || !form.ratePlanId) return null;
  if (units === null || adults === null || children === null) return null;
  return {
    arrival: form.arrival,
    departure: form.departure,
    room_type_id: form.roomTypeId,
    rate_plan_id: form.ratePlanId,
    units,
    adults,
    children,
  };
}

function stayProblem(form: BookingForm): string | null {
  if (!form.arrival || !form.departure) return "bookings.form.needDates";
  if (daysBetween(form.arrival, form.departure) < 1) return "bookings.form.badDates";
  if (!form.roomTypeId) return "bookings.form.needRoom";
  if (!form.ratePlanId) return "bookings.form.needPlan";
  if (parseWhole(form.units, 1, MAX_UNITS) === null) return "bookings.form.badUnits";
  if (parseWhole(form.adults, 1, MAX_GUESTS) === null) return "bookings.form.badAdults";
  if (parseWhole(form.children || "0", 0, MAX_GUESTS) === null) return "bookings.form.badChildren";
  return null;
}

export function checkBooking(form: BookingForm, maxGuests: number | null): Checked<BookingInput> {
  const problem = stayProblem(form);
  if (problem) return fail(problem);
  const stay = stayOf(form) as StayInput;
  if (maxGuests !== null && stay.adults + stay.children > maxGuests) {
    return fail("bookings.form.tooManyGuests", { max: maxGuests });
  }
  const guestName = form.guestName.trim();
  if (guestName === "") return fail("bookings.form.needGuest");
  const total = form.total.trim() === "" ? null : parseRupiah(form.total);
  if (form.total.trim() !== "" && total === null) return fail("bookings.form.badTotal");
  const phone = form.guestPhone.trim();
  const notes = form.notes.trim();
  return {
    ok: true,
    value: {
      ...stay,
      guest_name: guestName,
      ...(phone ? { guest_phone: phone } : {}),
      source: form.source,
      ...(total !== null ? { total_amount: total } : {}),
      ...(notes ? { notes } : {}),
    },
  };
}

export interface PaymentForm {
  amount: string;
  method: PaymentMethod;
  receivedOn: string;
  note: string;
}

export function checkPayment(form: PaymentForm, today: string): Checked<PaymentInput> {
  const amount = parseRupiah(form.amount);
  if (amount === null) return fail("bookings.pay.badAmount");
  if (!form.receivedOn) return fail("bookings.pay.needDate");
  if (form.receivedOn > today) return fail("bookings.pay.futureDate");
  const note = form.note.trim();
  return {
    ok: true,
    value: {
      amount,
      method: form.method,
      received_on: form.receivedOn,
      ...(note ? { note } : {}),
    },
  };
}

/**
 * What to send when changing a booking: unlike a new booking, an emptied field must be
 * sent so the server clears it (notes, number) or goes back to the calendar price.
 */
export function changesFor(input: BookingInput, hadHandSetTotal: boolean): BookingChanges {
  return {
    ...input,
    guest_phone: input.guest_phone ?? null,
    notes: input.notes ?? "",
    ...(input.total_amount === undefined && hadHandSetTotal ? { reset_price: true } : {}),
  };
}
