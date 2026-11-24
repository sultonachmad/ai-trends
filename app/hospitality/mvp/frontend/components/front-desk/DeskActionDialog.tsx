"use client";

import { useEffect, useState } from "react";

import type { DeskActionKind } from "@/components/front-desk/DeskEntryCard";
import { Dialog } from "@/components/Dialog";
import { inputClass } from "@/components/rooms/RoomTypeDialog";
import {
  checkIn,
  checkOut,
  markNoShow,
  undoDeskAction,
  type DeskEntry,
  type EarlyChoice,
} from "@/lib/front-desk-api";
import {
  deskErrorKey,
  isRefusedAs,
  leavesEarly,
  owesMoney,
  refusedRooms,
} from "@/lib/front-desk-format";
import { useLocale } from "@/lib/locale-store";
import { formatRupiah } from "@/lib/money";
import { useCan } from "@/lib/rbac-store";

type ConfirmKind = Exclude<DeskActionKind, "stay">;

interface DeskActionDialogProps {
  action: { kind: ConfirmKind; entry: DeskEntry } | null;
  today: string;
  onClose: () => void;
  onDone: () => void;
}

const secondary =
  "min-h-11 rounded-md border border-border px-4 py-2 text-sm hover:bg-accent disabled:opacity-50";
const primary =
  "min-h-11 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50";
const REASON_MIN = 3;
const REASON_MAX = 300;
const EARLY_CHOICES: readonly EarlyChoice[] = ["keep_price", "nights_stayed"];

/** Confirms a check-in, check-out, no-show or undo, with what staff need to know first. */
export function DeskActionDialog({ action, today, onClose, onDone }: DeskActionDialogProps) {
  const { t } = useLocale();
  const canReducePrice = useCan("bookings:edit");
  const [early, setEarly] = useState<EarlyChoice>("keep_price");
  const [reason, setReason] = useState("");
  const [notReady, setNotReady] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setEarly("keep_price");
    setReason("");
    setNotReady(null);
    setError(null);
  }, [action]);

  if (!action) return <Dialog open={false} onClose={onClose}>{null}</Dialog>;
  const { kind, entry } = action;
  const isEarly = kind === "checkout" && leavesEarly(entry, today);

  const send = () => {
    if (kind === "checkin") return checkIn(entry.id, notReady !== null);
    if (kind === "checkout") return checkOut(entry.id, isEarly ? early : null);
    if (kind === "noshow") return markNoShow(entry.id);
    return undoDeskAction(entry.id, reason.trim());
  };

  const submit = async () => {
    if (kind === "undo" && reason.trim().length < REASON_MIN) {
      setError(t("frontdesk.undo.needReason"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await send();
      onDone();
    } catch (cause) {
      if (isRefusedAs(cause, "room_not_ready")) {
        setNotReady(refusedRooms(cause));
      } else {
        const key = deskErrorKey(cause);
        const rooms = refusedRooms(cause).join(", ");
        const text = key ? t(key) : cause instanceof Error ? cause.message : String(cause);
        setError(rooms ? `${text} (${rooms})` : text);
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onClose={() => !busy && onClose()} title={t(`frontdesk.confirm.${kind}.title`)}>
      <div className="space-y-3 text-sm">
        <p>{t(`frontdesk.confirm.${kind}.body`, { guest: entry.guest_name })}</p>
        {(kind === "checkin" || kind === "checkout") && owesMoney(entry) && (
          <p role="status" className="rounded-lg bg-accent px-3 py-2 text-accent-foreground">
            {t("frontdesk.balanceWarning", { amount: formatRupiah(entry.balance_due) })}
          </p>
        )}
        {notReady && (
          <p role="alert" className="rounded-lg bg-destructive/15 px-3 py-2 text-destructive">
            {t("frontdesk.notReadyWarning", { rooms: notReady.join(", ") })}
          </p>
        )}
        {isEarly && (
          <fieldset className="space-y-2">
            <legend className="font-medium">{t("frontdesk.early.title")}</legend>
            {EARLY_CHOICES.filter(
              (choice) => choice === "keep_price" || canReducePrice,
            ).map((choice) => (
              <label
                key={choice}
                className="flex min-h-11 cursor-pointer items-center gap-3 rounded-md border border-border px-3 py-2 hover:bg-accent"
              >
                <input
                  type="radio"
                  name="desk-early"
                  checked={early === choice}
                  onChange={() => setEarly(choice)}
                />
                {t(`frontdesk.early.${choice}`)}
              </label>
            ))}
          </fieldset>
        )}
        {kind === "undo" && (
          <div>
            <label htmlFor="desk-undo-reason" className="mb-1 block font-medium">
              {t("frontdesk.undo.reason")}
            </label>
            <input
              id="desk-undo-reason"
              maxLength={REASON_MAX}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              className={inputClass}
            />
          </div>
        )}
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
          {t(notReady ? "frontdesk.confirm.checkin.anyway" : `frontdesk.confirm.${kind}.submit`)}
        </button>
      </div>
    </Dialog>
  );
}
