"use client";

import { useEffect, useState } from "react";

import { stayFocus } from "@/components/booking-page/stay-classes";
import {
  compactPrice,
  leadingBlanks,
  monthRange,
  shiftMonth,
} from "@/lib/booking-page-format";
import { fetchPublicCalendar, type PublicDay } from "@/lib/booking-page-api";
import { useLocale } from "@/lib/locale-store";

const WEEK_START = "2024-01-01"; // a Monday

interface AvailabilityMonthProps {
  slug: string;
  today: string;
  lastArrival: string;
  arrival: string;
  departure: string;
  onPick: (date: string) => void;
}

/** A month of dates with availability and the lowest price. */
export function AvailabilityMonth({
  slug,
  today,
  lastArrival,
  arrival,
  departure,
  onPick,
}: AvailabilityMonthProps) {
  const { t, locale } = useLocale();
  const [month, setMonth] = useState(() => shiftMonth(arrival || today, 0));
  const [days, setDays] = useState<PublicDay[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const { to } = monthRange(month);
    setDays(null);
    setFailed(false);
    fetchPublicCalendar(slug, month < today ? today : month, to)
      .then((found) => {
        if (!cancelled) setDays(found.days);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [slug, month, today]);

  const tag = locale === "id" ? "id-ID" : "en-GB";
  const title = new Intl.DateTimeFormat(tag, {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${month}T00:00:00Z`));
  const weekdays = Array.from({ length: 7 }, (_, index) =>
    new Intl.DateTimeFormat(tag, { weekday: "short", timeZone: "UTC" }).format(
      new Date(Date.parse(`${WEEK_START}T00:00:00Z`) + index * 86_400_000),
    ),
  );
  const { to } = monthRange(month);
  const dayCount = Number(to.slice(8));
  const byDate = new Map((days ?? []).map((day) => [day.date, day]));
  const canGoBack = month > shiftMonth(today, 0);
  const canGoForward = shiftMonth(month, 1) <= lastArrival;
  const navClass = `h-11 w-11 rounded-full border border-stay-hairline bg-stay-canvas text-lg text-stay-ink transition-colors hover:bg-stay-surface-soft disabled:cursor-not-allowed disabled:text-stay-muted-soft ${stayFocus}`;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <button
          type="button"
          aria-label={t("book.prevMonth")}
          disabled={!canGoBack}
          onClick={() => setMonth(shiftMonth(month, -1))}
          className={navClass}
        >
          ‹
        </button>
        <h3 aria-live="polite" className="text-type-title capitalize">
          {title}
        </h3>
        <button
          type="button"
          aria-label={t("book.nextMonth")}
          disabled={!canGoForward}
          onClick={() => setMonth(shiftMonth(month, 1))}
          className={navClass}
        >
          ›
        </button>
      </div>
      {failed && <p className="text-type-body-sm text-stay-error">{t("book.calendarFailed")}</p>}
      <div className="grid grid-cols-7 gap-y-1 text-center">
        {weekdays.map((name) => (
          <span key={name} aria-hidden="true" className="py-1 text-type-caption-sm text-stay-muted">
            {name}
          </span>
        ))}
        {Array.from({ length: leadingBlanks(month) }, (_, index) => (
          <span key={`blank-${index}`} />
        ))}
        {Array.from({ length: dayCount }, (_, index) => {
          const date = `${month.slice(0, 8)}${String(index + 1).padStart(2, "0")}`;
          const day = byDate.get(date);
          const open = Boolean(day?.available);
          // the departure day may itself be full: nobody sleeps that night
          const pickable = date >= today && (open || (Boolean(arrival) && !departure && date > arrival));
          const chosen = date === arrival || date === departure;
          const inside = Boolean(arrival && departure && date > arrival && date < departure);
          const hasRange = Boolean(arrival && departure);
          const lozenge = inside
            ? "bg-stay-surface-soft"
            : hasRange && date === arrival
              ? "rounded-l-full bg-stay-surface-soft"
              : hasRange && date === departure
                ? "rounded-r-full bg-stay-surface-soft"
                : "";
          const circle = chosen
            ? "bg-stay-ink text-stay-canvas"
            : pickable
              ? "text-stay-ink group-hover:outline-1 group-hover:outline-stay-ink"
              : "text-stay-muted-soft line-through";
          return (
            <button
              key={date}
              type="button"
              disabled={!pickable}
              aria-pressed={chosen}
              aria-label={
                open && day?.lowest_price
                  ? t("book.dayOpen", { date, price: compactPrice(day.lowest_price) })
                  : t("book.dayClosed", { date })
              }
              onClick={() => onPick(date)}
              className="group flex min-h-14 flex-col items-stretch focus-visible:outline-none disabled:cursor-not-allowed"
            >
              <span className={`flex h-10 items-center justify-center ${lozenge}`}>
                <span
                  className={`flex h-10 w-10 items-center justify-center rounded-full text-type-body-sm group-focus-visible:outline-2 group-focus-visible:outline-offset-1 group-focus-visible:outline-stay-ink ${circle}`}
                >
                  {index + 1}
                </span>
              </span>
              <span className="mt-0.5 h-3 text-type-badge font-normal text-stay-muted">
                {open && day?.lowest_price ? compactPrice(day.lowest_price) : ""}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
