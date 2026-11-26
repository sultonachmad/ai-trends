"use client";

import { useState } from "react";

import { dueLabel, apoaErrorKey } from "@/lib/apoa-format";
import type { ApoaItem, ApoaStep, StepState } from "@/lib/apoa-api";
import { fetchIdImage } from "@/lib/guest-ids-api";
import { formatClock, formatShortDate } from "@/lib/inbox-format";
import { useLocale } from "@/lib/locale-store";

export type ApoaAction = "mark" | "not_required" | "undo";

interface ApoaCardProps {
  item: ApoaItem;
  canEdit: boolean;
  /** May download the passport photo (guestid:edit). */
  canSeePhoto: boolean;
  onAction: (item: ApoaItem, action: ApoaAction, step: ApoaStep) => void;
}

const secondary =
  "min-h-11 rounded-md border border-border px-3 py-2 text-sm hover:bg-accent disabled:opacity-50";
const primary =
  "min-h-11 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90";
const EXTENSION: Record<string, string> = { "image/png": "png", "image/webp": "webp" };

function StepLine({ step, state }: { step: ApoaStep; state: StepState }) {
  const { t, locale } = useLocale();
  if (state.status === "pending") return null;
  const label = t(`apoa.step.${step}`);
  const when = state.at ? `${formatShortDate(state.at, locale)} ${formatClock(state.at, locale)}` : "";
  return (
    <p className="text-xs text-muted-foreground">
      {state.status === "submitted"
        ? t("apoa.state.submitted", { step: label, by: state.by ?? "-", when })
        : t("apoa.state.not_required", { step: label, reason: state.reason ?? "" })}
      {state.reference && ` · ${t("apoa.reference", { reference: state.reference })}`}
    </p>
  );
}

/** One foreign guest on one stay, and the APOA steps due or done. */
export function ApoaCard({ item, canEdit, canSeePhoto, onAction }: ApoaCardProps) {
  const { t, locale } = useLocale();
  const [error, setError] = useState<string | null>(null);
  const due = dueLabel(item.due_at);
  const when = (iso: string) => `${formatShortDate(iso, locale)} ${formatClock(iso, locale)}`;
  const lastDone: ApoaStep | null =
    item.departure.status !== "pending" ? "departure" : item.arrival.status !== "pending" ? "arrival" : null;

  const downloadPhoto = async () => {
    setError(null);
    try {
      const blob = await fetchIdImage(item.booking_id, item.document_id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `passport-${item.booking_number}.${EXTENSION[blob.type] ?? "jpg"}`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (cause) {
      const key = apoaErrorKey(cause);
      setError(key ? t(key) : cause instanceof Error ? cause.message : String(cause));
    }
  };

  return (
    <li
      className={`space-y-2 rounded-lg border bg-card p-3 ${item.overdue ? "border-destructive" : "border-border"}`}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-semibold">
          {item.full_name} <span className="font-normal text-muted-foreground">· {item.nationality}</span>
        </p>
        {due && (
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              item.overdue ? "bg-destructive text-destructive-foreground" : "bg-accent text-accent-foreground"
            }`}
          >
            {t(due.key, { hours: due.hours })}
          </span>
        )}
      </div>
      <p className="text-sm">
        <span className="font-mono">{item.masked_number ?? "-"}</span>
        {item.visa_type && ` · ${t(`guestid.visa.${item.visa_type}`)}`}
        {item.room && ` · ${t("apoa.room", { room: item.room })}`} · {item.booking_number}
      </p>
      <p className="text-xs text-muted-foreground">
        {t("apoa.checkedIn", { when: when(item.checked_in_at) })}
        {item.checked_out_at && ` · ${t("apoa.checkedOut", { when: when(item.checked_out_at) })}`}
      </p>
      <StepLine step="arrival" state={item.arrival} />
      <StepLine step="departure" state={item.departure} />
      {item.step === "arrival" && canSeePhoto && (
        <div className="space-y-1">
          {item.has_image ? (
            <>
              <button type="button" className={secondary} onClick={() => void downloadPhoto()}>
                {t("apoa.photo")}
              </button>
              <p className="text-xs text-muted-foreground">{t("apoa.photoNote")}</p>
            </>
          ) : (
            <p className="text-xs text-muted-foreground">{t("apoa.noPhoto")}</p>
          )}
        </div>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      {canEdit && (
        <div className="flex flex-wrap gap-2">
          {item.step && (
            <>
              <button
                type="button"
                className={primary}
                onClick={() => onAction(item, "mark", item.step as ApoaStep)}
                aria-label={`${t(item.step === "arrival" ? "apoa.markArrival" : "apoa.markDeparture")}: ${item.full_name}`}
              >
                {t(item.step === "arrival" ? "apoa.markArrival" : "apoa.markDeparture")}
              </button>
              <button
                type="button"
                className={secondary}
                onClick={() => onAction(item, "not_required", item.step as ApoaStep)}
              >
                {t("apoa.notRequired")}
              </button>
            </>
          )}
          {lastDone && (
            <button type="button" className={secondary} onClick={() => onAction(item, "undo", lastDone)}>
              {t("apoa.undo")}
            </button>
          )}
        </div>
      )}
    </li>
  );
}
