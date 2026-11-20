/**
 * Pure helpers for the matching editor: our room type + rate plan pairs on one side,
 * the channel's room + rate pairs on the other, each used at most once.
 */

import type { ChannelProducts, MappingPair } from "@/lib/channels-api";
import type { RatePlan } from "@/lib/rate-plans-api";
import type { RoomType } from "@/lib/rooms-api";

const SEPARATOR = "|";

export interface OwnPair {
  key: string;
  roomTypeId: string;
  ratePlanId: string;
  roomName: string;
  planName: string;
  maxGuests: number;
}

export interface ChannelPair {
  key: string;
  roomId: string;
  rateId: string;
  label: string;
  maxGuests: number;
}

/** our pair key -> chosen channel pair key ("" = not sold on this channel) */
export type Selection = Record<string, string>;

export const pairKey = (first: string, second: string) => `${first}${SEPARATOR}${second}`;

/** Every room type in use with every rate plan in use that sells it, in screen order. */
export function ownPairs(rooms: RoomType[], plans: RatePlan[]): OwnPair[] {
  return rooms
    .filter((room) => room.is_active)
    .flatMap((room) =>
      plans
        .filter(
          (plan) =>
            plan.is_active && plan.prices.some((price) => price.room_type_id === room.id),
        )
        .map((plan) => ({
          key: pairKey(room.id, plan.id),
          roomTypeId: room.id,
          ratePlanId: plan.id,
          roomName: room.name,
          planName: plan.name,
          maxGuests: room.max_guests,
        })),
    );
}

/** Every room + rate the channel lists. */
export function channelPairs(products: ChannelProducts | null): ChannelPair[] {
  return (products?.rooms ?? []).flatMap((room) =>
    room.rates.map((rate) => ({
      key: pairKey(room.id, rate.id),
      roomId: room.id,
      rateId: rate.id,
      label: `${room.name} · ${rate.name}`,
      maxGuests: room.max_guests,
    })),
  );
}

export function selectionOf(mappings: MappingPair[]): Selection {
  return Object.fromEntries(
    mappings.map((mapping) => [
      pairKey(mapping.room_type_id, mapping.rate_plan_id),
      pairKey(mapping.external_room_id, mapping.external_rate_id),
    ]),
  );
}

/** Channel pairs chosen for more than one of our pairs. */
export function usedTwice(selection: Selection): string[] {
  const counts = new Map<string, number>();
  for (const chosen of Object.values(selection)) {
    if (chosen !== "") counts.set(chosen, (counts.get(chosen) ?? 0) + 1);
  }
  return [...counts].filter(([, count]) => count > 1).map(([key]) => key);
}

/** The request body for a selection; pairs left empty are simply not sent. */
export function mappingsOf(own: OwnPair[], selection: Selection): MappingPair[] {
  return own.flatMap((pair) => {
    const chosen = selection[pair.key] ?? "";
    if (chosen === "") return [];
    const [externalRoomId, externalRateId] = chosen.split(SEPARATOR);
    return [
      {
        room_type_id: pair.roomTypeId,
        rate_plan_id: pair.ratePlanId,
        external_room_id: externalRoomId,
        external_rate_id: externalRateId,
      },
    ];
  });
}

/** Our pairs whose chosen channel room fits fewer guests than ours. */
export function tighterRooms(own: OwnPair[], theirs: ChannelPair[], selection: Selection): OwnPair[] {
  const guests = new Map(theirs.map((pair) => [pair.key, pair.maxGuests]));
  return own.filter((pair) => {
    const fits = guests.get(selection[pair.key] ?? "");
    return fits !== undefined && fits < pair.maxGuests;
  });
}

/** True when two selections choose the same channel pair for every one of our pairs. */
export function isUnchanged(a: Selection, b: Selection, own: OwnPair[]): boolean {
  return own.every((pair) => (a[pair.key] ?? "") === (b[pair.key] ?? ""));
}
