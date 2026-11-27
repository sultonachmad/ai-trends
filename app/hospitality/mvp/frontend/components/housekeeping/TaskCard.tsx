"use client";

import Link from "next/link";

import { shortDate } from "@/lib/booking-format";
import type { HkTask } from "@/lib/housekeeping-api";
import { isOpen, mainAction } from "@/lib/housekeeping-format";
import { useLocale } from "@/lib/locale-store";

export type TaskAction = "start" | "done" | "take" | "problem" | "pass" | "fail";

const button = "min-h-12 rounded-md px-4 py-2 text-sm font-medium disabled:opacity-50";

function statusClass(task: HkTask): string {
  if (task.problem_kind || task.status === "failed_inspection") return "bg-destructive/15 text-destructive";
  if (task.status === "in_progress") return "bg-accent text-accent-foreground";
  if (isOpen(task)) return "bg-muted";
  return "bg-primary/15 text-primary";
}

/** One room to clean: who is arriving or staying, and what to do now. */
export function TaskCard({
  task,
  canWork,
  canInspect,
  busy,
  onAction,
}: {
  task: HkTask;
  canWork: boolean;
  canInspect: boolean;
  busy: boolean;
  onAction: (action: TaskAction, task: HkTask) => void;
}) {
  const { t, locale } = useLocale();
  const next = mainAction(task);
  const free = task.assigned_staff_id === null;
  const guest = task.arriving ?? task.staying;
  return (
    <li className="space-y-2 rounded-lg border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xl font-bold">{task.room_name}</p>
          <p className="text-sm text-muted-foreground">{t(`hk.kind.${task.kind}`)}</p>
        </div>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusClass(task)}`}>
          {t(`hk.status.${task.status}`)}
        </span>
      </div>
      {task.arriving && (
        <p className="text-sm font-semibold text-primary">
          {task.arriving.eta
            ? t("hk.arrivingAt", { time: task.arriving.eta.slice(0, 5) })
            : t("hk.arrivingToday")}
        </p>
      )}
      {guest && (
        <div className="text-sm">
          {task.staying && !task.arriving && (
            <p>{t("hk.staying", { name: guest.name, date: shortDate(guest.departure, locale) })}</p>
          )}
          <p className="text-muted-foreground">
            {t("hk.guests", { adults: guest.adults, children: guest.children })}
          </p>
          {guest.special_requests && <p>{t("hk.requests", { text: guest.special_requests })}</p>}
        </div>
      )}
      <p className="text-xs text-muted-foreground">
        {task.assigned_name ? t("hk.assignedTo", { name: task.assigned_name }) : t("hk.free")}
      </p>
      {task.problem_kind && (
        <p className="text-sm text-destructive">
          {t("hk.problemShown", { kind: t(`hk.problem.${task.problem_kind}`) })}
          {task.problem_note && ` — ${task.problem_note}`}
          {task.problem_kind === "repair" && (
            <Link href="/maintenance" className="ml-2 underline">
              {t("repair.title")}
            </Link>
          )}
        </p>
      )}
      {task.status === "failed_inspection" && task.notes && (
        <p className="text-sm text-destructive">{t("hk.failedNote", { reason: task.notes })}</p>
      )}
      {task.awaiting_inspection && (
        <p className="text-sm text-muted-foreground">{t("hk.waitsInspection")}</p>
      )}
      <div className="flex flex-wrap gap-2">
        {canWork && free && isOpen(task) && (
          <button type="button" disabled={busy} onClick={() => onAction("take", task)} className={`${button} border border-border hover:bg-accent`}>
            {t("hk.take")}
          </button>
        )}
        {canWork && next && (task.mine || free || canInspect) && (
          <button type="button" disabled={busy} onClick={() => onAction(next, task)} className={`${button} bg-primary text-primary-foreground`}>
            {t(`hk.${next}`)}
          </button>
        )}
        {canWork && isOpen(task) && (task.mine || free || canInspect) && (
          <button type="button" disabled={busy} onClick={() => onAction("problem", task)} className={`${button} border border-border hover:bg-accent`}>
            {t("hk.problem")}
          </button>
        )}
        {canInspect && task.awaiting_inspection && (
          <>
            <button type="button" disabled={busy} onClick={() => onAction("pass", task)} className={`${button} bg-primary text-primary-foreground`}>
              {t("hk.inspect.pass")}
            </button>
            <button type="button" disabled={busy} onClick={() => onAction("fail", task)} className={`${button} border border-destructive text-destructive`}>
              {t("hk.inspect.fail")}
            </button>
          </>
        )}
      </div>
    </li>
  );
}
