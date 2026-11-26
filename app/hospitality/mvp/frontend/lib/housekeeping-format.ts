/** Pure helpers for the rooms board, big-button mode and the staff pages. */

import { ApiError } from "@/lib/api-client";
import type { HkBoard, HkGuest, HkTask, ProblemKind } from "@/lib/housekeeping-api";
import type { StaffRole } from "@/lib/staff-api";

export const PROBLEM_KINDS: readonly ProblemKind[] = ["dnd", "refused", "repair", "empty", "other"];
export const GUEST_ONLY: readonly ProblemKind[] = ["dnd", "refused"];
export const TASK_STATUSES = [
  "pending",
  "assigned",
  "in_progress",
  "paused",
  "done",
  "inspected",
  "failed_inspection",
  "skipped_dnd",
  "refused",
] as const;
export const TASK_KINDS = ["departure_clean", "stayover_clean"] as const;
export const STAFF_ROLES: readonly StaffRole[] = ["housekeeper", "front_desk", "manager"];

const OPEN = new Set(["pending", "assigned", "in_progress", "paused", "failed_inspection"]);
const STARTABLE = new Set(["pending", "assigned", "paused", "failed_inspection"]);

export const isOpen = (task: HkTask) => OPEN.has(task.status);

/** Rooms for me: mine and nobody's, in the server's order (arrivals first). */
export function myTasks(board: HkBoard): HkTask[] {
  return board.tasks.filter((task) => task.mine || (task.assigned_staff_id === null && isOpen(task)));
}

/** The one room big-button mode shows: the first of mine still to do. */
export function nextTask(board: HkBoard): HkTask | null {
  return myTasks(board).find(isOpen) ?? null;
}

/** What the big button does next for this task. */
export function mainAction(task: HkTask): "start" | "done" | null {
  if (task.status === "in_progress") return "done";
  return STARTABLE.has(task.status) ? "start" : null;
}

/** Problems that only make sense with a guest in the room. */
export function problemsFor(task: HkTask): ProblemKind[] {
  const occupied = task.kind === "stayover_clean";
  return PROBLEM_KINDS.filter((kind) => occupied || !GUEST_ONLY.includes(kind));
}

export function guestCount(guest: HkGuest): { adults: number; children: number } {
  return { adults: guest.adults, children: guest.children };
}

export const HOUSEKEEPING_ERROR_CODES = [
  "no_staff_profile",
  "task_not_found",
  "room_not_found",
  "not_your_task",
  "task_closed",
  "not_occupied",
  "not_done_yet",
  "reason_needed",
  "unknown_staff",
  "task_exists",
  "inspect_permission",
  "clear_permission",
] as const;

export const STAFF_ERROR_CODES = [
  "invite_not_found",
  "invite_expired",
  "invite_used",
  "invite_revoked",
  "wrong_email",
  "already_member",
  "already_invited",
  "staff_not_found",
  "cannot_change_owner",
  "cannot_change_self",
  "manager_only",
] as const;

function codeOf(cause: unknown): string | null {
  if (cause instanceof ApiError && typeof cause.detail === "object" && cause.detail) {
    return (cause.detail as { code?: string }).code ?? null;
  }
  return null;
}

/** i18n key of a housekeeping refusal; null for anything else. */
export function housekeepingErrorKey(cause: unknown): string | null {
  const code = codeOf(cause);
  return code && (HOUSEKEEPING_ERROR_CODES as readonly string[]).includes(code)
    ? `hk.error.${code}`
    : null;
}

/** i18n key of a staff or join refusal; null for anything else. */
export function staffErrorKey(cause: unknown): string | null {
  const code = codeOf(cause);
  return code && (STAFF_ERROR_CODES as readonly string[]).includes(code) ? `staff.error.${code}` : null;
}

/** The link the owner sends; the token travels in the path, never a query string. */
export function joinLink(origin: string, basePath: string, token: string): string {
  return `${origin}${basePath}/join/${encodeURIComponent(token)}`;
}

/** Where a new staff member lands after joining. */
export function homeFor(role: StaffRole): string {
  return role === "housekeeper" ? "/housekeeping" : "/front-desk";
}

/** A WhatsApp message with the link, ready to send. */
export function whatsappShare(text: string): string {
  return `https://wa.me/?text=${encodeURIComponent(text)}`;
}
