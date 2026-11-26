"use client";

import type { HkBoard, HkRoom } from "@/lib/housekeeping-api";
import { useLocale } from "@/lib/locale-store";

export type RoomAction = "dirty" | "clean" | "inspected" | "request";

const badge = "inline-block rounded-full px-2 py-0.5 text-xs font-medium";
const small = "min-h-11 rounded-md border border-border px-3 py-1 text-sm hover:bg-accent disabled:opacity-50";

function hkClass(status: string): string {
  if (status === "dirty") return "bg-destructive/15 text-destructive";
  if (status === "in_progress") return "bg-accent text-accent-foreground";
  return "bg-primary/15 text-primary";
}

/** Every room and its cleaning status; staff may change a status by hand. */
export function AllRooms({
  board,
  canEdit,
  canManage,
  busy,
  onAction,
}: {
  board: HkBoard;
  canEdit: boolean;
  canManage: boolean;
  busy: boolean;
  onAction: (action: RoomAction, room: HkRoom) => void;
}) {
  const { t } = useLocale();
  if (board.rooms.length === 0) {
    return <p className="text-sm text-muted-foreground">{t("frontdesk.noRooms")}</p>;
  }
  return (
    <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {board.rooms.map((room) => (
        <li key={room.id} className="space-y-2 rounded-lg border border-border bg-card p-4">
          <div>
            <p className="text-lg font-semibold">{room.name}</p>
            <p className="text-xs text-muted-foreground">{room.room_type}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className={`${badge} ${hkClass(room.hk_status)}`}>{t(`frontdesk.hk.${room.hk_status}`)}</span>
            <span className={`${badge} bg-muted`}>{t(`frontdesk.fo.${room.fo_status}`)}</span>
            {room.service_status !== "in_service" && (
              <span className={`${badge} bg-destructive/15 text-destructive`}>
                {t(`frontdesk.service.${room.service_status}`)}
              </span>
            )}
            {room.arrival_today && (
              <span className={`${badge} bg-primary text-primary-foreground`}>{t("hk.arrivingToday")}</span>
            )}
          </div>
          {room.task_status && (
            <p className="text-xs text-muted-foreground">
              {room.assigned_name
                ? t("hk.room.cleaning", { status: t(`hk.status.${room.task_status}`), name: room.assigned_name })
                : t(`hk.status.${room.task_status}`)}
            </p>
          )}
          {canEdit && (
            <div className="flex flex-wrap gap-2">
              {room.hk_status !== "clean" && room.hk_status !== "inspected" && (
                <button type="button" disabled={busy} onClick={() => onAction("clean", room)} className={small}>
                  {t("hk.room.markClean")}
                </button>
              )}
              {canManage && room.hk_status === "clean" && board.ready_when === "inspected" && (
                <button type="button" disabled={busy} onClick={() => onAction("inspected", room)} className={small}>
                  {t("hk.room.markInspected")}
                </button>
              )}
              {room.hk_status !== "dirty" && (
                <button type="button" disabled={busy} onClick={() => onAction("dirty", room)} className={small}>
                  {t("hk.room.markDirty")}
                </button>
              )}
              {room.fo_status === "occupied" && !room.task_status && (
                <button type="button" disabled={busy} onClick={() => onAction("request", room)} className={small}>
                  {t("hk.room.cleanToday")}
                </button>
              )}
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}
