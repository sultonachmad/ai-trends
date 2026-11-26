/** Rooms to clean (backend: app/routers/housekeeping.py). Every action returns the board. */

import { request } from "@/lib/api-client";

export type ProblemKind = "dnd" | "refused" | "repair" | "empty" | "other";

export interface HkGuest {
  name: string;
  adults: number;
  children: number;
  arrival: string;
  departure: string;
  eta: string | null;
  special_requests: string | null;
}

export interface HkTask {
  id: string;
  unit_id: string;
  room_name: string;
  room_type: string;
  kind: string;
  status: string;
  priority: string;
  assigned_staff_id: string | null;
  assigned_name: string | null;
  mine: boolean;
  arriving: HkGuest | null;
  staying: HkGuest | null;
  started_at: string | null;
  completed_at: string | null;
  awaiting_inspection: boolean;
  inspection_result: string | null;
  notes: string | null;
  problem_kind: ProblemKind | null;
  problem_note: string | null;
  problem_at: string | null;
}

export interface HkRoom {
  id: string;
  name: string;
  room_type: string;
  hk_status: string;
  fo_status: string;
  service_status: string;
  arrival_today: boolean;
  task_id: string | null;
  task_status: string | null;
  assigned_name: string | null;
}

export interface HkBoard {
  date: string;
  tasks: HkTask[];
  rooms: HkRoom[];
  staff: { id: string; name: string }[];
  my_staff_id: string | null;
  big_buttons: boolean;
  ready_when: "clean" | "inspected";
  stayover: "daily" | "on_request";
  poll_seconds: number;
}

export interface HkProblem {
  task_id: string;
  unit_id: string;
  room_name: string;
  kind: ProblemKind;
  note: string | null;
  at: string;
  by_name: string | null;
}

const base = "/api/housekeeping";
const send = (path: string, method: string, body?: unknown) =>
  request<HkBoard>(`${base}${path}`, {
    method,
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });

export const fetchBoard = () => request<HkBoard>(`${base}/board`);
export const startTask = (id: string) => send(`/tasks/${id}/start`, "POST");
export const finishTask = (id: string) => send(`/tasks/${id}/done`, "POST");
export const takeTask = (id: string) => send(`/tasks/${id}/take`, "POST");
export const reportProblem = (id: string, kind: ProblemKind, note: string | null) =>
  send(`/tasks/${id}/problem`, "POST", { kind, note });
export const clearProblem = (id: string) => send(`/tasks/${id}/clear-problem`, "POST");
export const assignTask = (id: string, staffId: string | null) =>
  send(`/tasks/${id}/assign`, "POST", { staff_id: staffId });
export const inspectTask = (id: string, passed: boolean, reason: string | null) =>
  send(`/tasks/${id}/inspect`, "POST", { passed, reason });
export const splitEvenly = (staffIds: string[]) => send("/split", "POST", { staff_ids: staffIds });
export const setRoomStatus = (unitId: string, hkStatus: "dirty" | "clean" | "inspected") =>
  send(`/rooms/${unitId}/status`, "PUT", { hk_status: hkStatus });
export const requestClean = (unitId: string) => send(`/rooms/${unitId}/clean-request`, "POST");
export const saveHkSettings = (readyWhen: string, stayover: string) =>
  send("/settings", "PUT", { ready_when: readyWhen, stayover });
export const setBigButtons = (on: boolean) => send("/me/mode", "PUT", { big_buttons: on });
