import { describe, expect, it } from "vitest";

import {
  isOpen,
  paymentBadgeClass,
  paymentStateKey,
  shortDate,
  sourceLabelKey,
  stayRange,
  todayNote,
} from "@/lib/booking-format";
import { STAFF_SOURCES, type PaymentState } from "@/lib/bookings-api";
import { LOCALES, translate } from "@/lib/i18n";

const STATES: PaymentState[] = ["unpaid", "partly_paid", "paid", "overpaid"];

describe("dates", () => {
  it("formats one date", () => {
    expect(shortDate("2026-11-20", "en")).toBe("20 Nov 2026");
    expect(shortDate("2026-12-01", "id")).toBe("1 Des 2026");
  });

  it("shortens a range inside one month", () => {
    expect(stayRange("2026-11-20", "2026-11-23", "en")).toBe("20–23 Nov 2026");
  });

  it("names both months when the stay crosses a month", () => {
    expect(stayRange("2026-11-28", "2026-12-02", "id")).toBe("28 Nov – 2 Des 2026");
  });

  it("names both years when the stay crosses a year", () => {
    expect(stayRange("2026-12-30", "2027-01-02", "en")).toBe("30 Dec 2026 – 2 Jan 2027");
  });
});

describe("labels", () => {
  it("has a payment label and badge for every state in every language", () => {
    for (const state of STATES) {
      expect(paymentBadgeClass(state)).not.toBe("");
      for (const locale of LOCALES) {
        expect(translate(locale, paymentStateKey(state))).not.toBe(paymentStateKey(state));
      }
    }
  });

  it("has a name for every source staff can pick in every language", () => {
    for (const source of STAFF_SOURCES) {
      for (const locale of LOCALES) {
        expect(translate(locale, sourceLabelKey(source))).not.toBe(sourceLabelKey(source));
      }
    }
  });
});

describe("todayNote", () => {
  const stay = { arrival: "2026-11-20", departure: "2026-11-23", status: "confirmed" as const };

  it("marks arrivals and departures of today", () => {
    expect(todayNote(stay, "2026-11-20")).toBe("arriving");
    expect(todayNote(stay, "2026-11-23")).toBe("leaving");
    expect(todayNote(stay, "2026-11-21")).toBeNull();
  });

  it("says nothing about cancelled bookings", () => {
    expect(todayNote({ ...stay, status: "cancelled" }, "2026-11-20")).toBeNull();
    expect(isOpen({ status: "cancelled" })).toBe(false);
    expect(isOpen(stay)).toBe(true);
  });
});
