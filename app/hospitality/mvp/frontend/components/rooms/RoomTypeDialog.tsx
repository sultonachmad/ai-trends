"use client";

import { useEffect, useState, type FormEvent } from "react";

import { Dialog } from "@/components/Dialog";
import { useLocale } from "@/lib/locale-store";
import { checkRoomType, MAX_GUESTS, type RoomTypeForm } from "@/lib/room-forms";
import {
  createRoomType,
  renameUnit,
  ROOM_KINDS,
  updateRoomType,
  type RoomKind,
  type RoomType,
} from "@/lib/rooms-api";

const UNIT_NAME_MAX = 80;
const EMPTY: RoomTypeForm = { name: "", kind: "room", units: "1", maxGuests: "2" };
export const inputClass =
  "w-full rounded-md border border-border bg-card px-3 py-2 text-sm text-card-foreground focus:outline-none focus:ring-2 focus:ring-primary";

interface RoomTypeDialogProps {
  open: boolean;
  onClose: () => void;
  onSaved: (room: RoomType) => void;
  /** The room type to edit; omitted to create one. */
  room?: RoomType;
  /** The property's limit on units per room type. */
  maxUnits: number;
}

const formOf = (room?: RoomType): RoomTypeForm =>
  room
    ? {
        name: room.name,
        kind: room.kind,
        units: String(room.units.length),
        maxGuests: String(room.max_guests),
      }
    : EMPTY;

const namesOf = (room?: RoomType): Record<string, string> =>
  Object.fromEntries((room?.units ?? []).map((unit) => [unit.id, unit.name]));

/** Create or edit a room type: name, kind, how many units, guests per unit, unit names. */
export function RoomTypeDialog({ open, onClose, onSaved, room, maxUnits }: RoomTypeDialogProps) {
  const { t } = useLocale();
  const [form, setForm] = useState<RoomTypeForm>(EMPTY);
  const [unitNames, setUnitNames] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Start from the room being edited (or a blank form) each time the dialog opens.
  useEffect(() => {
    if (!open) return;
    setForm(formOf(room));
    setUnitNames(namesOf(room));
    setError(null);
  }, [open, room]);

  const close = () => {
    if (!busy) onClose();
  };

  const set = (field: keyof RoomTypeForm, value: string) =>
    setForm((current) => ({ ...current, [field]: value }));

  const save = async (input: ReturnType<typeof checkRoomType> & { ok: true }) => {
    if (!room) return createRoomType(input.value);
    let saved = await updateRoomType(room.id, input.value);
    for (const unit of saved.units) {
      const wanted = (unitNames[unit.id] ?? "").trim();
      const original = room.units.find((existing) => existing.id === unit.id)?.name;
      // Only names the person actually edited; the rest follow the room type's name.
      if (wanted !== "" && wanted !== original) {
        saved = await renameUnit(room.id, unit.id, wanted);
      }
    }
    return saved;
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const checked = checkRoomType(form, maxUnits);
    if (!checked.ok) return setError(t(checked.problem.key, checked.problem.vars));
    setBusy(true);
    setError(null);
    try {
      onSaved(await save(checked));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  };

  const title = room ? t("rooms.form.titleEdit") : t("rooms.form.titleNew");
  return (
    <Dialog open={open} onClose={close} title={title}>
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <div>
          <label htmlFor="room-name" className="mb-1 block text-sm font-medium">
            {t("rooms.form.name")}
          </label>
          <input
            id="room-name"
            value={form.name}
            maxLength={UNIT_NAME_MAX}
            autoComplete="off"
            onChange={(event) => set("name", event.target.value)}
            aria-describedby="room-name-hint"
            className={inputClass}
          />
          <p id="room-name-hint" className="mt-1 text-xs text-muted-foreground">
            {t("rooms.form.nameHint")}
          </p>
        </div>
        <div>
          <label htmlFor="room-kind" className="mb-1 block text-sm font-medium">
            {t("rooms.form.kind")}
          </label>
          <select
            id="room-kind"
            value={form.kind}
            onChange={(event) => set("kind", event.target.value as RoomKind)}
            className={inputClass}
          >
            {ROOM_KINDS.map((kind) => (
              <option key={kind} value={kind}>
                {t(`rooms.kind.${kind}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="room-units" className="mb-1 block text-sm font-medium">
              {t("rooms.form.units")}
            </label>
            <input
              id="room-units"
              inputMode="numeric"
              value={form.units}
              onChange={(event) => set("units", event.target.value)}
              aria-describedby={room ? "room-units-hint" : undefined}
              className={inputClass}
            />
          </div>
          <div>
            <label htmlFor="room-guests" className="mb-1 block text-sm font-medium">
              {t("rooms.form.guests")}
            </label>
            <input
              id="room-guests"
              inputMode="numeric"
              value={form.maxGuests}
              max={MAX_GUESTS}
              onChange={(event) => set("maxGuests", event.target.value)}
              className={inputClass}
            />
          </div>
        </div>
        {room && (
          <p id="room-units-hint" className="text-xs text-muted-foreground">
            {t("rooms.form.unitsHint")}
          </p>
        )}
        {room && room.units.length > 0 && (
          <fieldset>
            <legend className="mb-1 text-sm font-medium">{t("rooms.form.unitNames")}</legend>
            <p className="mb-2 text-xs text-muted-foreground">{t("rooms.form.unitNamesHint")}</p>
            <div className="grid max-h-48 grid-cols-1 gap-2 overflow-y-auto sm:grid-cols-2">
              {room.units.map((unit, index) => (
                <input
                  key={unit.id}
                  aria-label={`${t("rooms.form.unitNames")} ${index + 1}`}
                  value={unitNames[unit.id] ?? ""}
                  maxLength={UNIT_NAME_MAX}
                  onChange={(event) =>
                    setUnitNames((current) => ({ ...current, [unit.id]: event.target.value }))
                  }
                  className={inputClass}
                />
              ))}
            </div>
          </fieldset>
        )}
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={close}
            disabled={busy}
            className="rounded-md bg-secondary px-4 py-2 text-sm text-secondary-foreground disabled:opacity-50"
          >
            {t("rooms.form.cancel")}
          </button>
          <button
            type="submit"
            disabled={busy}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {t("rooms.form.save")}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
