import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api-client";
import {
  APOA_ERROR_CODES,
  APOA_TABS,
  apoaErrorKey,
  checkReason,
  checkReference,
  dueLabel,
  registerRange,
} from "@/lib/apoa-format";
import { LOCALES, translate } from "@/lib/i18n";

describe("APOA helpers", () => {
  it("says how long is left, or how late it is", () => {
    const now = new Date("2026-11-26T10:00:00Z");
    expect(dueLabel("2026-11-26T15:00:00Z", now)).toEqual({ key: "apoa.dueIn", hours: 5 });
    expect(dueLabel("2026-11-26T09:20:00Z", now)).toEqual({ key: "apoa.lateBy", hours: 1 });
    expect(dueLabel("2026-11-26T10:20:00Z", now)).toEqual({ key: "apoa.dueIn", hours: 1 });
    expect(dueLabel(null, now)).toBeNull();
  });

  it("checks references and reasons like the server", () => {
    expect(checkReference("  STT-01 ")).toEqual({ ok: true, value: "STT-01" });
    expect(checkReference("   ")).toEqual({ ok: true, value: null });
    expect(checkReference("<b>")).toEqual({ ok: false, key: "apoa.badReference" });
    expect(checkReference("x".repeat(81))).toEqual({ ok: false, key: "apoa.badReference" });
    expect(checkReason(" ok ")).toEqual({ ok: false, key: "apoa.needReason" });
    expect(checkReason("Diplomat")).toEqual({ ok: true, value: "Diplomat" });
    expect(checkReason("ok \u202edenied")).toEqual({ ok: false, key: "apoa.needReason" });
  });

  it("defaults the register to this month and refuses a reversed range", () => {
    expect(registerRange("2026-11-26", "", "")).toEqual({
      ok: true,
      value: { from: "2026-11-01", to: "2026-11-26" },
    });
    expect(registerRange("2026-11-26", "2026-11-10", "2026-11-01")).toEqual({
      ok: false,
      key: "apoa.badRange",
    });
  });

  it("translates APOA and guest ID refusals", () => {
    expect(apoaErrorKey(new ApiError(409, "x", { code: "arrival_first" }))).toBe(
      "apoa.error.arrival_first",
    );
    expect(apoaErrorKey(new ApiError(409, "x", { code: "guest_reported" }))).toBe(
      "guestid.error.guest_reported",
    );
    expect(apoaErrorKey(new Error("x"))).toBeNull();
  });

  it("has text for every tab and code in both languages", () => {
    const keys = [
      ...APOA_ERROR_CODES.map((code) => `apoa.error.${code}`),
      ...APOA_TABS.map((tab) => `apoa.tab.${tab}`),
      "guestid.error.guest_reported",
    ];
    for (const locale of LOCALES) {
      for (const key of keys) expect(translate(locale, key), `${locale} ${key}`).not.toBe(key);
    }
  });
});
