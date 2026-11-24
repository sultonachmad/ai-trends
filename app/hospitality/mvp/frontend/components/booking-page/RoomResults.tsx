"use client";

import { RoomPlate } from "@/components/booking-page/RoomPlate";
import { staySecondaryButton, staySectionTitle } from "@/components/booking-page/stay-classes";
import { freeCancelUntil, hasFreeCancellation, termsKey } from "@/lib/booking-page-format";
import type { Availability, RateOption, RoomResult } from "@/lib/booking-page-api";
import { shortDate } from "@/lib/booking-format";
import { useLocale } from "@/lib/locale-store";
import { formatRupiah } from "@/lib/money";

interface RoomResultsProps {
  result: Availability;
  arrival: string;
  depositPercent: number;
  preferredRoom: string | null;
  roomOrder: readonly string[];
  onChoose: (room: RoomResult, option: RateOption) => void;
}

/** The rooms that can be booked for the stay, with total price and terms in plain words. */
export function RoomResults({
  result,
  arrival,
  depositPercent,
  preferredRoom,
  roomOrder,
  onChoose,
}: RoomResultsProps) {
  const { t, locale } = useLocale();
  if (result.rooms.length === 0) {
    return (
      <p role="status" className="rounded-stay-md bg-stay-surface-soft p-6 text-type-body text-stay-body">
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
    <section>
      <h2 className={staySectionTitle}>{t("book.results")}</h2>
      <ul
        className="mt-4 grid grid-cols-1 gap-x-4 gap-y-8 min-[480px]:grid-cols-2 min-[744px]:grid-cols-1 lg:grid-cols-2"
        aria-label={t("book.results")}
      >
        {rooms.map((room) => (
          <li key={room.id}>
            <div className="relative">
              <RoomPlate id={room.id} order={roomOrder} className="aspect-square w-full rounded-stay-md" />
              {hasFreeCancellation(room.options) && (
                <span className="absolute left-3 top-3 rounded-full bg-stay-canvas px-2.5 py-1 text-type-badge text-stay-ink shadow-stay">
                  {t("book.freeCancelBadge")}
                </span>
              )}
            </div>
            <h3 className="mt-3 text-type-title">{room.name}</h3>
            <p className="text-type-body-sm text-stay-muted">
              {t("book.maxGuests", { count: room.max_guests })}
            </p>
            {room.options.map((option) => {
              const until = freeCancelUntil(arrival, option.free_cancellation_days);
              return (
                <div key={option.rate_plan_id} className="mt-3 space-y-2 border-t border-stay-hairline-soft pt-3">
                  <p className="text-type-caption">{option.name}</p>
                  <p className="text-type-body-sm text-stay-muted">
                    {t(termsKey(option), { date: until ? shortDate(until, locale) : "" })}{" "}
                    {t("book.depositLine", {
                      percent: depositPercent,
                      amount: formatRupiah(option.deposit),
                    })}
                  </p>
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-type-title">{formatRupiah(option.total)}</p>
                      <p className="text-type-caption-sm text-stay-muted">
                        {t("book.totalFor", { nights: result.nights })}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => onChoose(room, option)}
                      className={`shrink-0 ${staySecondaryButton}`}
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
    </section>
  );
}
