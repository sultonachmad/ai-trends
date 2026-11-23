"use client";

import { useEffect, useState, type FormEvent } from "react";

import { Dialog } from "@/components/Dialog";
import { inputClass } from "@/components/rooms/RoomTypeDialog";
import {
  createCalendarLink,
  updateCalendarLink,
  type CalendarLink,
  type CalendarLinkCreated,
} from "@/lib/calendar-links-api";
import { useLocale } from "@/lib/locale-store";
import type { RoomType } from "@/lib/rooms-api";

const errorText = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));
const labelClass = "mb-1 block text-sm font-medium";

interface CalendarLinkDialogProps {
  open: boolean;
  /** Set when editing; otherwise a new link is created. */
  link: CalendarLink | null;
  rooms: RoomType[];
  onClose: () => void;
  onSaved: (saved: CalendarLink | CalendarLinkCreated) => void;
}

/** Add a calendar link, or change its name and the site's calendar address. */
export function CalendarLinkDialog({ open, link, rooms, onClose, onSaved }: CalendarLinkDialogProps) {
  const { t } = useLocale();
  const [roomId, setRoomId] = useState("");
  const [label, setLabel] = useState("");
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setRoomId(link?.room_type_id ?? rooms[0]?.id ?? "");
    setLabel(link?.label ?? "");
    setUrl("");
    setError(null);
  }, [open, link, rooms]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const importUrl = url.trim();
    try {
      const saved = link
        ? await updateCalendarLink(link.id, {
            label: label.trim(),
            ...(importUrl ? { import_url: importUrl } : {}),
          })
        : await createCalendarLink({
            room_type_id: roomId,
            label: label.trim(),
            ...(importUrl ? { import_url: importUrl } : {}),
          });
      onSaved(saved);
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={() => (busy ? null : onClose())}
      title={t(link ? "calendarLinks.editTitle" : "calendarLinks.addTitle")}
    >
      <form onSubmit={(event) => void submit(event)} className="space-y-4">
        {!link && (
          <div>
            <label htmlFor="calendar-room" className={labelClass}>
              {t("calendarLinks.room")}
            </label>
            <select
              id="calendar-room"
              required
              value={roomId}
              onChange={(event) => setRoomId(event.target.value)}
              className={inputClass}
            >
              {rooms.map((room) => (
                <option key={room.id} value={room.id}>
                  {room.name}
                </option>
              ))}
            </select>
          </div>
        )}
        <div>
          <label htmlFor="calendar-label" className={labelClass}>
            {t("calendarLinks.label")}
          </label>
          <input
            id="calendar-label"
            required
            maxLength={80}
            value={label}
            placeholder={t("calendarLinks.labelPlaceholder")}
            onChange={(event) => setLabel(event.target.value)}
            className={inputClass}
          />
        </div>
        <div>
          <label htmlFor="calendar-url" className={labelClass}>
            {t("calendarLinks.importUrl")}
          </label>
          <input
            id="calendar-url"
            type="url"
            maxLength={2048}
            autoComplete="off"
            value={url}
            placeholder="https://"
            onChange={(event) => setUrl(event.target.value)}
            className={inputClass}
          />
          <p className="mt-1 text-xs text-muted-foreground">
            {t(link?.imports ? "calendarLinks.importKeep" : "calendarLinks.importHint")}
          </p>
        </div>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={onClose}
            className="rounded-md bg-secondary px-4 py-2 text-sm text-secondary-foreground disabled:opacity-50"
          >
            {t("rooms.form.cancel")}
          </button>
          <button
            type="submit"
            disabled={busy || !label.trim() || (!link && !roomId)}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {t("calendarLinks.save")}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
