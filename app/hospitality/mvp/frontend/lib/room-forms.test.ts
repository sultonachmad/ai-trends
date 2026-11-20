import { describe, expect, it } from "vitest";

import { LOCALES, translate } from "@/lib/i18n";
import { formatRupiah } from "@/lib/money";
import {
  checkRatePlan,
  checkRoomType,
  numberSetting,
  parseWhole,
  type RatePlanForm,
  type RoomTypeForm,
} from "@/lib/room-forms";

const problemOf = (checked: ReturnType<typeof checkRoomType> | ReturnType<typeof checkRatePlan>) =>
  checked.ok ? null : checked.problem.key;

describe("parseWhole", () => {
  it("reads whole numbers inside the range", () => {
    expect(parseWhole(" 3 ", 1, 10)).toBe(3);
    expect(parseWhole("0", 0, 365)).toBe(0);
  });

  it("refuses anything else", () => {
    expect(["0", "11", "2.5", "-1", "tiga", ""].map((v) => parseWhole(v, 1, 10))).toEqual(
      Array(6).fill(null),
    );
  });
});

describe("checkRoomType", () => {
  const form = (overrides: Partial<RoomTypeForm> = {}): RoomTypeForm => ({
    name: " Deluxe ",
    kind: "villa",
    units: "3",
    maxGuests: "4",
    ...overrides,
  });

  it("returns the cleaned input", () => {
    expect(checkRoomType(form(), 100)).toEqual({
      ok: true,
      value: { name: "Deluxe", kind: "villa", units: 3, max_guests: 4 },
    });
  });

  it("names each problem", () => {
    expect(problemOf(checkRoomType(form({ name: "  " }), 100))).toBe("rooms.form.needName");
    expect(problemOf(checkRoomType(form({ units: "0" }), 100))).toBe("rooms.form.badUnits");
    expect(problemOf(checkRoomType(form({ units: "101" }), 100))).toBe("rooms.form.badUnits");
    expect(problemOf(checkRoomType(form({ maxGuests: "51" }), 100))).toBe("rooms.form.badGuests");
  });
});

describe("checkRatePlan", () => {
  const rooms = [
    { id: "a", name: "Deluxe" },
    { id: "b", name: "Suite" },
  ];
  const bounds = { min: 10000, max: 500000000 };
  const form = (overrides: Partial<RatePlanForm> = {}): RatePlanForm => ({
    name: "Harga Normal",
    mealPlan: "breakfast",
    nonRefundable: false,
    freeDays: "7",
    prices: { a: "750.000", b: "" },
    ...overrides,
  });
  const check = (overrides: Partial<RatePlanForm> = {}) =>
    checkRatePlan(form(overrides), rooms, bounds, formatRupiah);

  it("keeps only the room types that were given a price", () => {
    expect(check()).toEqual({
      ok: true,
      value: {
        name: "Harga Normal",
        meal_plan: "breakfast",
        non_refundable: false,
        free_cancellation_days: 7,
        prices: [{ room_type_id: "a", amount: 750000 }],
      },
    });
  });

  it("sends no free days for a non-refundable plan", () => {
    const checked = check({ nonRefundable: true, freeDays: "" });

    expect(checked.ok && checked.value).toMatchObject({ non_refundable: true });
    expect(checked.ok && "free_cancellation_days" in checked.value).toBe(false);
  });

  it("names each problem", () => {
    expect(problemOf(check({ name: "" }))).toBe("rates.form.needName");
    expect(problemOf(check({ freeDays: "366" }))).toBe("rates.form.badDays");
    expect(problemOf(check({ prices: {} }))).toBe("rates.form.needPrice");
    expect(problemOf(check({ prices: { a: "9.999" } }))).toBe("rates.form.badPrice");
    expect(problemOf(check({ prices: { a: "750000,50" } }))).toBe("rates.form.badPrice");
  });

  it("says which room and which range", () => {
    const checked = check({ prices: { b: "5" } });

    expect(!checked.ok && checked.problem.vars).toEqual({
      room: "Suite",
      min: "Rp 10.000",
      max: "Rp 500.000.000",
    });
  });
});

describe("numberSetting", () => {
  it("reads a number or falls back", () => {
    expect(numberSetting({ max_room_types: 12 }, "max_room_types", 30)).toBe(12);
    expect(numberSetting({ max_room_types: "12" }, "max_room_types", 30)).toBe(30);
    expect(numberSetting({}, "max_room_types", 30)).toBe(30);
  });
});

describe("texts", () => {
  it("has every form message in every language", () => {
    const keys = [
      "rooms.form.needName",
      "rooms.form.badUnits",
      "rooms.form.badGuests",
      "rates.form.needName",
      "rates.form.badDays",
      "rates.form.needPrice",
      "rates.form.badPrice",
    ];
    for (const locale of LOCALES) {
      for (const key of keys) {
        expect(translate(locale, key, { max: 1, min: 1, room: "x" })).not.toBe(key);
      }
    }
  });
});
