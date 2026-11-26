/** Front desk calls (backend: app/routers/front_desk.py). */

import type { HkProblem } from "@/lib/housekeeping-api";
import { request } from "@/lib/api-client";

export type EarlyChoice = "keep_price" | "nights_stayed";

export interface DeskRoom {
  line_id: string;
  unit_id: string | null;
  name: string | null;
  hk_status: string | null;
  service_status: string | null;
  locked: boolean;
}

export interface DeskEntry {
  id: string;
  number: string;
  status: string;
  guest_name: string;
  guest_phone: string | null;
  arrival: string;
  departure: string;
  nights: number;
  room_type: string;
  units: number;
  adults: number;
  children: number;
  source: string;
  total_amount: string;
  total_with_tax: string;
  balance_due: string;
  /** The arrival or departure should already have happened. */
  overdue: boolean;
  /** Today's check-in can still be taken back. */
  can_undo: boolean;
  rooms: DeskRoom[];
}

export interface RoomToday {
  id: string;
  name: string;
  room_type: string;
  hk_status: string;
  fo_status: string;
  service_status: string;
  guest_name: string | null;
  booking_id: string | null;
  departure: string | null;
}

export interface DeskToday {
  date: string;
  arrivals: DeskEntry[];
  in_house: DeskEntry[];
  departures: DeskEntry[];
  /** Checked out or no-show today, and still possible to undo. */
  done_today: DeskEntry[];
  rooms: RoomToday[];
  /** Foreign guests due or overdue in APOA (counts only). */
  apoa: { due: number; overdue: number };
  /** The oldest past day not closed yet, if any. */
  day_close: { unclosed: string | null };
  /** Housekeeping problems the desk has not dealt with yet. */
  problems: HkProblem[];
  /** How often the page refreshes while open, in seconds. */
  poll_seconds: number;
}

export interface FreeRoom {
  id: string;
  name: string;
  hk_status: string;
  service_status: string;
  ready: boolean;
}

const base = "/api/front-desk";
const json = (method: string, body: unknown) => ({ method, body: JSON.stringify(body) });

export const fetchDeskToday = () => request<DeskToday>(`${base}/today`);
export const fetchFreeRooms = (bookingId: string) =>
  request<FreeRoom[]>(`${base}/bookings/${bookingId}/free-rooms`);
export const assignRoom = (lineId: string, unitId: string | null, acceptNotReady = false) =>
  request<DeskEntry>(
    `${base}/lines/${lineId}/room`,
    json("PUT", { unit_id: unitId, accept_not_ready: acceptNotReady }),
  );
export const lockRoom = (lineId: string, locked: boolean) =>
  request<DeskEntry>(`${base}/lines/${lineId}/lock`, json("PUT", { locked }));
export const checkIn = (bookingId: string, acceptNotReady = false, noIdReason: string | null = null) =>
  request<DeskEntry>(
    `${base}/bookings/${bookingId}/check-in`,
    json("POST", {
      accept_not_ready: acceptNotReady,
      ...(noIdReason ? { no_id_reason: noIdReason } : {}),
    }),
  );
export const checkOut = (
  bookingId: string,
  early: EarlyChoice | null,
  leaveUnpaidReason: string | null = null,
) =>
  request<DeskEntry>(
    `${base}/bookings/${bookingId}/check-out`,
    json("POST", {
      ...(early ? { early } : {}),
      ...(leaveUnpaidReason ? { leave_unpaid_reason: leaveUnpaidReason } : {}),
    }),
  );
export const markNoShow = (bookingId: string) =>
  request<DeskEntry>(`${base}/bookings/${bookingId}/no-show`, { method: "POST" });
export const undoDeskAction = (bookingId: string, reason: string) =>
  request<DeskEntry>(`${base}/bookings/${bookingId}/undo`, json("POST", { reason }));
