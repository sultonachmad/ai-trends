"use client";

import { useEffect, useState } from "react";

import { Dialog } from "@/components/Dialog";
import { useLocale } from "@/lib/locale-store";
import { parseCost } from "@/lib/maintenance-format";

export type NoteMode = "wait" | "fix" | "cancel";

const field = "min-h-12 w-full rounded-md border border-border bg-background px-3 py-2 text-base";
const LABEL: Record<NoteMode, string> = {
  wait: "repair.waitNote",
  fix: "repair.fixNote",
  cancel: "repair.cancelReason",
};

/** A short note for a step: why it waits, what was done (with a cost), why cancelled. */
export function NoteDialog({
  mode,
  busy,
  onClose,
  onSend,
}: {
  mode: NoteMode | null;
  busy: boolean;
  onClose: () => void;
  onSend: (note: string | null, cost: number | null) => void;
}) {
  const { t } = useLocale();
  const [note, setNote] = useState("");
  const [cost, setCost] = useState("");
  useEffect(() => {
    setNote("");
    setCost("");
  }, [mode]);
  if (!mode) return null;
  const needsNote = mode !== "fix";
  const parsed = parseCost(cost);
  const costBad = parsed !== null && Number.isNaN(parsed);
  const ready = (!needsNote || note.trim().length > 0) && !costBad;
  return (
    <Dialog open onClose={onClose} title={t(mode === "cancel" ? "repair.cancel" : `repair.step.${mode}`)}>
      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          if (ready) onSend(note.trim() || null, mode === "fix" ? parsed : null);
        }}
      >
        <label className="block space-y-1 text-sm">
          <span>{t(LABEL[mode])}</span>
          <textarea
            value={note}
            maxLength={300}
            rows={2}
            required={needsNote}
            onChange={(e) => setNote(e.target.value)}
            className={field}
          />
        </label>
        {mode === "fix" && (
          <label className="block space-y-1 text-sm">
            <span>{t("repair.cost")}</span>
            <input inputMode="numeric" value={cost} onChange={(e) => setCost(e.target.value)} className={field} />
            {costBad && <span className="text-destructive">{t("repair.costBad")}</span>}
          </label>
        )}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="min-h-12 rounded-md border border-border px-4">
            {t("hk.cancel")}
          </button>
          <button
            type="submit"
            disabled={!ready || busy}
            className="min-h-12 rounded-md bg-primary px-4 font-medium text-primary-foreground disabled:opacity-50"
          >
            {t("repair.save")}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
