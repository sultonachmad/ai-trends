import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api-client";

import {
  BILL_ERROR_CODES,
  balanceState,
  billErrorKey,
  checkCharge,
  checkCorrection,
  checkReason,
  lineLabelKey,
} from "@/lib/bill-format";
import { CHARGE_CATEGORIES } from "@/lib/bills-api";
import { LOCALES, translate } from "@/lib/i18n";

describe("charges", () => {
  it("multiplies and checks a charge", () => {
    expect(
      checkCharge({ category: "laundry", description: " Cuci ", quantity: "2", unitPrice: "25.000" }),
    ).toEqual({
      ok: true,
      value: { category: "laundry", description: "Cuci", quantity: 2, unit_price: 25000 },
    });
  });

  it("refuses empty or silly charges", () => {
    const good = { category: "other" as const, description: "x", quantity: "1", unitPrice: "1000" };
    expect(checkCharge({ ...good, description: " " }).ok).toBe(false);
    expect(checkCharge({ ...good, quantity: "0" }).ok).toBe(false);
    expect(checkCharge({ ...good, quantity: "1000" }).ok).toBe(false);
    expect(checkCharge({ ...good, quantity: "1.5" }).ok).toBe(false);
    expect(checkCharge({ ...good, unitPrice: "abc" }).ok).toBe(false);
  });
});

describe("corrections and reasons", () => {
  it("reads a signed amount", () => {
    expect(checkCorrection("-20.000")).toEqual({ ok: true, value: -20000 });
    expect(checkCorrection("15000")).toEqual({ ok: true, value: 15000 });
    expect(checkCorrection("0").ok).toBe(false);
    expect(checkCorrection("-").ok).toBe(false);
  });

  it("needs a real reason", () => {
    expect(checkReason("ok").ok).toBe(false);
    expect(checkReason("  Salah input  ")).toEqual({ ok: true, value: "Salah input" });
  });
});

describe("refusals", () => {
  it("translates bill and front desk refusals alike", () => {
    expect(billErrorKey(new ApiError(422, "x", { code: "discount_too_large" }))).toBe(
      "frontdesk.error.discount_too_large",
    );
    expect(billErrorKey(new ApiError(409, "x", { code: "room_taken" }))).toBe(
      "frontdesk.error.room_taken",
    );
    expect(billErrorKey(new ApiError(409, "x", { code: "made_up" }))).toBeNull();
  });
});

describe("display", () => {
  it("names the balance", () => {
    expect(balanceState("100.00")).toBe("owes");
    expect(balanceState("0.00")).toBe("settled");
    expect(balanceState("-5.00")).toBe("refund");
  });

  it("has every label in every language", () => {
    const keys = [
      ...CHARGE_CATEGORIES.map(lineLabelKey),
      lineLabelKey("discount"),
      lineLabelKey("correction"),
      ...BILL_ERROR_CODES.map((code) => `frontdesk.error.${code}`),
    ];
    for (const locale of LOCALES) {
      for (const key of keys) expect(translate(locale, key)).not.toBe(key);
    }
  });
});
