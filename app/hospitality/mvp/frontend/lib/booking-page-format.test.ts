import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api-client";
import {
  ERROR_CODES,
  addDays,
  bookingPageUrl,
  changedTotal,
  compactPrice,
  errorCode,
  freeCancelUntil,
  hasFreeCancellation,
  isValidSlug,
  leadingBlanks,
  monthRange,
  newCheckoutKey,
  nightsBetween,
  parseDeepLink,
  plateVariant,
  recallBookingPath,
  rememberBookingPath,
  shiftMonth,
  termsKey,
  whatsappUrl,
} from "@/lib/booking-page-format";
import { LOCALES, translate } from "@/lib/i18n";

describe("room presentation", () => {
  it("gives a room the same plate every time, within range", () => {
    expect(plateVariant("room-a", 3)).toBe(plateVariant("room-a", 3));
    for (const id of ["", "a", "room-b", "9f3c-11"]) {
      const variant = plateVariant(id, 3);
      expect(variant).toBeGreaterThanOrEqual(0);
      expect(variant).toBeLessThan(3);
    }
  });

  it("gives neighbouring rooms different plates when the room order is known", () => {
    const order = ["room-c", "room-a", "room-b"];
    expect(order.map((id) => plateVariant(id, 3, order))).toEqual([0, 1, 2]);
    expect(plateVariant("not-listed", 3, order)).toBe(plateVariant("not-listed", 3));
  });

  it("badges a room only when a refundable rate has a cancellation window", () => {
    const rate = { non_refundable: false, free_cancellation_days: 3 };
    expect(hasFreeCancellation([rate])).toBe(true);
    expect(hasFreeCancellation([{ ...rate, non_refundable: true }])).toBe(false);
    expect(hasFreeCancellation([{ ...rate, free_cancellation_days: null }])).toBe(false);
    expect(hasFreeCancellation([])).toBe(false);
  });

  it("builds a WhatsApp link from digits, or none without a number", () => {
    expect(whatsappUrl("+62 812-3456")).toBe("https://wa.me/628123456");
    expect(whatsappUrl(null)).toBeNull();
    expect(whatsappUrl("n/a")).toBeNull();
  });
});

describe("dates", () => {
  it("moves across months and years", () => {
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
    expect(nightsBetween("2026-12-30", "2027-01-02")).toBe(3);
    expect(shiftMonth("2026-12-15", 1)).toBe("2027-01-01");
    expect(shiftMonth("2027-01-15", -1)).toBe("2026-12-01");
  });

  it("knows the month's length, including February", () => {
    expect(monthRange("2028-02-10")).toEqual({ from: "2028-02-01", to: "2028-02-29" });
  });

  it("starts the grid on Monday", () => {
    expect(leadingBlanks("2026-11-01")).toBe(6); // a Sunday
    expect(leadingBlanks("2026-12-01")).toBe(1); // a Tuesday
  });

  it("gives the last free-cancellation day", () => {
    expect(freeCancelUntil("2026-12-10", 7)).toBe("2026-12-03");
    expect(freeCancelUntil("2026-12-10", null)).toBeNull();
  });
});

describe("compactPrice", () => {
  it("shortens rupiah", () => {
    expect(compactPrice("500000.00")).toBe("500rb");
    expect(compactPrice(1_200_000)).toBe("1,2jt");
    expect(compactPrice("x")).toBe("");
  });
});

describe("parseDeepLink", () => {
  it("reads a valid link", () => {
    const link = parseDeepLink(
      new URLSearchParams("arrival=2027-01-01&departure=2027-01-03&adults=3&children=1&room=r1"),
    );
    expect(link).toEqual({
      arrival: "2027-01-01",
      departure: "2027-01-03",
      adults: 3,
      children: 1,
      room: "r1",
    });
  });

  it("ignores reversed dates and bad counts", () => {
    const link = parseDeepLink(
      new URLSearchParams("arrival=2027-01-03&departure=2027-01-01&adults=-1&children=abc"),
    );
    expect(link.arrival).toBeUndefined();
    expect(link.adults).toBe(2);
    expect(link.children).toBe(0);
  });

  it("builds a shareable link", () => {
    expect(
      bookingPageUrl("https://x.id/", "villa", { arrival: "2027-01-01", departure: "2027-01-02" }),
    ).toBe("https://x.id/book/villa?arrival=2027-01-01&departure=2027-01-02");
    expect(bookingPageUrl("https://x.id", "villa")).toBe("https://x.id/book/villa");
  });
});

describe("page names", () => {
  it("accepts short lowercase names only", () => {
    expect(isValidSlug("villa-ubud")).toBe(true);
    for (const bad of ["a", "Villa", "-villa", "villa-", "vi lla"]) {
      expect(isValidSlug(bad)).toBe(false);
    }
  });
});

describe("errors", () => {
  it("reads the server's code and new total", () => {
    const failure = new ApiError(409, "x", { code: "price_changed", total: "900000.00" });
    expect(errorCode(failure)).toBe("price_changed");
    expect(changedTotal(failure)).toBe("900000.00");
  });

  it("treats anything else as unknown", () => {
    expect(errorCode(new ApiError(500, "boom"))).toBe("unknown");
    expect(errorCode(new Error("x"))).toBe("unknown");
    expect(changedTotal(new Error("x"))).toBeNull();
  });

  it("has every error message in every language", () => {
    for (const locale of LOCALES) {
      for (const code of ERROR_CODES) {
        expect(translate(locale, `book.error.${code}`)).not.toBe(`book.error.${code}`);
      }
    }
  });
});

describe("checkout", () => {
  it("makes keys the server accepts", () => {
    expect(newCheckoutKey()).toMatch(/^[A-Za-z0-9_-]{16,64}$/);
    expect(newCheckoutKey()).not.toBe(newCheckoutKey());
  });

  it("labels terms", () => {
    expect(termsKey({ non_refundable: true })).toBe("book.terms.nonRefundable");
    expect(termsKey({ non_refundable: false })).toBe("book.terms.free");
  });
});

describe("the way back from the pay page", () => {
  it("remembers the guest's page only for that pay link", () => {
    const store = new Map<string, string>();
    Object.defineProperty(globalThis, "window", {
      configurable: true,
      value: {
        sessionStorage: {
          getItem: (key: string) => store.get(key) ?? null,
          setItem: (key: string, value: string) => store.set(key, value),
        },
      },
    });
    rememberBookingPath("https://x.id/pay/abc", "/booking/secret");
    expect(recallBookingPath("abc")).toBe("/booking/secret");
    expect(recallBookingPath("other")).toBeNull();
    rememberBookingPath("https://x.id/pay/bad", "https://evil.example/");
    expect(recallBookingPath("bad")).toBeNull();
  });
});
