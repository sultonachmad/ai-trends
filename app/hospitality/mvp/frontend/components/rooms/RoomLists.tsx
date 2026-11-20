"use client";

import { useLocale } from "@/lib/locale-store";
import { formatRupiah } from "@/lib/money";
import type { RatePlan } from "@/lib/rate-plans-api";
import type { RoomType } from "@/lib/rooms-api";

const rowClass = "flex flex-wrap items-center justify-between gap-3 px-4 py-3";
const actionClass = "rounded-md border border-border px-3 py-1 text-sm hover:bg-accent";

function OffBadge() {
  const { t } = useLocale();
  return (
    <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
      {t("rooms.off")}
    </span>
  );
}

interface RoomTypeListProps {
  rooms: RoomType[];
  onEdit: (room: RoomType) => void;
  onToggle: (room: RoomType) => void;
}

/** Room types with their unit count and capacity; edit and switch on/off. */
export function RoomTypeList({ rooms, onEdit, onToggle }: RoomTypeListProps) {
  const { t } = useLocale();
  return (
    <ul className="divide-y divide-border">
      {rooms.map((room) => (
        <li key={room.id} className={`${rowClass} ${room.is_active ? "" : "opacity-70"}`}>
          <div className="min-w-0">
            <p className="flex flex-wrap items-center gap-2 font-medium">
              <span className="truncate">{room.name}</span>
              {!room.is_active && <OffBadge />}
            </p>
            <p className="text-sm text-muted-foreground">
              {t(`rooms.kind.${room.kind}`)} · {t("rooms.units", { count: room.units.length })} ·{" "}
              {t("rooms.guests", { count: room.max_guests })}
            </p>
          </div>
          <div className="flex gap-2">
            {room.is_active && (
              <button type="button" onClick={() => onEdit(room)} className={actionClass}>
                {t("rooms.edit")}
              </button>
            )}
            <button type="button" onClick={() => onToggle(room)} className={actionClass}>
              {room.is_active ? t("rooms.switchOff") : t("rooms.switchOn")}
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}

interface RatePlanListProps {
  plans: RatePlan[];
  rooms: RoomType[];
  onEdit: (plan: RatePlan) => void;
  onToggle: (plan: RatePlan) => void;
}

/** Rate plans with their terms and the normal price of each room type they sell. */
export function RatePlanList({ plans, rooms, onEdit, onToggle }: RatePlanListProps) {
  const { t } = useLocale();
  const roomName = (id: string) => rooms.find((room) => room.id === id)?.name ?? "";
  const terms = (plan: RatePlan) => {
    if (plan.non_refundable) return t("rates.terms.nonRefundable");
    return plan.free_cancellation_days === 0
      ? t("rates.terms.freeUntilArrival")
      : t("rates.terms.free", { days: plan.free_cancellation_days ?? 0 });
  };
  return (
    <ul className="divide-y divide-border">
      {plans.map((plan) => (
        <li key={plan.id} className={`${rowClass} ${plan.is_active ? "" : "opacity-70"}`}>
          <div className="min-w-0 flex-1">
            <p className="flex flex-wrap items-center gap-2 font-medium">
              <span className="truncate">{plan.name}</span>
              {!plan.is_active && <OffBadge />}
            </p>
            <p className="text-sm text-muted-foreground">
              {t(`rates.meal.${plan.meal_plan}`)} · {terms(plan)}
            </p>
            <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm">
              {plan.prices.map((price) => (
                <li key={price.room_type_id}>
                  <span className="text-muted-foreground">{roomName(price.room_type_id)}:</span>{" "}
                  <span className="font-medium tabular-nums">
                    {t("rates.perNight", { amount: formatRupiah(price.amount) })}
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div className="flex gap-2">
            {plan.is_active && (
              <button type="button" onClick={() => onEdit(plan)} className={actionClass}>
                {t("rooms.edit")}
              </button>
            )}
            <button type="button" onClick={() => onToggle(plan)} className={actionClass}>
              {plan.is_active ? t("rooms.switchOff") : t("rooms.switchOn")}
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}
