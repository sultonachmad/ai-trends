import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api-client";
import {
  CHECK_CODES,
  END_OF_DAY_ERROR_CODES,
  blockingChecks,
  checkCount,
  dayBefore,
  endOfDayErrorKey,
  needsNote,
} from "@/lib/end-of-day-format";
import { LOCALES, translate } from "@/lib/i18n";

describe("end of day helpers", () => {
  it("knows the day before, across months and years", () => {
    expect(dayBefore("2026-12-01")).toBe("2026-11-30");
    expect(dayBefore("2027-01-01")).toBe("2026-12-31");
  });

  it("checks the count against what is expected", () => {
    expect(checkCount("450.000", "450000")).toEqual({ ok: true, value: 450000, difference: 0 });
    expect(checkCount("440000", "450000")).toEqual({ ok: true, value: 440000, difference: -10000 });
    expect(checkCount("abc", "450000")).toEqual({ ok: false, key: "drawer.badAmount" });
    expect(checkCount("0", "0")).toEqual({ ok: true, value: 0, difference: 0 });
    expect(needsNote(-10000, " ")).toBe(true);
    expect(needsNote(-10000, "Salah kembalian")).toBe(false);
    expect(needsNote(0, "")).toBe(false);
  });

  it("separates blocking items from warnings", () => {
    const checks = [
      { code: "arrivals_pending", level: "blocking" as const, count: 1, items: [] },
      { code: "proofs_waiting", level: "warning" as const, count: 2, items: [] },
    ];
    expect(blockingChecks(checks).map((c) => c.code)).toEqual(["arrivals_pending"]);
  });

  it("translates refusals, including a closed day on a payment", () => {
    expect(endOfDayErrorKey(new ApiError(409, "x", { code: "day_closed" }))).toBe(
      "endofday.error.day_closed",
    );
    expect(endOfDayErrorKey(new ApiError(409, "x", { code: "room_occupied" }))).toBe(
      "frontdesk.error.room_occupied",
    );
    expect(endOfDayErrorKey(new Error("x"))).toBeNull();
  });

  it("has text for every code in both languages", () => {
    const keys = [
      ...END_OF_DAY_ERROR_CODES.map((code) => `endofday.error.${code}`),
      ...CHECK_CODES.map((code) => `endofday.check.${code}`),
    ];
    for (const locale of LOCALES) {
      for (const key of keys) expect(translate(locale, key), `${locale} ${key}`).not.toBe(key);
    }
  });
});
