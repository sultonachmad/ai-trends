import { describe, expect, it } from "vitest";

import { LOCALES, translate } from "@/lib/i18n";
import {
  isBlocked,
  quotaPercent,
  quotaState,
  quotaTextKey,
  resetDateLabel,
  type LinkUsage,
  type QuotaState,
} from "@/lib/link-quota";

const usage = (overrides: Partial<LinkUsage> = {}): LinkUsage => ({
  payment_links_used: 3,
  payment_links_limit: 30,
  payment_links_resets_at: "2026-11-30T16:00:00Z",
  payment_links_resets_on: "2026-12-01",
  payment_links_warning: false,
  payment_links_limit_reached: false,
  ...overrides,
});

const STATES: QuotaState[] = ["unlimited", "ok", "warning", "reached", "notInPlan"];

describe("quotaState", () => {
  it("is ok below the warning point", () => {
    expect(quotaState(usage())).toBe("ok");
  });

  it("follows the server's warning and limit flags", () => {
    expect(quotaState(usage({ payment_links_used: 24, payment_links_warning: true }))).toBe(
      "warning",
    );
    expect(
      quotaState(usage({ payment_links_used: 30, payment_links_limit_reached: true })),
    ).toBe("reached");
  });

  it("knows a plan with no limit and a plan with no links", () => {
    expect(quotaState(usage({ payment_links_limit: null }))).toBe("unlimited");
    expect(
      quotaState(usage({ payment_links_limit: 0, payment_links_limit_reached: true })),
    ).toBe("notInPlan");
  });
});

describe("isBlocked", () => {
  it("blocks only when no link can be created", () => {
    expect(STATES.filter(isBlocked)).toEqual(["reached", "notInPlan"]);
  });
});

describe("quotaPercent", () => {
  it("is the share of the limit used", () => {
    expect(quotaPercent(usage({ payment_links_used: 15 }))).toBe(50);
    expect(quotaPercent(usage({ payment_links_used: 1 }))).toBe(3);
  });

  it("never passes 100, even when the limit was lowered later", () => {
    expect(quotaPercent(usage({ payment_links_used: 45 }))).toBe(100);
  });

  it("is null without a limit to measure against", () => {
    expect(quotaPercent(usage({ payment_links_limit: null }))).toBeNull();
    expect(quotaPercent(usage({ payment_links_limit: 0 }))).toBeNull();
  });
});

describe("resetDateLabel", () => {
  it("shows the property's local date as given by the server", () => {
    expect(resetDateLabel("2026-12-01", "id")).toBe("1 Desember");
    expect(resetDateLabel("2026-12-01", "en")).toBe("1 December");
    expect(resetDateLabel("2027-01-01", "en")).toBe("1 January");
  });
});

describe("texts", () => {
  it("has a usage line for every state in every language", () => {
    for (const locale of LOCALES) {
      for (const state of STATES) {
        const key = quotaTextKey(state);
        expect(translate(locale, key, { used: 1, limit: 30, date: "1 December" })).not.toBe(key);
      }
    }
  });
});
