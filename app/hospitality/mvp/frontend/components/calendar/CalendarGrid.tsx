"use client";

import type { Calendar, CalendarDay, CalendarRoomType } from "@/lib/calendar-api";
import {
  cellState,
  compactRupiah,
  dayHeading,
  isEditable,
  isWeekend,
  longDate,
} from "@/lib/calendar-grid";
import type { Locale } from "@/lib/i18n";
import { useLocale } from "@/lib/locale-store";
import { formatRupiah } from "@/lib/money";

/** What a clicked cell asks to change. */
export type CellTarget =
  | { row: "availability"; roomTypeId: string; date: string; closed: boolean }
  | { row: "price"; roomTypeId: string; date: string; ratePlanId: string; amount: string }
  | { row: "minStay"; roomTypeId: string; date: string; minStay: number | null };

interface CalendarGridProps {
  calendar: Calendar;
  onCell: (target: CellTarget) => void;
}

const labelCell =
  "sticky left-0 z-10 w-24 min-w-24 bg-card px-2 py-2 text-left text-xs font-medium sm:w-36 sm:min-w-36";
const dayCell = "min-w-11 border-l border-border p-0 text-center text-xs";
const cellButton =
  "block h-full min-h-10 w-full px-1 py-2 tabular-nums hover:bg-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary disabled:cursor-default disabled:hover:bg-transparent";

function columnTone(date: string, today: string): string {
  if (date === today) return "bg-primary/10";
  return isWeekend(date) ? "bg-secondary/10" : "";
}

function HeaderRow({ days, today, locale }: { days: CalendarDay[]; today: string; locale: Locale }) {
  const { t } = useLocale();
  return (
    <tr className="border-b border-border text-muted-foreground">
      <th scope="col" className={labelCell}>
        <span className="sr-only">{t("calendar.title")}</span>
      </th>
      {days.map((day, index) => {
        const heading = dayHeading(day.date, locale);
        const showMonth = index === 0 || heading.day === "1";
        return (
          <th
            key={day.date}
            scope="col"
            aria-current={day.date === today ? "date" : undefined}
            className={`${dayCell} py-1 font-normal ${columnTone(day.date, today)}`}
          >
            <span
              className={`block text-[0.65rem] uppercase ${
                isWeekend(day.date) ? "font-bold text-foreground" : ""
              }`}
            >
              {heading.weekday}
            </span>
            <span className={`block text-sm ${day.date === today ? "font-bold text-foreground" : ""}`}>
              {heading.day}
            </span>
            <span className="block h-3 text-[0.65rem]">{showMonth ? heading.month : ""}</span>
          </th>
        );
      })}
    </tr>
  );
}

function RoomTable({ room, calendar, onCell }: { room: CalendarRoomType } & CalendarGridProps) {
  const { t, locale } = useLocale();
  const { today, last_editable_date: lastEditable } = calendar;
  const editable = (date: string) => isEditable(date, today, lastEditable);
  const label = (what: string, date: string) =>
    t("calendar.cell.edit", { what, room: room.name, date: longDate(date, locale) });
  const faded = (day: CalendarDay) =>
    cellState(day, today, lastEditable) === "past" ? "text-muted-foreground" : "";

  return (
    <div className="relative overflow-x-auto rounded-xl border border-border bg-card text-card-foreground shadow-sm">
      <table className="w-full border-collapse">
        <caption className="border-b border-border px-3 py-2 text-left text-sm font-semibold">
          <span className="sr-only">{t("calendar.table", { room: room.name })}</span>
          <span aria-hidden="true">{room.name}</span>
          <span aria-hidden="true" className="ml-2 font-normal text-muted-foreground">
            {t("rooms.units", { count: room.units })}
          </span>
        </caption>
        <thead>
          <HeaderRow days={room.days} today={today} locale={locale} />
        </thead>
        <tbody>
          <tr className="border-b border-border">
            <th scope="row" className={labelCell}>
              {t("calendar.row.available")}
            </th>
            {room.days.map((day) => (
              <td key={day.date} className={`${dayCell} ${columnTone(day.date, today)}`}>
                <button
                  type="button"
                  disabled={!editable(day.date)}
                  aria-label={label(t("calendar.row.available"), day.date)}
                  onClick={() =>
                    onCell({ row: "availability", roomTypeId: room.id, date: day.date, closed: day.closed })
                  }
                  className={`${cellButton} ${faded(day)}`}
                >
                  {day.closed ? (
                    <span className="rounded bg-destructive/15 px-1 py-0.5 text-[0.65rem] font-semibold text-destructive">
                      {t("calendar.closed")}
                    </span>
                  ) : (
                    <span className="font-semibold">{day.available}</span>
                  )}
                </button>
              </td>
            ))}
          </tr>
          {room.rate_plans.map((plan, planIndex) => (
            <tr key={plan.id} className="border-b border-border">
              <th scope="row" className={`${labelCell} font-normal`}>
                <span className="block truncate" title={plan.name}>
                  {plan.name}
                </span>
              </th>
              {room.days.map((day) => {
                const price = day.prices[planIndex];
                return (
                  <td key={day.date} className={`${dayCell} ${columnTone(day.date, today)}`}>
                    <button
                      type="button"
                      disabled={!editable(day.date)}
                      title={formatRupiah(price.amount)}
                      aria-label={`${label(plan.name, day.date)}: ${formatRupiah(price.amount)}${
                        price.is_override ? `, ${t("calendar.cell.changed")}` : ""
                      }`}
                      onClick={() =>
                        onCell({
                          row: "price",
                          roomTypeId: room.id,
                          date: day.date,
                          ratePlanId: plan.id,
                          amount: price.amount,
                        })
                      }
                      className={`${cellButton} ${faded(day)} ${day.closed ? "line-through opacity-60" : ""}`}
                    >
                      <span className={price.is_override ? "font-bold underline decoration-dotted" : ""}>
                        {compactRupiah(price.amount, locale)}
                      </span>
                    </button>
                  </td>
                );
              })}
            </tr>
          ))}
          <tr>
            <th scope="row" className={`${labelCell} font-normal text-muted-foreground`}>
              {t("calendar.row.minStay")}
            </th>
            {room.days.map((day) => (
              <td key={day.date} className={`${dayCell} ${columnTone(day.date, today)}`}>
                <button
                  type="button"
                  disabled={!editable(day.date)}
                  aria-label={`${label(t("calendar.row.minStay"), day.date)}: ${day.min_stay ?? "–"}`}
                  onClick={() =>
                    onCell({ row: "minStay", roomTypeId: room.id, date: day.date, minStay: day.min_stay })
                  }
                  className={`${cellButton} ${faded(day)}`}
                >
                  {day.min_stay ?? <span className="text-muted-foreground">–</span>}
                </button>
              </td>
            ))}
          </tr>
        </tbody>
      </table>
      {room.rate_plans.length === 0 && (
        <p className="border-t border-border px-3 py-2 text-sm text-muted-foreground">
          {t("calendar.noPlan")}
        </p>
      )}
    </div>
  );
}

/** One table per room type: availability, a price row per rate plan, minimum stay. */
export function CalendarGrid({ calendar, onCell }: CalendarGridProps) {
  return (
    <div className="space-y-4">
      {calendar.room_types.map((room) => (
        <RoomTable key={room.id} room={room} calendar={calendar} onCell={onCell} />
      ))}
    </div>
  );
}
