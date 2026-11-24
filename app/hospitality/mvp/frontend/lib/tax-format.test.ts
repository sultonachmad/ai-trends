import { describe, expect, it } from "vitest";

import { LOCALES, translate } from "@/lib/i18n";
import { PBJT_MAX, SERVICE_MAX, checkTaxForm, examplePrice } from "@/lib/tax-format";

const form = {
  regionCode: "51.03",
  pbjt: "10",
  service: "10",
  pbjtOnService: true,
  mode: "plus_plus" as const,
  untaxed: ["transport" as const],
  effectiveFrom: "2027-01-01",
  confirmed: true,
};

describe("tax form", () => {
  it("accepts sane rates with a decimal comma", () => {
    expect(checkTaxForm({ ...form, pbjt: "7,5" }, "2027-01-01")).toEqual({
      ok: true,
      value: {
        region_code: "51.03",
        pbjt_pct: "7.5",
        service_pct: "10",
        pbjt_on_service: true,
        price_mode: "plus_plus",
        untaxed_categories: ["transport"],
        effective_from: "2027-01-01",
        confirmed: true,
      },
    });
  });

  it("refuses what the law or the owner would not allow", () => {
    expect(checkTaxForm({ ...form, pbjt: String(PBJT_MAX + 1) }, "2027-01-01").ok).toBe(false);
    expect(checkTaxForm({ ...form, service: String(SERVICE_MAX + 1) }, "2027-01-01").ok).toBe(false);
    expect(checkTaxForm({ ...form, pbjt: "abc" }, "2027-01-01").ok).toBe(false);
    expect(checkTaxForm({ ...form, regionCode: "" }, "2027-01-01").ok).toBe(false);
    expect(checkTaxForm({ ...form, confirmed: false }, "2027-01-01").ok).toBe(false);
    expect(checkTaxForm({ ...form, effectiveFrom: "2026-12-31" }, "2027-01-01").ok).toBe(false);
  });
});

describe("example", () => {
  it("shows what Rp 500.000 becomes", () => {
    expect(examplePrice(500000, 10, 10, true, "plus_plus")).toEqual({
      base: 500000,
      service: 50000,
      pbjt: 55000,
      total: 605000,
    });
    expect(examplePrice(605000, 10, 10, true, "nett")).toEqual({
      base: 500000,
      service: 50000,
      pbjt: 55000,
      total: 605000,
    });
  });

  it("has its labels in every language", () => {
    for (const locale of LOCALES) {
      for (const key of ["settings.taxes.title", "settings.taxes.badRate", "settings.taxes.needConfirm"]) {
        expect(translate(locale, key)).not.toBe(key);
      }
    }
  });
});
