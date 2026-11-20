import { describe, expect, it } from "vitest";

import {
  changesFor,
  checkBooking,
  checkPayment,
  stayOf,
  type BookingForm,
  type PaymentForm,
} from "@/lib/booking-forms";
import { LOCALES, translate } from "@/lib/i18n";

const form = (overrides: Partial<BookingForm> = {}): BookingForm => ({
  arrival: "2026-11-21",
  departure: "2026-11-23",
  roomTypeId: "room",
  ratePlanId: "plan",
  units: "1",
  adults: "2",
  children: "",
  guestName: " Budi Santoso ",
  guestPhone: " 0812-3456-7890 ",
  source: "whatsapp",
  total: "",
  notes: "  ",
  ...overrides,
});
const problemOf = (checked: ReturnType<typeof checkBooking> | ReturnType<typeof checkPayment>) =>
  checked.ok ? null : checked.problem.key;

describe("stayOf", () => {
  it("gives the stay once it is complete", () => {
    expect(stayOf(form())).toEqual({
      arrival: "2026-11-21",
      departure: "2026-11-23",
      room_type_id: "room",
      rate_plan_id: "plan",
      units: 1,
      adults: 2,
      children: 0,
    });
  });

  it("is null while anything needed for a price is missing or wrong", () => {
    const incomplete: Partial<BookingForm>[] = [
      { arrival: "" },
      { departure: "2026-11-21" },
      { roomTypeId: "" },
      { ratePlanId: "" },
      { units: "0" },
      { adults: "" },
      { children: "x" },
    ];
    expect(incomplete.map((change) => stayOf(form(change)))).toEqual(Array(7).fill(null));
  });
});

describe("checkBooking", () => {
  it("returns the cleaned input, leaving out what was not given", () => {
    expect(checkBooking(form(), 2)).toEqual({
      ok: true,
      value: {
        arrival: "2026-11-21",
        departure: "2026-11-23",
        room_type_id: "room",
        rate_plan_id: "plan",
        units: 1,
        adults: 2,
        children: 0,
        guest_name: "Budi Santoso",
        guest_phone: "0812-3456-7890",
        source: "whatsapp",
      },
    });
  });

  it("includes a typed total and notes", () => {
    const checked = checkBooking(form({ total: "1.200.000", notes: "Kasur tambahan" }), null);

    expect(checked.ok && checked.value).toMatchObject({
      total_amount: 1200000,
      notes: "Kasur tambahan",
    });
  });

  it("names each problem", () => {
    const cases: [Partial<BookingForm>, string][] = [
      [{ arrival: "" }, "bookings.form.needDates"],
      [{ departure: "2026-11-21" }, "bookings.form.badDates"],
      [{ roomTypeId: "" }, "bookings.form.needRoom"],
      [{ ratePlanId: "" }, "bookings.form.needPlan"],
      [{ units: "0" }, "bookings.form.badUnits"],
      [{ adults: "0" }, "bookings.form.badAdults"],
      [{ children: "-1" }, "bookings.form.badChildren"],
      [{ adults: "3" }, "bookings.form.tooManyGuests"],
      [{ guestName: "  " }, "bookings.form.needGuest"],
      [{ total: "1.200.000,50" }, "bookings.form.badTotal"],
    ];
    for (const [change, key] of cases) {
      expect(problemOf(checkBooking(form(change), 2))).toBe(key);
      for (const locale of LOCALES) {
        expect(translate(locale, key, { max: 2 })).not.toBe(key);
      }
    }
  });

  it("does not count guests when the limit is not known yet", () => {
    expect(checkBooking(form({ adults: "9" }), null).ok).toBe(true);
  });
});

describe("checkPayment", () => {
  const TODAY = "2026-11-20";
  const payment = (overrides: Partial<PaymentForm> = {}): PaymentForm => ({
    amount: "500.000",
    method: "cash",
    receivedOn: TODAY,
    note: " DP ",
    ...overrides,
  });

  it("returns the cleaned input", () => {
    expect(checkPayment(payment(), TODAY)).toEqual({
      ok: true,
      value: { amount: 500000, method: "cash", received_on: TODAY, note: "DP" },
    });
  });

  it("names each problem", () => {
    const cases: [Partial<PaymentForm>, string][] = [
      [{ amount: "0" }, "bookings.pay.badAmount"],
      [{ amount: "lima ratus" }, "bookings.pay.badAmount"],
      [{ receivedOn: "" }, "bookings.pay.needDate"],
      [{ receivedOn: "2026-11-21" }, "bookings.pay.futureDate"],
    ];
    for (const [change, key] of cases) {
      expect(problemOf(checkPayment(payment(change), TODAY))).toBe(key);
      for (const locale of LOCALES) {
        expect(translate(locale, key)).not.toBe(key);
      }
    }
  });
});

describe("changesFor", () => {
  const input = (overrides: Partial<BookingForm> = {}) => {
    const checked = checkBooking(form(overrides), null);
    if (!checked.ok) throw new Error("the form should be valid");
    return checked.value;
  };

  it("sends emptied notes and number so the server clears them", () => {
    const changes = changesFor(input({ guestPhone: "", notes: "" }), false);

    expect(changes).toMatchObject({ guest_phone: null, notes: "" });
    expect("reset_price" in changes).toBe(false);
  });

  it("asks for the calendar price when a hand-set total was emptied", () => {
    expect(changesFor(input({ total: "" }), true)).toMatchObject({ reset_price: true });
  });

  it("keeps a typed total and never sends both instructions", () => {
    const changes = changesFor(input({ total: "900.000" }), true);

    expect(changes.total_amount).toBe(900000);
    expect("reset_price" in changes).toBe(false);
  });

  it("keeps what was typed", () => {
    expect(changesFor(input({ notes: "Kasur tambahan" }), false)).toMatchObject({
      guest_phone: "0812-3456-7890",
      notes: "Kasur tambahan",
    });
  });
});
