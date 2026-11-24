"use client";

import { useEffect, useState, type FormEvent } from "react";

import { Dialog } from "@/components/Dialog";
import { inputClass } from "@/components/rooms/RoomTypeDialog";
import { NOTE_MAX } from "@/lib/booking-forms";
import { fetchBooking, updateBooking } from "@/lib/bookings-api";
import type { DeskEntry } from "@/lib/front-desk-api";
import { useLocale } from "@/lib/locale-store";

interface StayChangeDialogProps {
  entry: DeskEntry | null;
  today: string;
  onClose: () => void;
  onDone: () => void;
}

const secondary =
  "min-h-11 rounded-md border border-border px-4 py-2 text-sm hover:bg-accent disabled:opacity-50";
const primary =
  "min-h-11 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50";
const textOf = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));

/** After check-in only the departure date, guest counts and notes can change. */
export function StayChangeDialog({ entry, today, onClose, onDone }: StayChangeDialogProps) {
  const { t } = useLocale();
  const [departure, setDeparture] = useState("");
  const [adults, setAdults] = useState(1);
  const [children, setChildren] = useState(0);
  const [notes, setNotes] = useState("");
  const [savedNotes, setSavedNotes] = useState<string | null>(null); // null until loaded
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bookingId = entry?.id ?? null;

  useEffect(() => {
    if (!entry) return;
    setDeparture(entry.departure);
    setAdults(entry.adults);
    setChildren(entry.children);
    setNotes("");
    setSavedNotes(null);
    setError(null);
    let cancelled = false;
    fetchBooking(entry.id)
      .then((found) => {
        if (cancelled) return;
        setNotes(found.notes ?? "");
        setSavedNotes(found.notes ?? "");
      })
      .catch((cause) => {
        if (!cancelled) setError(textOf(cause));
      });
    return () => {
      cancelled = true;
    };
    // the form is filled when another booking opens
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookingId]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!entry) return;
    setBusy(true);
    setError(null);
    try {
      await updateBooking(entry.id, {
        ...(departure !== entry.departure ? { departure } : {}),
        adults,
        children,
        ...(savedNotes !== null && notes.trim() !== savedNotes ? { notes: notes.trim() } : {}),
      });
      onDone();
    } catch (cause) {
      setError(textOf(cause));
    } finally {
      setBusy(false);
    }
  };

  const earliest = entry && entry.arrival >= today ? entry.arrival : today;
  return (
    <Dialog open={entry !== null} onClose={() => !busy && onClose()} title={t("frontdesk.stay.title")}>
      <form onSubmit={(event) => void submit(event)} className="space-y-3 text-sm">
        <div>
          <label htmlFor="stay-departure" className="mb-1 block font-medium">
            {t("frontdesk.stay.departure")}
          </label>
          <input
            id="stay-departure"
            type="date"
            min={earliest}
            value={departure}
            onChange={(event) => setDeparture(event.target.value)}
            className={inputClass}
          />
          <p className="mt-1 text-xs text-muted-foreground">{t("frontdesk.stay.priceHint")}</p>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="stay-adults" className="mb-1 block font-medium">
              {t("frontdesk.stay.adults")}
            </label>
            <input
              id="stay-adults"
              type="number"
              min={1}
              value={adults}
              onChange={(event) => setAdults(Number(event.target.value))}
              className={inputClass}
            />
          </div>
          <div>
            <label htmlFor="stay-children" className="mb-1 block font-medium">
              {t("frontdesk.stay.children")}
            </label>
            <input
              id="stay-children"
              type="number"
              min={0}
              value={children}
              onChange={(event) => setChildren(Number(event.target.value))}
              className={inputClass}
            />
          </div>
        </div>
        <div>
          <label htmlFor="stay-notes" className="mb-1 block font-medium">
            {t("frontdesk.stay.notes")}
          </label>
          <input
            id="stay-notes"
            maxLength={NOTE_MAX}
            disabled={savedNotes === null}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            className={inputClass}
          />
        </div>
        {error && (
          <p role="alert" className="text-destructive">
            {error}
          </p>
        )}
        <div className="flex flex-wrap justify-end gap-2">
          <button type="button" disabled={busy} onClick={onClose} className={secondary}>
            {t("frontdesk.back")}
          </button>
          <button type="submit" disabled={busy || savedNotes === null} className={primary}>
            {t("frontdesk.stay.save")}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
