"use client";

import { freeCancelUntil, termsKey } from "@/lib/booking-page-format";
import type { Availability, RateOption, RoomResult } from "@/lib/booking-page-api";
import { shortDate } from "@/lib/booking-format";
import { useLocale } from "@/lib/locale-store";
import { formatRupiah } from "@/lib/money";

const cardClass = "rounded-xl border border-border bg-card p-4 text-card-foreground shadow-sm";

interface RoomResultsProps {
  result: Availability;
  arrival: string;
  depositPercent: number;
  preferredRoom: string | null;
  onChoose: (room: RoomResult, option: RateOption) => void;
}

/** The rooms that can be booked for the stay, with total price and terms in plain words. */
export function RoomResults({
  result,
  arrival,
  depositPercent,
  preferredRoom,
  onChoose,
}: RoomResultsProps) {
  const { t, locale } = useLocale();
  if (result.rooms.length === 0) {
    return (
      <p role="status" className={`${cardClass} text-sm`}>
        {t(`book.none.${result.unavailable_reason ?? "sold_out"}`, {
          nights: result.min_stay ?? 0,
        })}
      </p>
    );
  }
  const rooms = [...result.rooms].sort(
    (a, b) => Number(b.id === preferredRoom) - Number(a.id === preferredRoom),
  );
  return (
    <ul className="space-y-3" aria-label={t("book.results")}>
      {rooms.map((room) => (
        <li key={room.id} className={`${cardClass} space-y-3`}>
          <div>
            <h3 className="text-lg font-semibold">{room.name}</h3>
            <p className="text-sm text-muted-foreground">
              {t("book.maxGuests", { count: room.max_guests })}
            </p>
          </div>
          {room.options.map((option) => {
            const until = freeCancelUntil(arrival, option.free_cancellation_days);
            return (
              <div
                key={option.rate_plan_id}
                className="flex flex-wrap items-end justify-between gap-3 border-t border-border pt-3"
              >
                <div className="min-w-0 space-y-1 text-sm">
                  <p className="font-medium">{option.name}</p>
                  <p className="text-muted-foreground">
                    {t(termsKey(option), {
                      date: until ? shortDate(until, locale) : "",
                    })}
                  </p>
                  <p className="text-muted-foreground">
                    {t("book.depositLine", {
                      percent: depositPercent,
                      amount: formatRupiah(option.deposit),
                    })}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-lg font-bold">{formatRupiah(option.total)}</p>
                  <p className="mb-2 text-xs text-muted-foreground">
                    {t("book.totalFor", { nights: result.nights })}
                  </p>
                  <button
                    type="button"
                    onClick={() => onChoose(room, option)}
                    className="min-h-11 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
                  >
                    {t("book.choose")}
                    <span className="sr-only">
                      : {room.name}, {option.name}
                    </span>
                  </button>
                </div>
              </div>
            );
          })}
        </li>
      ))}
    </ul>
  );
}
