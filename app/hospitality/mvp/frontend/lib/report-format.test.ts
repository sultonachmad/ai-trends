import { describe, expect, it } from "vitest";

import { LOCALES, translate } from "@/lib/i18n";
import {
  PERIOD_PRESETS,
  barWidth,
  percentLabel,
  periodFor,
  periodProblem,
  todayIn,
} from "@/lib/report-format";

describe("periods", () => {
  it("builds this month", () => {
    expect(periodFor("this_month", "2028-02-10")).toEqual({
      from: "2028-02-01",
      to: "2028-02-29",
    });
  });

  it("builds last month across a year", () => {
    expect(periodFor("last_month", "2027-01-15")).toEqual({
      from: "2026-12-01",
      to: "2026-12-31",
    });
  });

  it("builds the last 30 days including today", () => {
    expect(periodFor("last_30", "2027-01-30")).toEqual({ from: "2027-01-01", to: "2027-01-30" });
  });

  it("uses the property's date, not the browser's", () => {
    const now = new Date("2026-11-30T17:00:00Z");
    expect(todayIn("Asia/Makassar", now)).toBe("2026-12-01");
    expect(todayIn("UTC", now)).toBe("2026-11-30");
  });

  it("refuses bad custom periods", () => {
    expect(periodProblem("", "2027-01-01")).toBe("reports.period.needDates");
    expect(periodProblem("2027-01-02", "2027-01-01")).toBe("reports.period.reversed");
    expect(periodProblem("2026-01-01", "2027-01-02")).toBe("reports.period.tooLong");
    expect(periodProblem("2026-01-01", "2027-01-01")).toBeNull();
  });
});

describe("display", () => {
  it("keeps bars in range", () => {
    expect(barWidth("60.0")).toBe("60%");
    expect(barWidth("140")).toBe("100%");
    expect(barWidth("x")).toBe("0%");
  });

  it("writes a percent", () => {
    expect(percentLabel("12.5")).toBe("12,5%");
  });

  it("has every period label in every language", () => {
    for (const locale of LOCALES) {
      for (const preset of PERIOD_PRESETS) {
        const key = `reports.preset.${preset}`;
        expect(translate(locale, key)).not.toBe(key);
      }
      for (const key of [
        "reports.period.needDates",
        "reports.period.reversed",
        "reports.period.tooLong",
      ]) {
        expect(translate(locale, key)).not.toBe(key);
      }
    }
  });
});
