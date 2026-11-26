"use client";

import type { HkProblem } from "@/lib/housekeeping-api";
import { useLocale } from "@/lib/locale-store";

/** Problems housekeepers reported, until someone at the desk has dealt with them. */
export function HousekeepingProblems({
  problems,
  busy,
  onDone,
}: {
  problems: HkProblem[];
  busy: boolean;
  /** Given when the person may mark a problem as dealt with. */
  onDone?: (problem: HkProblem) => void;
}) {
  const { t, locale } = useLocale();
  if (problems.length === 0) return null;
  const time = (iso: string) =>
    new Date(iso).toLocaleTimeString(locale === "id" ? "id-ID" : "en-GB", { hour: "2-digit", minute: "2-digit" });
  return (
    <section aria-labelledby="desk-hk-problems" className="space-y-2 rounded-lg bg-destructive/10 p-3 text-sm">
      <h2 id="desk-hk-problems" className="font-semibold text-destructive">
        {t("frontdesk.problems.title")}
      </h2>
      <ul className="space-y-2">
        {problems.map((problem) => (
          <li key={problem.task_id} className="flex flex-wrap items-center justify-between gap-2">
            <span>
              {t("frontdesk.problems.line", { room: problem.room_name, kind: t(`hk.problem.${problem.kind}`) })}
              {problem.note && ` — ${problem.note}`}
              <span className="block text-xs text-muted-foreground">
                {time(problem.at)}
                {problem.by_name && ` · ${t("frontdesk.problems.by", { name: problem.by_name })}`}
              </span>
            </span>
            {onDone && (
              <button
                type="button"
                disabled={busy}
                onClick={() => onDone(problem)}
                className="min-h-11 rounded-md border border-current px-3 py-1 font-medium disabled:opacity-50"
              >
                {t("frontdesk.problems.gotIt")}
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
