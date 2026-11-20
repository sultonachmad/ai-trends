/**
 * Room type calls (backend: app/routers/rooms.py).
 */

import { request } from "@/lib/api-client";

export type RoomKind = "room" | "villa" | "apartment" | "cabin" | "other";
export const ROOM_KINDS: readonly RoomKind[] = ["room", "villa", "apartment", "cabin", "other"];

export interface RoomUnit {
  id: string;
  name: string;
}

export interface RoomType {
  id: string;
  name: string;
  kind: RoomKind;
  max_guests: number;
  is_active: boolean;
  /** The units in use, in order. */
  units: RoomUnit[];
}

export interface RoomTypeInput {
  name: string;
  kind: RoomKind;
  units: number;
  max_guests: number;
}

const base = "/api/room-types";
const json = (method: string, body: unknown) => ({ method, body: JSON.stringify(body) });

export const fetchRoomTypes = () => request<RoomType[]>(base);
export const createRoomType = (input: RoomTypeInput) =>
  request<RoomType>(base, json("POST", input));
export const updateRoomType = (id: string, changes: Partial<RoomTypeInput & { is_active: boolean }>) =>
  request<RoomType>(`${base}/${id}`, json("PATCH", changes));
export const renameUnit = (roomTypeId: string, unitId: string, name: string) =>
  request<RoomType>(`${base}/${roomTypeId}/units/${unitId}`, json("PATCH", { name }));
