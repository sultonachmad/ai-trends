import { describe, expect, it } from "vitest";

import {
  channelPairs,
  isUnchanged,
  mappingsOf,
  ownPairs,
  pairKey,
  selectionOf,
  tighterRooms,
  usedTwice,
} from "@/lib/channel-mapping";
import type { ChannelProducts } from "@/lib/channels-api";
import type { RatePlan } from "@/lib/rate-plans-api";
import type { RoomType } from "@/lib/rooms-api";

const room = (id: string, name: string, guests: number, active = true): RoomType => ({
  id,
  name,
  kind: "room",
  max_guests: guests,
  is_active: active,
  units: [],
});
const plan = (id: string, name: string, roomIds: string[], active = true): RatePlan => ({
  id,
  name,
  meal_plan: "room_only",
  non_refundable: false,
  free_cancellation_days: 7,
  is_active: active,
  prices: roomIds.map((roomId) => ({ room_type_id: roomId, amount: "500000.00" })),
});

const ROOMS = [room("deluxe", "Deluxe", 2), room("suite", "Suite", 4), room("old", "Old", 2, false)];
const PLANS = [
  plan("normal", "Normal", ["deluxe", "suite", "old"]),
  plan("hemat", "Hemat", ["deluxe"]),
  plan("gone", "Gone", ["suite"], false),
];
const PRODUCTS: ChannelProducts = {
  property_name: "Listing",
  rooms: [
    { id: "R1", name: "Deluxe Twin", max_guests: 2, rates: [{ id: "P1", name: "Std" }, { id: "P2", name: "NR" }] },
    { id: "R2", name: "Suite", max_guests: 3, rates: [{ id: "P3", name: "Std" }] },
  ],
};

describe("pairs", () => {
  it("lists our pairs for rooms and plans in use only", () => {
    expect(ownPairs(ROOMS, PLANS).map((pair) => `${pair.roomName}/${pair.planName}`)).toEqual([
      "Deluxe/Normal",
      "Deluxe/Hemat",
      "Suite/Normal",
    ]);
  });

  it("lists the channel's room and rate pairs with readable labels", () => {
    expect(channelPairs(PRODUCTS).map((pair) => [pair.key, pair.label])).toEqual([
      ["R1|P1", "Deluxe Twin · Std"],
      ["R1|P2", "Deluxe Twin · NR"],
      ["R2|P3", "Suite · Std"],
    ]);
    expect(channelPairs(null)).toEqual([]);
  });
});

describe("selection", () => {
  const own = ownPairs(ROOMS, PLANS);
  const saved = [
    { room_type_id: "deluxe", rate_plan_id: "normal", external_room_id: "R1", external_rate_id: "P1" },
  ];

  it("round-trips through the saved matching", () => {
    const selection = selectionOf(saved);

    expect(selection).toEqual({ [pairKey("deluxe", "normal")]: "R1|P1" });
    expect(mappingsOf(own, selection)).toEqual(saved);
  });

  it("leaves out pairs that are not sold on the channel", () => {
    expect(mappingsOf(own, { [pairKey("deluxe", "normal")]: "", [pairKey("suite", "normal")]: "R2|P3" })).toEqual([
      { room_type_id: "suite", rate_plan_id: "normal", external_room_id: "R2", external_rate_id: "P3" },
    ]);
  });

  it("spots a channel pair chosen twice", () => {
    expect(usedTwice({ a: "R1|P1", b: "R1|P1", c: "R2|P3", d: "" })).toEqual(["R1|P1"]);
    expect(usedTwice({ a: "R1|P1", b: "", c: "" })).toEqual([]);
  });

  it("warns when the channel room fits fewer guests", () => {
    const selection = { [pairKey("suite", "normal")]: "R2|P3", [pairKey("deluxe", "normal")]: "R1|P1" };

    expect(tighterRooms(own, channelPairs(PRODUCTS), selection).map((pair) => pair.roomName)).toEqual([
      "Suite",
    ]);
  });

  it("knows when nothing was changed", () => {
    const selection = selectionOf(saved);

    expect(isUnchanged(selection, { ...selection, [pairKey("suite", "normal")]: "" }, own)).toBe(true);
    expect(isUnchanged(selection, { ...selection, [pairKey("suite", "normal")]: "R2|P3" }, own)).toBe(
      false,
    );
  });
});
