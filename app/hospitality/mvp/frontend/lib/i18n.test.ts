import { describe, expect, it } from "vitest";

import {
  ALL_PROPERTY_TYPES,
  DEFAULT_LOCALE,
  LOCALES,
  ONBOARDING_PROPERTY_TYPES,
  isLocale,
  translate,
} from "@/lib/i18n";

describe("translate", () => {
  it("defaults to Bahasa Indonesia", () => {
    expect(DEFAULT_LOCALE).toBe("id");
  });

  it("returns the text in the requested language", () => {
    expect(translate("id", "onboarding.submit")).toBe("Buat ruang kerja");
    expect(translate("en", "onboarding.submit")).toBe("Create workspace");
  });

  it("fills placeholders", () => {
    expect(translate("en", "dashboard.linksUsed", { used: 3, limit: 30 })).toBe(
      "3 of 30 payment links used this month",
    );
    expect(translate("id", "dashboard.linksUsed", { used: 3, limit: 30 })).toBe(
      "3 dari 30 tautan pembayaran terpakai bulan ini",
    );
  });

  it("leaves a placeholder visible when its value is missing", () => {
    expect(translate("en", "dashboard.welcome")).toBe("Welcome, {name}");
  });

  it("returns the key itself for an unknown key", () => {
    expect(translate("id", "no.such.key")).toBe("no.such.key");
  });

  it("offers only known property types at onboarding", () => {
    for (const type of ONBOARDING_PROPERTY_TYPES) {
      expect(ALL_PROPERTY_TYPES).toContain(type);
    }
  });

  it("has a label in both languages for every property type the backend accepts", () => {
    for (const type of ALL_PROPERTY_TYPES) {
      for (const locale of LOCALES) {
        expect(translate(locale, `propertyType.${type}`)).not.toBe(`propertyType.${type}`);
      }
    }
  });
});

describe("isLocale", () => {
  it("accepts supported locales only", () => {
    expect(isLocale("id")).toBe(true);
    expect(isLocale("en")).toBe(true);
    expect(isLocale("fr")).toBe(false);
    expect(isLocale(null)).toBe(false);
  });
});
