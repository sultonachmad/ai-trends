import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api-client";
import type { HkBoard, HkTask } from "@/lib/housekeeping-api";
import {
  HOUSEKEEPING_ERROR_CODES,
  PROBLEM_KINDS,
  STAFF_ERROR_CODES,
  STAFF_ROLES,
  TASK_KINDS,
  TASK_STATUSES,
  homeFor,
  housekeepingErrorKey,
  joinLink,
  mainAction,
  myTasks,
  nextTask,
  problemsFor,
  staffErrorKey,
  whatsappShare,
} from "@/lib/housekeeping-format";
import { translate } from "@/lib/i18n";

const task = (overrides: Partial<HkTask> = {}): HkTask => ({
  id: "t1",
  unit_id: "u1",
  room_name: "101",
  room_type: "Deluxe",
  kind: "departure_clean",
  status: "pending",
  priority: "normal",
  assigned_staff_id: null,
  assigned_name: null,
  mine: false,
  arriving: null,
  staying: null,
  started_at: null,
  completed_at: null,
  awaiting_inspection: false,
  inspection_result: null,
  notes: null,
  problem_kind: null,
  problem_note: null,
  problem_at: null,
  ...overrides,
});

const board = (tasks: HkTask[]): HkBoard => ({
  date: "2026-11-26",
  tasks,
  rooms: [],
  staff: [],
  my_staff_id: "me",
  big_buttons: false,
  ready_when: "clean",
  stayover: "daily",
  poll_seconds: 15,
});

describe("my rooms", () => {
  it("keeps mine and nobody's open rooms, in the server's order", () => {
    const mine = task({ id: "a", mine: true, assigned_staff_id: "me" });
    const free = task({ id: "b" });
    const theirs = task({ id: "c", assigned_staff_id: "other" });
    const freeDone = task({ id: "d", status: "done" });
    expect(myTasks(board([mine, theirs, free, freeDone])).map((t) => t.id)).toEqual(["a", "b"]);
  });

  it("big-button mode shows the first room still to do", () => {
    const done = task({ id: "a", mine: true, assigned_staff_id: "me", status: "done" });
    const next = task({ id: "b", mine: true, assigned_staff_id: "me" });
    expect(nextTask(board([done, next]))?.id).toBe("b");
    expect(nextTask(board([done]))).toBeNull();
  });
});

describe("the big button", () => {
  it("starts, then finishes, and offers nothing once done", () => {
    expect(mainAction(task())).toBe("start");
    expect(mainAction(task({ status: "failed_inspection" }))).toBe("start");
    expect(mainAction(task({ status: "in_progress" }))).toBe("done");
    expect(mainAction(task({ status: "done" }))).toBeNull();
    expect(mainAction(task({ status: "skipped_dnd" }))).toBeNull();
  });

  it("offers do not disturb and refused only for rooms with a guest", () => {
    expect(problemsFor(task())).not.toContain("dnd");
    expect(problemsFor(task({ kind: "stayover_clean" }))).toEqual([...PROBLEM_KINDS]);
  });
});

describe("refusals", () => {
  it("maps housekeeping and staff codes to text, and nothing else", () => {
    const refusal = (code: string) => new ApiError(409, "x", { code, message: "x" });
    expect(housekeepingErrorKey(refusal("not_your_task"))).toBe("hk.error.not_your_task");
    expect(housekeepingErrorKey(refusal("invite_used"))).toBeNull();
    expect(staffErrorKey(refusal("invite_used"))).toBe("staff.error.invite_used");
    expect(staffErrorKey(new Error("x"))).toBeNull();
  });
});

describe("join links", () => {
  it("puts the token in the path and sends people to their page", () => {
    expect(joinLink("https://app.example", "/hotel", "a_b-c")).toBe("https://app.example/hotel/join/a_b-c");
    expect(homeFor("housekeeper")).toBe("/housekeeping");
    expect(homeFor("front_desk")).toBe("/front-desk");
    expect(whatsappShare("Join: https://x/join/t")).toBe("https://wa.me/?text=Join%3A%20https%3A%2F%2Fx%2Fjoin%2Ft");
  });
});

describe("text", () => {
  it("has Indonesian and English for every status, kind, problem, role and refusal", () => {
    const keys = [
      ...TASK_STATUSES.map((s) => `hk.status.${s}`),
      ...TASK_KINDS.map((k) => `hk.kind.${k}`),
      ...PROBLEM_KINDS.map((p) => `hk.problem.${p}`),
      ...STAFF_ROLES.map((r) => `staff.role.${r}`),
      "staff.role.custom",
      ...HOUSEKEEPING_ERROR_CODES.map((c) => `hk.error.${c}`),
      ...STAFF_ERROR_CODES.map((c) => `staff.error.${c}`),
    ];
    for (const locale of ["id", "en"] as const) {
      for (const key of keys) {
        expect(translate(locale, key), `${locale} ${key}`).not.toBe(key);
      }
    }
  });
});
