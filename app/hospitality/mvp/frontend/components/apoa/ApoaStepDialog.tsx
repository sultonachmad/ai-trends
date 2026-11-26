"use client";

import { useEffect, useState } from "react";

import type { ApoaAction } from "@/components/apoa/ApoaCard";
import { Dialog } from "@/components/Dialog";
import { inputClass } from "@/components/rooms/RoomTypeDialog";
import {
  apoaNotRequired,
  markApoa,
  undoApoa,
  type ApoaItem,
  type ApoaList,
  type ApoaStep,
} from "@/lib/apoa-api";
import { apoaErrorKey, checkReason, checkReference } from "@/lib/apoa-format";
import { useLocale } from "@/lib/locale-store";

export type StepTarget = { item: ApoaItem; action: ApoaAction; step: ApoaStep } | null;

interface ApoaStepDialogProps {
  target: StepTarget;
  onClose: () => void;
  onDone: (list: ApoaList) => void;
}

const secondary =
  "min-h-11 rounded-md border border-border px-4 py-2 text-sm hover:bg-accent disabled:opacity-50";
const primary =
  "min-h-11 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50";
const TITLE: Record<ApoaAction, string> = {
  mark: "apoa.confirm.mark.title",
  not_required: "apoa.confirm.notRequired.title",
  undo: "apoa.confirm.undo.title",
};

/** Record an APOA step, skip it with a reason, or take a record back with a reason. */
export function ApoaStepDialog({ target, onClose, onDone }: ApoaStepDialogProps) {
  const { t } = useLocale();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setText("");
    setError(null);
  }, [target]);

  if (!target) return <Dialog open={false} onClose={onClose}>{null}</Dialog>;
  const { item, action, step } = target;
  const input = { booking_id: item.booking_id, guest_id: item.guest_id, step };

  /** The call to make, or the i18n key of what is wrong with the text. */
  const request = (): Promise<ApoaList> | string => {
    if (action === "mark") {
      const reference = checkReference(text);
      return reference.ok ? markApoa(input, reference.value) : reference.key;
    }
    const reason = checkReason(text);
    if (!reason.ok) return reason.key;
    return action === "undo" ? undoApoa(input, reason.value) : apoaNotRequired(input, reason.value);
  };

  const submit = async () => {
    const call = request();
    if (typeof call === "string") {
      setError(t(call));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      onDone(await call);
    } catch (cause) {
      const key = apoaErrorKey(cause);
      setError(key ? t(key) : cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  };

  const stepLabel = t(`apoa.step.${step}`);
  return (
    <Dialog open onClose={() => !busy && onClose()} title={t(TITLE[action], { step: stepLabel })}>
      <div className="space-y-3 text-sm">
        {action === "mark" && <p>{t("apoa.confirm.mark.body", { guest: item.full_name })}</p>}
        <div>
          <label htmlFor="apoa-step-text" className="mb-1 block font-medium">
            {t(action === "mark" ? "apoa.confirm.referenceLabel" : "apoa.confirm.reasonLabel")}
          </label>
          <input
            id="apoa-step-text"
            value={text}
            maxLength={action === "mark" ? 80 : 300}
            onChange={(event) => setText(event.target.value)}
            className={inputClass}
          />
        </div>
        {error && (
          <p role="alert" className="text-destructive">
            {error}
          </p>
        )}
      </div>
      <div className="mt-4 flex flex-wrap justify-end gap-2">
        <button type="button" disabled={busy} onClick={onClose} className={secondary}>
          {t("frontdesk.back")}
        </button>
        <button type="button" disabled={busy} onClick={() => void submit()} className={primary}>
          {t("apoa.confirm.save")}
        </button>
      </div>
    </Dialog>
  );
}
