"use client";

import { useEffect, useState } from "react";

import { Dialog } from "@/components/Dialog";
import { useLocale } from "@/lib/locale-store";
import type { Category, MaintBoard, NewRequest } from "@/lib/maintenance-api";
import { CATEGORIES } from "@/lib/maintenance-format";

const field = "min-h-12 w-full rounded-md border border-border bg-background px-3 py-2 text-base";
const NOT_A_ROOM = "";

/** Report a repair: room or place, what is broken, urgent, what is wrong, a photo. */
export function ReportForm({
  open,
  board,
  busy,
  onClose,
  onSend,
}: {
  open: boolean;
  board: MaintBoard;
  busy: boolean;
  onClose: () => void;
  onSend: (request: NewRequest) => void;
}) {
  const { t } = useLocale();
  const [unitId, setUnitId] = useState(NOT_A_ROOM);
  const [place, setPlace] = useState("");
  const [category, setCategory] = useState<Category>("ac");
  const [urgent, setUrgent] = useState(false);
  const [description, setDescription] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);

  useEffect(() => {
    if (!open) return;
    setUnitId(NOT_A_ROOM);
    setPlace("");
    setCategory("ac");
    setUrgent(false);
    setDescription("");
    setPhoto(null);
  }, [open]);

  const ready = description.trim().length > 0 && (unitId !== NOT_A_ROOM || place.trim().length > 0);
  return (
    <Dialog open={open} onClose={onClose} title={t("repair.report")}>
      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          if (ready) onSend({ unitId: unitId || null, place, category, urgent, description, photo });
        }}
      >
        <label className="block space-y-1 text-sm">
          <span>{t("repair.room")}</span>
          <select value={unitId} onChange={(e) => setUnitId(e.target.value)} className={field}>
            <option value={NOT_A_ROOM}>{t("repair.noRoom")}</option>
            {board.rooms.map((room) => (
              <option key={room.id} value={room.id}>{room.name}</option>
            ))}
          </select>
        </label>
        {unitId === NOT_A_ROOM && (
          <label className="block space-y-1 text-sm">
            <span>{t("repair.place")}</span>
            <input value={place} maxLength={80} onChange={(e) => setPlace(e.target.value)} className={field} />
          </label>
        )}
        <label className="block space-y-1 text-sm">
          <span>{t("repair.categoryLabel")}</span>
          <select value={category} onChange={(e) => setCategory(e.target.value as Category)} className={field}>
            {CATEGORIES.map((option) => (
              <option key={option} value={option}>{t(`repair.category.${option}`)}</option>
            ))}
          </select>
        </label>
        <label className="block space-y-1 text-sm">
          <span>{t("repair.description")}</span>
          <textarea
            value={description}
            maxLength={300}
            rows={3}
            required
            onChange={(e) => setDescription(e.target.value)}
            className={field}
          />
        </label>
        <label className="flex min-h-12 items-center gap-3 text-base">
          <input type="checkbox" checked={urgent} onChange={(e) => setUrgent(e.target.checked)} className="h-5 w-5" />
          {t("repair.urgent")}
        </label>
        <label className="block space-y-1 text-sm">
          <span>{t("repair.photo")}</span>
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            capture="environment"
            onChange={(e) => setPhoto(e.target.files?.[0] ?? null)}
            className="block w-full text-sm"
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
            {t("repair.send")}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
