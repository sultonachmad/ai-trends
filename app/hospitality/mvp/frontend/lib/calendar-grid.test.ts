import { describe, expect, it } from "vitest";

import {
  addDays,
  cellState,
  compactRupiah,
  dayHeading,
  daysBetween,
  isEditable,
  isWeekend,
  longDate,
  nextStart,
  parseNights,
  previousStart,
  rangeProblem,
  todayIn,
  weekdayIndex,
  weekdayName,
  weekdaysForRequest,
  windowDates,
  windowSize,
  WEEKDAYS,
  type RangeForm,
} from "@/lib/calendar-grid";
import { LOCALES, translate } from "@/lib/i18n";

const TODAY = "2026-11-20"; // a Friday
const LAST = "2027-11-19";

describe("date maths", () => {
  it("adds days across months and years without drifting", () => {
    expect(addDays("2026-02-28", 1)).toBe("2026-03-01");
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
    expect(addDays("2026-03-01", -1)).toBe("2026-02-28");
  });

  it("builds a window of consecutive dates", () => {
    expect(windowDates("2026-11-29", 3)).toEqual(["2026-11-29", "2026-11-30", "2026-12-01"]);
  });

  it("counts days between dates", () => {
    expect(daysBetween("2026-11-20", "2026-11-20")).toBe(0);
    expect(daysBetween("2026-11-20", "2026-12-20")).toBe(30);
    expect(daysBetween("2026-11-20", "2026-11-18")).toBe(-2);
  });

  it("moves a whole window back and forward", () => {
    expect(previousStart("2026-11-20", 14)).toBe("2026-11-06");
    expect(nextStart("2026-11-20", 7)).toBe("2026-11-27");
  });
});

describe("weekdays", () => {
  it("numbers Monday as 0 like the server", () => {
    expect(weekdayIndex("2026-11-16")).toBe(0);
    expect(weekdayIndex(TODAY)).toBe(4);
    expect(weekdayIndex("2026-11-22")).toBe(6);
  });

  it("knows the weekend", () => {
    expect(["2026-11-20", "2026-11-21", "2026-11-22"].map(isWeekend)).toEqual([false, true, true]);
  });

  it("names weekdays in both languages", () => {
    expect(weekdayName(0, "id", "long")).toBe("Senin");
    expect(weekdayName(6, "en", "long")).toBe("Sunday");
    expect(weekdayName(4, "en")).toBe("Fri");
  });

  it("omits weekdays from the request when every day is chosen", () => {
    expect(weekdaysForRequest([...WEEKDAYS])).toBeUndefined();
    expect(weekdaysForRequest([5, 4])).toEqual([4, 5]);
  });
});

describe("headings", () => {
  it("gives short parts for a column", () => {
    expect(dayHeading(TODAY, "en")).toEqual({ weekday: "Fri", day: "20", month: "Nov" });
    expect(dayHeading(TODAY, "id").weekday).toBe("Jum");
  });

  it("gives a full date for sentences", () => {
    expect(longDate(TODAY, "en")).toBe("Friday, 20 November 2026");
    expect(longDate(TODAY, "id")).toBe("Jumat, 20 November 2026");
  });
});

describe("window size", () => {
  it("shows a week on a phone and two weeks on a wide screen", () => {
    expect(windowSize(390)).toBe(7);
    expect(windowSize(768)).toBe(14);
    expect(windowSize(1440)).toBe(14);
  });
});

describe("cellState", () => {
  it("separates past, locked, closed and open", () => {
    expect(cellState({ date: "2026-11-19", closed: false }, TODAY, LAST)).toBe("past");
    expect(cellState({ date: "2027-11-20", closed: false }, TODAY, LAST)).toBe("locked");
    expect(cellState({ date: TODAY, closed: true }, TODAY, LAST)).toBe("closed");
    expect(cellState({ date: LAST, closed: false }, TODAY, LAST)).toBe("open");
  });

  it("past wins over closed", () => {
    expect(cellState({ date: "2026-11-01", closed: true }, TODAY, LAST)).toBe("past");
  });

  it("only today through the last date can be edited", () => {
    expect(["2026-11-19", TODAY, LAST, "2027-11-20"].map((d) => isEditable(d, TODAY, LAST))).toEqual([
      false,
      true,
      true,
      false,
    ]);
  });
});

