"use client";

import { shortDate } from "@/lib/booking-format";
import type { RoomToday } from "@/lib/front-desk-api";
import { useLocale } from "@/lib/locale-store";

const badge = "inline-block rounded-full px-2 py-0.5 text-xs font-medium";

function hkClass(status: string): string {
  if (status === "dirty") return "bg-destructive/15 text-destructive";
  if (status === "in_progress") return "bg-accent text-accent-foreground";
  return "bg-primary/15 text-primary";
}

/** Every room right now: who is in it and whether it is ready. */
export function RoomsToday({
  rooms,
  busy = false,
  onStatus,
}: {
  rooms: RoomToday[];
  busy?: boolean;
  /** Given when the person may change a room's cleaning status by hand. */
  onStatus?: (room: RoomToday, status: "clean" | "dirty") => void;
}) {
  const { t, locale } = useLocale();
  if (rooms.length === 0) {
    return <p className="text-sm text-muted-foreground">{t("frontdesk.noRooms")}</p>;
  }
  return (
    <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {rooms.map((room) => (
        <li key={room.id} className="space-y-2 rounded-lg border border-border bg-card p-4">
          <div>
            <p className="font-semibold">{room.name}</p>
            <p className="text-xs text-muted-foreground">{room.room_type}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className={`${badge} ${hkClass(room.hk_status)}`}>
              {t(`frontdesk.hk.${room.hk_status}`)}
            </span>
            <span className={`${badge} bg-muted`}>{t(`frontdesk.fo.${room.fo_status}`)}</span>
            {room.service_status !== "in_service" && (
              <span className={`${badge} bg-destructive/15 text-destructive`}>
                {t(`frontdesk.service.${room.service_status}`)}
              </span>
            )}
          </div>
          {onStatus && (
            <button
              type="button"
              disabled={busy}
              onClick={() => onStatus(room, room.hk_status === "dirty" ? "clean" : "dirty")}
              className="min-h-11 rounded-md border border-border px-3 py-1 text-sm hover:bg-accent disabled:opacity-50"
            >
              {t(room.hk_status === "dirty" ? "hk.room.markClean" : "hk.room.markDirty")}
            </button>
          )}
          {room.guest_name && (
            <p className="text-sm">
              {room.guest_name}
              {room.departure && (
                <span className="block text-xs text-muted-foreground">
                  {t("frontdesk.leaves", { date: shortDate(room.departure, locale) })}
                </span>
              )}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}
