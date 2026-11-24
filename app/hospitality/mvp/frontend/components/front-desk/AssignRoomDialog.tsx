"use client";

import { useEffect, useState } from "react";

import { Dialog } from "@/components/Dialog";
import {
  assignRoom,
  fetchFreeRooms,
  lockRoom,
  type DeskEntry,
  type DeskRoom,
  type FreeRoom,
} from "@/lib/front-desk-api";
import { deskErrorKey, isRefusedAs } from "@/lib/front-desk-format";
import { useLocale } from "@/lib/locale-store";

interface AssignRoomDialogProps {
  target: { entry: DeskEntry; room: DeskRoom } | null;
  onClose: () => void;
  onDone: () => void;
}

const secondary =
  "min-h-11 rounded-md border border-border px-4 py-2 text-sm hover:bg-accent disabled:opacity-50";
const primary =
  "min-h-11 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50";

/** Choose, change or clear the room of one line of a booking. */
export function AssignRoomDialog({ target, onClose, onDone }: AssignRoomDialogProps) {
  const { t } = useLocale();
  const [rooms, setRooms] = useState<FreeRoom[] | null>(null);
  const [chosen, setChosen] = useState<string | null>(null);
  const [needsConfirm, setNeedsConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bookingId = target?.entry.id ?? null;

  useEffect(() => {
    setRooms(null);
    setChosen(null);
    setNeedsConfirm(false);
    setError(null);
    if (!bookingId) return;
    let cancelled = false;
    fetchFreeRooms(bookingId)
      .then((found) => {
        if (cancelled) return;
        setRooms(found);
        setChosen(found[0]?.id ?? null); // ready rooms come first: the suggestion
      })
      .catch((cause) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : String(cause));
      });
    return () => {
      cancelled = true;
    };
  }, [bookingId]);

  const run = async (change: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await change();
      onDone();
    } catch (cause) {
      if (isRefusedAs(cause, "room_not_ready")) setNeedsConfirm(true);
      const key = deskErrorKey(cause);
      setError(key ? t(key) : cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  };

  const room = target?.room;
  const inHouse = target?.entry.status === "in_house";
  return (
    <Dialog
      open={target !== null}
      onClose={() => !busy && onClose()}
      title={t(room?.unit_id ? "frontdesk.assign.change" : "frontdesk.assign.title")}
    >
      {room?.locked ? (
        <p className="text-sm">{t("frontdesk.assign.lockedHint")}</p>
      ) : rooms === null ? (
        <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
      ) : rooms.length === 0 ? (
        <p className="text-sm">{t("frontdesk.assign.none")}</p>
      ) : (
        <fieldset className="space-y-2">
          <legend className="sr-only">{t("frontdesk.assign.title")}</legend>
          {rooms.map((option) => (
            <label
              key={option.id}
              className="flex min-h-11 cursor-pointer items-center gap-3 rounded-md border border-border px-3 py-2 text-sm hover:bg-accent"
            >
              <input
                type="radio"
                name="desk-room"
                checked={chosen === option.id}
                onChange={() => {
                  setChosen(option.id);
                  setNeedsConfirm(false);
                }}
              />
              <span className="font-medium">{option.name}</span>
              <span className="text-xs text-muted-foreground">
                {t(`frontdesk.hk.${option.hk_status}`)}
              </span>
            </label>
          ))}
        </fieldset>
      )}
      {error && (
        <p role="alert" className="mt-3 text-sm text-destructive">
          {error}
        </p>
      )}
      <div className="mt-4 flex flex-wrap justify-end gap-2">
        {room?.unit_id && (
          <button
            type="button"
            disabled={busy}
            onClick={() => void run(() => lockRoom(room.line_id, !room.locked))}
            className={secondary}
          >
            {t(room.locked ? "frontdesk.assign.unlock" : "frontdesk.assign.lock")}
          </button>
        )}
        {room?.unit_id && !room.locked && !inHouse && (
          <button
            type="button"
            disabled={busy}
            onClick={() => void run(() => assignRoom(room.line_id, null))}
            className={secondary}
          >
            {t("frontdesk.assign.clear")}
          </button>
        )}
        <button type="button" disabled={busy} onClick={onClose} className={secondary}>
          {t("proofs.close")}
        </button>
        {room && !room.locked && chosen && (
          <button
            type="button"
            disabled={busy}
            onClick={() => void run(() => assignRoom(room.line_id, chosen, needsConfirm))}
            className={primary}
          >
            {t(needsConfirm ? "frontdesk.assign.anyway" : inHouse ? "frontdesk.assign.move" : "frontdesk.assign.save")}
          </button>
        )}
      </div>
    </Dialog>
  );
}
