"use client";

/** Rooms to clean — phone-first: my rooms in order, all rooms, and the supervisor's plan. */

import { useCallback, useRef, useState } from "react";

import { AllRooms, type RoomAction } from "@/components/housekeeping/AllRooms";
import { BigButtonView } from "@/components/housekeeping/BigButtonView";
import { PlanView } from "@/components/housekeeping/PlanView";
import { ReasonDialog } from "@/components/housekeeping/ReasonDialog";
import { TaskCard, type TaskAction } from "@/components/housekeeping/TaskCard";
import { LanguageSwitch } from "@/components/LanguageSwitch";
import { ApiError } from "@/lib/api-client";
import { shortDate } from "@/lib/booking-format";
import {
  assignTask,
  fetchBoard,
  finishTask,
  inspectTask,
  reportProblem,
  requestClean,
  saveHkSettings,
  setBigButtons,
  setRoomStatus,
  splitEvenly,
  startTask,
  takeTask,
  type HkBoard,
  type HkRoom,
  type HkTask,
} from "@/lib/housekeeping-api";
import { housekeepingErrorKey, myTasks } from "@/lib/housekeeping-format";
import { useLocale } from "@/lib/locale-store";
import { useCan } from "@/lib/rbac-store";
import { usePolling } from "@/lib/use-polling";

type Tab = "mine" | "all" | "plan";
type Problem = { key: string } | { text: string };
const FORBIDDEN = 403;
const STALE = new Set(["hk.error.task_not_found", "hk.error.task_closed", "hk.error.not_your_task"]);

function problemOf(cause: unknown): Problem {
  const key = housekeepingErrorKey(cause);
  return key ? { key } : { text: cause instanceof Error ? cause.message : String(cause) };
}

export default function HousekeepingPage() {
  const { t, locale } = useLocale();
  const canEdit = useCan("housekeeping:edit");
  const canManage = useCan("housekeeping:manage");
  const [board, setBoard] = useState<HkBoard | null>(null);
  const [tab, setTab] = useState<Tab>("mine");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [asking, setAsking] = useState<{ task: HkTask; mode: "problem" | "fail" } | null>(null);
  const [noAccess, setNoAccess] = useState(false);
  const requestId = useRef(0);

  const load = useCallback(async () => {
    const id = ++requestId.current;
    try {
      const found = await fetchBoard();
      if (id === requestId.current) setBoard(found);
    } catch (cause) {
      if (id !== requestId.current) return;
      if (cause instanceof ApiError && cause.status === FORBIDDEN) setNoAccess(true);
      else setProblem({ key: "hk.loadError" });
    }
  }, []);

  // Loads at once, then every few seconds while the page is visible (and not mid-action).
  usePolling(load, (board?.poll_seconds ?? 15) * 1000, !busy && asking === null);

  const run = async (call: () => Promise<HkBoard>, saved?: string) => {
    setBusy(true);
    setNotice(null);
    requestId.current += 1; // a refresh already on its way must not undo this answer
    try {
      setBoard(await call());
      setProblem(null);
      if (saved) setNotice(saved);
    } catch (cause) {
      const found = problemOf(cause);
      setProblem(found);
      if ("key" in found && STALE.has(found.key)) void load(); // the list changed meanwhile
    } finally {
      setBusy(false);
    }
  };

  const onTask = (action: TaskAction, task: HkTask) => {
    if (action === "problem" || action === "fail") {
      setAsking({ task, mode: action });
      return;
    }
    const calls: Record<Exclude<TaskAction, "problem" | "fail">, () => Promise<HkBoard>> = {
      start: () => startTask(task.id),
      done: () => finishTask(task.id),
      take: () => takeTask(task.id),
      pass: () => inspectTask(task.id, true, null),
    };
    void run(calls[action]);
  };
  const onRoom = (action: RoomAction, room: HkRoom) =>
    void run(() => (action === "request" ? requestClean(room.id) : setRoomStatus(room.id, action)));

  if (noAccess) return <p role="alert" className="p-8 text-sm">{t("frontdesk.noAccess")}</p>;
  const tabs: Tab[] = canManage ? ["mine", "all", "plan"] : ["mine", "all"];
  const mine = board ? myTasks(board) : [];
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{t("hk.title")}</h1>
          {board && <p className="text-sm text-muted-foreground">{t("hk.today", { date: shortDate(board.date, locale) })}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {board?.my_staff_id && (
            <button
              type="button"
              role="switch"
              aria-checked={board.big_buttons}
              disabled={busy}
              onClick={() => void run(() => setBigButtons(!board.big_buttons))}
              className={`min-h-11 rounded-full border px-4 py-2 text-sm font-medium ${
                board.big_buttons ? "border-primary bg-primary text-primary-foreground" : "border-border"
              }`}
            >
              {t("hk.bigButtons")}
            </button>
          )}
          <LanguageSwitch />
        </div>
      </div>
      {problem && (
        <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {"key" in problem ? t(problem.key) : problem.text}
        </p>
      )}
      {notice && <p role="status" className="text-sm text-primary">{notice}</p>}
      <div role="tablist" aria-label={t("hk.title")} className="flex flex-wrap gap-2">
        {tabs.map((name) => (
          <button
            key={name}
            type="button"
            role="tab"
            aria-selected={tab === name}
            onClick={() => setTab(name)}
            className={`min-h-11 rounded-md border px-4 py-2 text-sm ${
              tab === name ? "border-primary bg-primary text-primary-foreground" : "border-border hover:bg-accent"
            }`}
          >
            {t(`hk.tab.${name}`)}
            {name === "mine" && board && ` (${mine.length})`}
          </button>
        ))}
      </div>
      {!board ? (
        <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
      ) : tab === "mine" && board.big_buttons ? (
        <BigButtonView board={board} busy={busy} onAction={onTask} />
      ) : tab === "mine" ? (
        mine.length === 0 ? (
          <p className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">{t("hk.none")}</p>
        ) : (
          <ul className="space-y-3">
            {mine.map((task) => (
              <TaskCard key={task.id} task={task} canWork={canEdit} canInspect={canManage} busy={busy} onAction={onTask} />
            ))}
          </ul>
        )
      ) : tab === "all" ? (
        <AllRooms board={board} canEdit={canEdit} canManage={canManage} busy={busy} onAction={onRoom} />
      ) : (
        <div className="space-y-4">
          <ul className="space-y-3">
            {board.tasks
              .filter((task) => task.awaiting_inspection)
              .map((task) => (
                <TaskCard key={task.id} task={task} canWork={canEdit} canInspect busy={busy} onAction={onTask} />
              ))}
          </ul>
          <PlanView
            board={board}
            busy={busy}
            onAssign={(taskId, staffId) => void run(() => assignTask(taskId, staffId))}
            onSplit={(staffIds) => void run(() => splitEvenly(staffIds))}
            onSettings={(readyWhen, stayover) =>
              void run(() => saveHkSettings(readyWhen, stayover), t("hk.settings.saved"))
            }
          />
        </div>
      )}
      <ReasonDialog
        task={asking?.task ?? null}
        mode={asking?.mode ?? "problem"}
        busy={busy}
        onClose={() => setAsking(null)}
        onSend={(task, note, kind) => {
          const mode = asking?.mode;
          setAsking(null);
          void run(() =>
            mode === "fail" ? inspectTask(task.id, false, note) : reportProblem(task.id, kind ?? "other", note),
          );
        }}
      />
    </div>
  );
}
