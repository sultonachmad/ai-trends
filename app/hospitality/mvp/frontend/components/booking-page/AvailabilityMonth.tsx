"use client";

import { useEffect, useState } from "react";

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
  const navClass =
    "h-11 w-11 rounded-md border border-border text-lg hover:bg-accent disabled:opacity-40";

  return (
    <div className="space-y-2">
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
        <h3 aria-live="polite" className="font-semibold capitalize">
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
      {failed && <p className="text-sm text-muted-foreground">{t("book.calendarFailed")}</p>}
      <div className="grid grid-cols-7 gap-1 text-center text-xs">
        {weekdays.map((name) => (
          <span key={name} aria-hidden="true" className="py-1 text-muted-foreground">
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
          const state = chosen
            ? "bg-primary text-primary-foreground"
            : inside
              ? "bg-primary/15"
              : open
                ? "border border-border hover:bg-accent"
                : "text-muted-foreground/60";
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
              className={`flex min-h-11 flex-col items-center justify-center rounded-md px-0 py-1 disabled:cursor-not-allowed ${state}`}
            >
              <span className="text-sm font-medium">{index + 1}</span>
              <span className="text-[10px] leading-3">
                {open && day?.lowest_price ? compactPrice(day.lowest_price) : " "}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
