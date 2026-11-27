import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api-client";
import { translate } from "@/lib/i18n";
import type { MaintBoard, MaintRequest } from "@/lib/maintenance-api";
import {
  CATEGORIES,
  REPAIR_ERROR_CODES,
  STEPS,
  addDays,
  mineOrFree,
  nextSteps,
  nightsProblem,
  ordered,
  parseCost,
  repairError,
  shiftMonth,
  taxTotal,
} from "@/lib/maintenance-format";

const request = (overrides: Partial<MaintRequest> = {}): MaintRequest => ({
  id: "r1",
  number: "MT-0001",
  unit_id: "u1",
  room_name: "101",
  place: null,
  category: "ac",
  urgent: false,
  description: "AC bocor",
  status: "open",
  status_note: null,
  reported_by_name: "Wayan",
  reported_at: "2026-11-27T01:00:00Z",
  from_housekeeping: false,
  assigned_staff_id: null,
  assigned_name: null,
  vendor_name: null,
  mine: false,
  has_photo: false,
  off_sale: null,
  cost: null,
  completed_at: null,
  ...overrides,
});

describe("lists", () => {
  it("puts urgent open requests first and finished ones last", () => {
    const list = ordered([
      request({ id: "done", status: "completed", reported_at: "2026-11-27T03:00:00Z" }),
      request({ id: "old" }),
      request({ id: "urgent", urgent: true, reported_at: "2026-11-27T02:00:00Z" }),
    ]);
    expect(list.map((r) => r.id)).toEqual(["urgent", "old", "done"]);
  });

  it("my list holds mine and nobody's open requests", () => {
    const board: MaintBoard = {
      today: "2026-11-27",
      rooms: [],
      staff: [],
      requests: [
        request({ id: "mine", mine: true, assigned_staff_id: "me" }),
        request({ id: "free" }),
        request({ id: "vendor", vendor_name: "Pak Made" }),
        request({ id: "theirs", assigned_staff_id: "x" }),
      ],
    };
    expect(mineOrFree(board).map((r) => r.id)).toEqual(["mine", "free"]);
  });

  it("offers the next steps", () => {
    expect(nextSteps(request())).toEqual(["start", "fix"]);
    expect(nextSteps(request({ status: "in_progress" }))).toEqual(["wait", "fix"]);
    expect(nextSteps(request({ status: "completed" }))).toEqual([]);
  });
});

describe("off-sale nights and costs", () => {
  it("checks the nights", () => {
    expect(nightsProblem("2026-11-27", "2026-11-28", "2026-11-27")).toBeNull();
    expect(nightsProblem("2026-11-26", "2026-11-28", "2026-11-27")).toBe("repair.offSale.fromToday");
    expect(nightsProblem("2026-11-28", "2026-11-27", "2026-11-27")).toBe("repair.offSale.order");
    expect(nightsProblem("2026-11-27", addDays("2026-11-27", 90), "2026-11-27")).toBe("repair.offSale.tooLong");
  });

  it("reads Indonesian money", () => {
    expect(parseCost("150.000")).toBe(150000);
    expect(parseCost("")).toBeNull();
    expect(parseCost("abc")).toBeNaN();
  });
});

describe("refusals and months", () => {
  it("keeps the booking numbers or nights of a refusal", () => {
    const refusal = new ApiError(409, "x", { code: "room_booked", message: "x", items: ["VS-1"] });
    expect(repairError(refusal)).toEqual({ key: "repair.error.room_booked", items: ["VS-1"] });
    expect(repairError(new ApiError(409, "x", { code: "other" }))).toBeNull();
  });

  it("moves between months and sums tax", () => {
    expect(shiftMonth("2026-01", -1)).toBe("2025-12");
    expect(shiftMonth("2026-12", 1)).toBe("2027-01");
    const zero = {
      room_nights: 0, room_base: "0", extras_base: "0", untaxed: "0", channel_nights: 0,
      channel_base: "0", channel_service: "0", channel_pbjt: "0",
    };
    expect(taxTotal({ ...zero, service: "100000", pbjt: "110000" })).toBe(210000);
  });
});

describe("text", () => {
  it("has Indonesian and English for every category, step and refusal", () => {
    const keys = [
      ...CATEGORIES.map((c) => `repair.category.${c}`),
      ...STEPS.map((s) => `repair.status.${s}`),
      ...REPAIR_ERROR_CODES.map((c) => `repair.error.${c}`),
    ];
    for (const locale of ["id", "en"] as const) {
      for (const key of keys) expect(translate(locale, key), `${locale} ${key}`).not.toBe(key);
    }
  });
});
