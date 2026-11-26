"use client";

import { useEffect, useState } from "react";

import type { HkBoard } from "@/lib/housekeeping-api";
import { isOpen } from "@/lib/housekeeping-format";
import { useLocale } from "@/lib/locale-store";

const field = "min-h-11 rounded-md border border-border bg-background px-3 py-2 text-sm";
const action = "min-h-11 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50";

/** For supervisors: who cleans which room, sharing free rooms, and the rules. */
export function PlanView({
  board,
  busy,
  onAssign,
  onSplit,
  onSettings,
}: {
  board: HkBoard;
  busy: boolean;
  onAssign: (taskId: string, staffId: string | null) => void;
  onSplit: (staffIds: string[]) => void;
  onSettings: (readyWhen: string, stayover: string) => void;
}) {
  const { t } = useLocale();
  const [chosen, setChosen] = useState<string[]>([]);
  const [readyWhen, setReadyWhen] = useState<string>(board.ready_when);
  const [stayover, setStayover] = useState<string>(board.stayover);
  useEffect(() => {
    setReadyWhen(board.ready_when);
    setStayover(board.stayover);
  }, [board.ready_when, board.stayover]);

  const open = board.tasks.filter(isOpen);
  const free = open.filter((task) => task.assigned_staff_id === null).length;
  const toggle = (id: string) =>
    setChosen((current) => (current.includes(id) ? current.filter((x) => x !== id) : [...current, id]));
  return (
    <div className="space-y-4">
      <section aria-labelledby="hk-split" className="space-y-2 rounded-lg border border-border bg-card p-4">
        <h2 id="hk-split" className="font-semibold">{t("hk.plan.free", { count: free })}</h2>
        <fieldset className="flex flex-wrap gap-3">
          <legend className="mb-1 text-sm">{t("hk.plan.splitWho")}</legend>
          {board.staff.map((member) => (
            <label key={member.id} className="flex min-h-11 items-center gap-2 text-sm">
              <input type="checkbox" checked={chosen.includes(member.id)} onChange={() => toggle(member.id)} className="h-5 w-5" />
              {member.name}
            </label>
          ))}
        </fieldset>
        <button type="button" disabled={busy || free === 0 || chosen.length === 0} onClick={() => onSplit(chosen)} className={action}>
          {t("hk.plan.split")}
        </button>
      </section>
      <ul className="space-y-2">
        {open.map((task) => (
          <li key={task.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-card p-3">
            <span className="font-medium">
              {task.room_name} · <span className="text-sm text-muted-foreground">{t(`hk.kind.${task.kind}`)}</span>
            </span>
            <label className="flex items-center gap-2 text-sm">
              <span className="sr-only">{t("hk.plan.assign", { room: task.room_name })}</span>
              <select
                value={task.assigned_staff_id ?? ""}
                disabled={busy}
                onChange={(event) => onAssign(task.id, event.target.value || null)}
                className={field}
              >
                <option value="">{t("hk.plan.nobody")}</option>
                {board.staff.map((member) => (
                  <option key={member.id} value={member.id}>{member.name}</option>
                ))}
              </select>
            </label>
          </li>
        ))}
      </ul>
      <form
        aria-labelledby="hk-rules"
        className="space-y-3 rounded-lg border border-border bg-card p-4"
        onSubmit={(event) => {
          event.preventDefault();
          onSettings(readyWhen, stayover);
        }}
      >
        <h2 id="hk-rules" className="font-semibold">{t("hk.settings.title")}</h2>
        <label className="block space-y-1 text-sm">
          <span>{t("hk.settings.readyWhen")}</span>
          <select value={readyWhen} onChange={(event) => setReadyWhen(event.target.value)} className={`${field} w-full`}>
            <option value="clean">{t("hk.settings.ready.clean")}</option>
            <option value="inspected">{t("hk.settings.ready.inspected")}</option>
          </select>
        </label>
        <label className="block space-y-1 text-sm">
          <span>{t("hk.settings.stayover")}</span>
          <select value={stayover} onChange={(event) => setStayover(event.target.value)} className={`${field} w-full`}>
            <option value="daily">{t("hk.settings.stayover.daily")}</option>
            <option value="on_request">{t("hk.settings.stayover.on_request")}</option>
          </select>
        </label>
        <button type="submit" disabled={busy} className={action}>{t("hk.settings.save")}</button>
      </form>
    </div>
  );
}
