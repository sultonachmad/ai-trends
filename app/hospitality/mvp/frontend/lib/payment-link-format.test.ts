import { describe, expect, it } from "vitest";

import { LOCALES, translate } from "@/lib/i18n";
import {
  LINK_STATES,
  stateBadgeClass,
  stateLabelKey,
  timeLeft,
  timeLeftKey,
} from "@/lib/payment-link-format";

const now = new Date("2026-11-20T10:00:00Z");
const inMinutes = (minutes: number) => new Date(now.getTime() + minutes * 60_000).toISOString();

describe("timeLeft", () => {
  it.each([
    [1, { unit: "minutes", value: 1 }],
    [0.4, { unit: "minutes", value: 1 }],
    [90, { unit: "minutes", value: 90 }],
    [119, { unit: "minutes", value: 119 }],
    [120, { unit: "hours", value: 2 }],
    [24 * 60, { unit: "hours", value: 24 }],
    [47 * 60, { unit: "hours", value: 47 }],
    [48 * 60, { unit: "days", value: 2 }],
    [7 * 24 * 60 + 5, { unit: "days", value: 7 }],
  ])("%s minutes ahead is %o", (minutes, expected) => {
    expect(timeLeft(inMinutes(minutes), now)).toEqual(expected);
  });

  it.each([0, -1, -600])("is null once the time has passed (%s minutes)", (minutes) => {
    expect(timeLeft(inMinutes(minutes), now)).toBeNull();
  });

  it("is null for an unreadable date", () => {
    expect(timeLeft("not a date", now)).toBeNull();
  });
});

describe("labels", () => {
  it("has a label in both languages for every state and time unit", () => {
    const keys = [
      ...LINK_STATES.map(stateLabelKey),
      ...(["minutes", "hours", "days"] as const).map((unit) => timeLeftKey({ unit, value: 3 })),
    ];
    for (const key of keys) {
      for (const locale of LOCALES) {
        expect(translate(locale, key, { value: 3 })).not.toBe(key);
      }
    }
  });

  it("gives each kind of state a badge style", () => {
    expect(stateBadgeClass("paid")).toContain("bg-primary");
    expect(stateBadgeClass("pending")).toContain("bg-accent");
    expect(stateBadgeClass("expired")).toBe(stateBadgeClass("cancelled"));
  });
});
