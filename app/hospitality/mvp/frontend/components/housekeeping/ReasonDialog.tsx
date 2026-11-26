"use client";

import { useEffect, useState } from "react";

import { Dialog } from "@/components/Dialog";
import type { HkTask, ProblemKind } from "@/lib/housekeeping-api";
import { problemsFor } from "@/lib/housekeeping-format";
import { useLocale } from "@/lib/locale-store";

const MAX_NOTE = 300;

/**
 * Asks why: the problem in a room (`mode="problem"`, big tap targets, a note is optional)
 * or why a room failed inspection (`mode="fail"`, the reason is required).
 */
export function ReasonDialog({
  task,
  mode,
  busy,
  onClose,
  onSend,
}: {
  task: HkTask | null;
  mode: "problem" | "fail";
  busy: boolean;
  onClose: () => void;
  onSend: (task: HkTask, note: string | null, kind: ProblemKind | null) => void;
}) {
  const { t } = useLocale();
  const [kind, setKind] = useState<ProblemKind | null>(null);
  const [note, setNote] = useState("");

  useEffect(() => {
    setKind(null);
    setNote("");
  }, [task, mode]);

  if (!task) return null;
  const trimmed = note.trim();
  const ready = mode === "problem" ? kind !== null : trimmed.length > 0;
  const title =
    mode === "problem" ? t("hk.problemTitle", { room: task.room_name }) : t("hk.inspect.reason");
  return (
    <Dialog open onClose={onClose} title={title}>
      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          if (ready) onSend(task, trimmed || null, kind);
        }}
      >
        {mode === "problem" && (
          <fieldset className="grid gap-2">
            <legend className="sr-only">{title}</legend>
            {problemsFor(task).map((option) => (
              <label
                key={option}
                className={`flex min-h-12 cursor-pointer items-center gap-3 rounded-md border px-3 text-base ${
                  kind === option ? "border-primary bg-primary/10" : "border-border"
                }`}
              >
                <input
                  type="radio"
                  name="problem"
                  value={option}
                  checked={kind === option}
                  onChange={() => setKind(option)}
                  className="h-5 w-5"
                />
                {t(`hk.problem.${option}`)}
              </label>
            ))}
          </fieldset>
        )}
        <label className="block space-y-1 text-sm">
          <span>{mode === "problem" ? t("hk.problemNote") : t("hk.inspect.reason")}</span>
          <textarea
            value={note}
            maxLength={MAX_NOTE}
            rows={2}
            required={mode === "fail"}
            onChange={(event) => setNote(event.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-base"
          />
        </label>
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="min-h-12 rounded-md border border-border px-4">
            {t("hk.cancel")}
          </button>
          <button
            type="submit"
            disabled={!ready || busy}
            className="min-h-12 rounded-md bg-primary px-4 font-medium text-primary-foreground disabled:opacity-50"
          >
            {t("hk.send")}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