describe("rangeProblem", () => {
  const form = (overrides: Partial<RangeForm> = {}): RangeForm => ({
    start: TODAY,
    end: "2026-11-30",
    roomTypeIds: ["a"],
    weekdays: [...WEEKDAYS],
    ...overrides,
  });
  const check = (overrides: Partial<RangeForm>, maxDays = 365) =>
    rangeProblem(form(overrides), TODAY, LAST, maxDays);

  it("accepts a sensible range", () => {
    expect(check({})).toBeNull();
    expect(check({ start: TODAY, end: LAST })).toBeNull();
  });

  it("names each problem", () => {
    expect(check({ start: "" })).toBe("calendar.form.needDates");
    expect(check({ end: "2026-11-19" })).toBe("calendar.form.reversed");
    expect(check({ start: "2026-11-19" })).toBe("calendar.form.past");
    expect(check({ end: "2027-11-20" })).toBe("calendar.form.beyond");
    expect(check({ end: "2026-11-27" }, 7)).toBe("calendar.form.tooLong");
    expect(check({ roomTypeIds: [] })).toBe("calendar.form.needRoom");
    expect(check({ weekdays: [] })).toBe("calendar.form.needWeekday");
  });

  it("notices weekdays that match no date in the range", () => {
    expect(check({ end: "2026-11-21", weekdays: [0] })).toBe("calendar.form.noMatch");
    expect(check({ end: "2026-11-23", weekdays: [0] })).toBeNull();
  });

  it("has a message for every problem in every language", () => {
    const keys = [
      "needDates",
      "reversed",
      "past",
      "beyond",
      "tooLong",
      "needRoom",
      "needWeekday",
      "noMatch",
    ].map((name) => `calendar.form.${name}`);
    for (const locale of LOCALES) {
      for (const key of keys) {
        expect(translate(locale, key, { max: 365, date: "x" })).not.toBe(key);
      }
    }
  });
});

describe("parseNights", () => {
  it("reads whole nights from 1 to 365", () => {
    expect(parseNights("1")).toBe(1);
    expect(parseNights(" 3 ")).toBe(3);
    expect(parseNights("365")).toBe(365);
  });

  it("refuses anything else", () => {
    expect(["0", "366", "2.5", "-1", "tiga", "", "1000"].map(parseNights)).toEqual(
      Array(7).fill(null),
    );
  });
});

describe("compactRupiah", () => {
  it("shortens thousands and millions the Indonesian way", () => {
    expect(compactRupiah("750000.00", "id")).toBe("750rb");
    expect(compactRupiah(1250000, "id")).toBe("1,25jt");
    expect(compactRupiah(2000000, "id")).toBe("2jt");
    expect(compactRupiah(15500, "id")).toBe("15,5rb");
  });

  it("uses k and m in English", () => {
    expect(compactRupiah(750000, "en")).toBe("750k");
    expect(compactRupiah(1250000, "en")).toBe("1.25m");
  });

  it("leaves small amounts alone and survives nonsense", () => {
    expect(compactRupiah(900, "id")).toBe("900");
    expect(compactRupiah("abc", "id")).toBe("");
  });
});

describe("todayIn", () => {
  const lateUtc = new Date("2026-11-30T17:30:00Z"); // 01:30 on 1 Dec in Bali

  it("is the date at the property", () => {
    expect(todayIn("Asia/Makassar", lateUtc)).toBe("2026-12-01");
    expect(todayIn("UTC", lateUtc)).toBe("2026-11-30");
  });

  it("falls back for an unknown timezone", () => {
    expect(todayIn("Not/AZone", lateUtc)).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});
