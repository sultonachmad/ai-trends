"use client";

import type { HkBoard, HkTask } from "@/lib/housekeeping-api";
import { isOpen, mainAction, myTasks, nextTask } from "@/lib/housekeeping-format";
import { useLocale } from "@/lib/locale-store";

import type { TaskAction } from "./TaskCard";

/** One room at a time with three large buttons, for staff who prefer a simple screen. */
export function BigButtonView({
  board,
  busy,
  onAction,
}: {
  board: HkBoard;
  busy: boolean;
  onAction: (action: TaskAction, task: HkTask) => void;
}) {
  const { t } = useLocale();
  const task = nextTask(board);
  if (!task) {
    return (
      <p className="rounded-lg border border-border bg-card p-8 text-center text-2xl font-semibold">
        ✓ {t("hk.allDone")}
      </p>
    );
  }
  const action = mainAction(task);
  const left = myTasks(board).filter((other) => other.id !== task.id && isOpen(other)).length;
  return (
    <section aria-live="polite" className="space-y-4 rounded-lg border border-border bg-card p-5 text-center">
      <p className="text-5xl font-bold">{task.room_name}</p>
      <p className="text-lg">{t(`hk.kind.${task.kind}`)}</p>
      {task.arriving && <p className="text-lg font-semibold text-primary">{t("hk.arrivingToday")}</p>}
      {task.problem_kind && (
        <p className="text-lg text-destructive">
          {t("hk.problemShown", { kind: t(`hk.problem.${task.problem_kind}`) })}
        </p>
      )}
      {task.status === "failed_inspection" && task.notes && (
        <p className="text-lg text-destructive">{t("hk.failedNote", { reason: task.notes })}</p>
      )}
      {action && (
        <button
          type="button"
          disabled={busy}
          onClick={() => onAction(action, task)}
          className={`min-h-24 w-full rounded-xl text-3xl font-bold text-white disabled:opacity-50 ${
            action === "start" ? "bg-emerald-600" : "bg-blue-600"
          }`}
        >
          {action === "start" ? "▶ " : "✓ "}
          {t(`hk.${action}`)}
        </button>
      )}
      <button
        type="button"
        disabled={busy}
        onClick={() => onAction("problem", task)}
        className="min-h-20 w-full rounded-xl bg-amber-500 text-2xl font-bold text-black disabled:opacity-50"
      >
        ⚠ {t("hk.problem")}
      </button>
      {left > 0 && <p className="text-muted-foreground">{t("hk.more", { count: left })}</p>}
    </section>
  );
}
