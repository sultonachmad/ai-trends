/** Repair requests (backend: app/routers/maintenance.py). Every action returns the board. */

import { request, requestBlob } from "@/lib/api-client";

export type Category = "ac" | "plumbing" | "electrical" | "furniture" | "tv_wifi" | "door_lock" | "other";

export interface MaintRequest {
  id: string;
  number: string;
  unit_id: string | null;
  room_name: string | null;
  place: string | null;
  category: Category;
  urgent: boolean;
  description: string;
  status: string;
  status_note: string | null;
  reported_by_name: string | null;
  reported_at: string;
  from_housekeeping: boolean;
  assigned_staff_id: string | null;
  assigned_name: string | null;
  vendor_name: string | null;
  mine: boolean;
  has_photo: boolean;
  off_sale: { first_night: string; last_night: string } | null;
  cost: string | null;
  completed_at: string | null;
}

export interface MaintBoard {
  today: string;
  requests: MaintRequest[];
  rooms: { id: string; name: string }[];
  staff: { id: string; name: string }[];
}

export interface MaintNotice {
  id: string;
  number: string;
  room_name: string | null;
  place: string | null;
  category: Category;
  urgent: boolean;
  off_sale_until: string | null;
}

export interface NewRequest {
  unitId: string | null;
  place: string;
  category: Category;
  urgent: boolean;
  description: string;
  photo: File | null;
}

const base = "/api/maintenance";
const send = (path: string, body?: unknown) =>
  request<MaintBoard>(`${base}${path}`, {
    method: "POST",
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });

export const fetchMaintenance = () => request<MaintBoard>(base);
export function reportRepair(input: NewRequest): Promise<MaintBoard> {
  const body = new FormData();
  body.append("category", input.category);
  body.append("description", input.description.trim());
  body.append("urgent", String(input.urgent));
  if (input.unitId) body.append("unit_id", input.unitId);
  if (input.place.trim()) body.append("place", input.place.trim());
  if (input.photo) body.append("photo", input.photo);
  return request<MaintBoard>(base, { method: "POST", body });
}
export const fetchRepairPhoto = (id: string) => requestBlob(`${base}/${id}/photo`);
export const startRepair = (id: string) => send(`/${id}/start`);
export const waitRepair = (id: string, note: string) => send(`/${id}/wait`, { note });
export const fixRepair = (id: string, note: string | null, cost: number | null) =>
  send(`/${id}/fix`, { note, cost });
export const cancelRepair = (id: string, reason: string) => send(`/${id}/cancel`, { reason });
export const assignRepair = (id: string, staffId: string | null, vendorName: string | null) =>
  send(`/${id}/assign`, { staff_id: staffId, vendor_name: vendorName });
export const takeOffSale = (id: string, firstNight: string, lastNight: string) =>
  send(`/${id}/off-sale`, { first_night: firstNight, last_night: lastNight });
export const putOnSale = (id: string) => send(`/${id}/on-sale`);
