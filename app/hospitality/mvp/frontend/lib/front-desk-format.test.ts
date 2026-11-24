import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api-client";
import type { DeskEntry } from "@/lib/front-desk-api";
import {
  DESK_ERROR_CODES,
  DESK_TABS,
  HK_STATUSES,
  allRoomsAssigned,
  deskErrorKey,
  leavesEarly,
  owesMoney,
  refusedRooms,
} from "@/lib/front-desk-format";
import { LOCALES, translate } from "@/lib/i18n";

const room = (unit: string | null) => ({
  line_id: "l",
  unit_id: unit,
  name: unit,
  hk_status: "clean",
  service_status: "in_service",
  locked: false,
});
const entry = (overrides: Partial<DeskEntry> = {}) =>
  ({ departure: "2027-01-05", balance_due: "0.00", rooms: [room("a")], ...overrides }) as DeskEntry;

describe("front desk rules", () => {
  it("needs every room assigned", () => {
    expect(allRoomsAssigned(entry())).toBe(true);
    expect(allRoomsAssigned(entry({ rooms: [room("a"), room(null)] }))).toBe(false);
  });

  it("knows when a guest leaves early", () => {
    expect(leavesEarly(entry(), "2027-01-04")).toBe(true);
    expect(leavesEarly(entry(), "2027-01-05")).toBe(false);
    expect(leavesEarly(entry(), "2027-01-06")).toBe(false);
  });

  it("knows when money is owed", () => {
    expect(owesMoney(entry({ balance_due: "1.00" }))).toBe(true);
    expect(owesMoney(entry())).toBe(false);
    expect(owesMoney(entry({ balance_due: "-5.00" }))).toBe(false);
  });
});

describe("refusals", () => {
  it("reads the code and rooms the server sent", () => {
    const cause = new ApiError(409, "x", { code: "room_not_ready", rooms: ["Deluxe 1"] });
    expect(deskErrorKey(cause)).toBe("frontdesk.error.room_not_ready");
    expect(refusedRooms(cause)).toEqual(["Deluxe 1"]);
  });

  it("leaves other errors alone", () => {
    expect(deskErrorKey(new Error("x"))).toBeNull();
    expect(deskErrorKey(new ApiError(500, "x", { code: "made_up" }))).toBeNull();
    expect(refusedRooms(new Error("x"))).toEqual([]);
  });

  it("has every label in every language", () => {
    const keys = [
      ...DESK_ERROR_CODES.map((code) => `frontdesk.error.${code}`),
      ...DESK_TABS.map((tab) => `frontdesk.tab.${tab}`),
      ...HK_STATUSES.map((status) => `frontdesk.hk.${status}`),
    ];
    for (const locale of LOCALES) {
      for (const key of keys) expect(translate(locale, key)).not.toBe(key);
    }
  });
});
