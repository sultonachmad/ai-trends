"use client";

import { shortDate, stayRange } from "@/lib/booking-format";
import type { DeskEntry, DeskRoom } from "@/lib/front-desk-api";
import { owesMoney } from "@/lib/front-desk-format";
import { useLocale } from "@/lib/locale-store";
import { formatRupiah } from "@/lib/money";

export type DeskActionKind = "checkin" | "checkout" | "noshow" | "undo" | "stay";

interface DeskEntryCardProps {
  entry: DeskEntry;
  actions: readonly DeskActionKind[];
  canEdit: boolean;
  onAction: (kind: DeskActionKind, entry: DeskEntry) => void;
  onRoom: (entry: DeskEntry, room: DeskRoom) => void;
}

const badge = "inline-block rounded-full px-2 py-0.5 text-xs font-medium";
const primary =
  "min-h-11 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90";
const secondary = "min-h-11 rounded-md border border-border px-4 py-2 text-sm hover:bg-accent";
const MAIN_ACTIONS: readonly DeskActionKind[] = ["checkin", "checkout"];

function RoomChip({ room, canEdit, onClick }: { room: DeskRoom; canEdit: boolean; onClick: () => void }) {
  const { t } = useLocale();
  const label = room.name ?? t("frontdesk.assignRoom");
  const state = room.hk_status ? t(`frontdesk.hk.${room.hk_status}`) : null;
  const text = (
    <>
      {label}
      {state && <span className="ml-1 text-xs text-muted-foreground">· {state}</span>}
      {room.locked && <span className="ml-1 text-xs">· {t("frontdesk.locked")}</span>}
    </>
  );
  if (!canEdit) return <span className="rounded-md bg-muted px-3 py-2 text-sm">{text}</span>;
  return (
    <button
      type="button"
      onClick={onClick}
      className={`min-h-11 rounded-md border px-3 py-2 text-left text-sm hover:bg-accent ${
        room.unit_id ? "border-border" : "border-primary font-medium text-primary"
      }`}
    >
      {text}
    </button>
  );
}

/** One booking on the desk: who, when, which rooms, what can be done now. */
export function DeskEntryCard({ entry, actions, canEdit, onAction, onRoom }: DeskEntryCardProps) {
  const { t, locale } = useLocale();
  return (
    <li className="space-y-3 rounded-lg border border-border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-base font-semibold">{entry.guest_name}</span>
        <span className="text-xs text-muted-foreground">{entry.number}</span>
        {entry.overdue && (
          <span className={`${badge} bg-destructive/15 text-destructive`}>
            {t("frontdesk.overdue")}
          </span>
        )}
        {entry.status === "no_show" && (
          <span className={`${badge} bg-muted`}>{t("bookings.status.no_show")}</span>
        )}
        {entry.status === "checked_out" && (
          <span className={`${badge} bg-muted`}>{t("bookings.status.checked_out")}</span>
        )}
        {owesMoney(entry) && (
          <span className={`${badge} bg-accent text-accent-foreground`}>
            {t("bookings.balance", { amount: formatRupiah(entry.balance_due) })}
          </span>
        )}
      </div>
      <p className="text-sm">
        {stayRange(entry.arrival, entry.departure, locale)} ·{" "}
        {t("bookings.nights", { count: entry.nights })} ·{" "}
        {t("bookings.unitsOf", { count: entry.units, room: entry.room_type })} · {entry.source}
      </p>
      <div className="flex flex-wrap gap-2">
        {entry.rooms.map((room) => (
          <RoomChip
            key={room.line_id}
            room={room}
            canEdit={canEdit && entry.status !== "no_show" && entry.status !== "checked_out"}
            onClick={() => onRoom(entry, room)}
          />
        ))}
      </div>
      {canEdit && actions.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {actions.map((kind) => (
            <button
              key={kind}
              type="button"
              onClick={() => onAction(kind, entry)}
              aria-label={`${t(`frontdesk.action.${kind}`)}: ${entry.guest_name}`}
              className={MAIN_ACTIONS.includes(kind) ? primary : secondary}
            >
              {t(`frontdesk.action.${kind}`)}
            </button>
          ))}
        </div>
      )}
      {entry.status === "in_house" && (
        <p className="text-xs text-muted-foreground">
          {t("frontdesk.leaves", { date: shortDate(entry.departure, locale) })}
        </p>
      )}
    </li>
  );
}
