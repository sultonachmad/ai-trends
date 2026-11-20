/**
 * Pure helpers for the calendar screen: date windows, cell states, form checks.
 *
 * Dates are the property's local calendar dates as "YYYY-MM-DD" strings. All maths is
 * done in UTC on those strings, so the viewer's own timezone never shifts a date.
 */

import type { Locale } from "@/lib/i18n";
import type { CalendarDay } from "@/lib/calendar-api";

const MS_PER_DAY = 86_400_000;
const LOCALE_TAGS: Record<Locale, string> = { id: "id-ID", en: "en-GB" };
export const WIDE_WINDOW_DAYS = 14;
export const NARROW_WINDOW_DAYS = 7;
export const NARROW_SCREEN_PX = 768;
export const MAX_MIN_STAY = 365;
/** Monday-first, matching the server (0 = Monday … 6 = Sunday). */
export const WEEKDAYS: readonly number[] = [0, 1, 2, 3, 4, 5, 6];
const SATURDAY = 5;

const toUtc = (iso: string) => new Date(`${iso}T00:00:00Z`);
const toIso = (date: Date) => date.toISOString().slice(0, 10);

export function addDays(iso: string, days: number): string {
  return toIso(new Date(toUtc(iso).getTime() + days * MS_PER_DAY));
}

/** `count` consecutive dates starting at `start`. */
export function windowDates(start: string, count: number): string[] {
  return Array.from({ length: count }, (_, offset) => addDays(start, offset));
}

/** Days from `from` to `to` (negative when `to` is earlier). */
export function daysBetween(from: string, to: string): number {
  return Math.round((toUtc(to).getTime() - toUtc(from).getTime()) / MS_PER_DAY);
}

/** 0 = Monday … 6 = Sunday. */
export function weekdayIndex(iso: string): number {
  return (toUtc(iso).getUTCDay() + 6) % 7;
}

export function isWeekend(iso: string): boolean {
  return weekdayIndex(iso) >= SATURDAY;
}

export function windowSize(screenWidth: number): number {
  return screenWidth < NARROW_SCREEN_PX ? NARROW_WINDOW_DAYS : WIDE_WINDOW_DAYS;
}

export interface DayHeading {
  weekday: string;
  day: string;
  month: string;
}

/** Short heading parts for a date column ("Jum", "20", "Nov"). */
export function dayHeading(iso: string, locale: Locale): DayHeading {
  const part = (options: Intl.DateTimeFormatOptions) =>
    new Intl.DateTimeFormat(LOCALE_TAGS[locale], { ...options, timeZone: "UTC" }).format(toUtc(iso));
  return {
    weekday: part({ weekday: "short" }),
    day: part({ day: "numeric" }),
    month: part({ month: "short" }),
  };
}

/** A full date for sentences and labels ("Jumat, 20 November 2026"). */
export function longDate(iso: string, locale: Locale): string {
  return new Intl.DateTimeFormat(LOCALE_TAGS[locale], {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(toUtc(iso));
}

/** Name of a weekday by server index, short ("Sen") or long ("Senin"). */
export function weekdayName(index: number, locale: Locale, width: "short" | "long" = "short"): string {
  // 2024-01-01 was a Monday.
  return new Intl.DateTimeFormat(LOCALE_TAGS[locale], { weekday: width, timeZone: "UTC" }).format(
    toUtc(addDays("2024-01-01", index)),
  );
}

export type CellState = "past" | "locked" | "closed" | "open";

/** past = before today; locked = beyond the last date that can be changed yet. */
export function cellState(day: Pick<CalendarDay, "date" | "closed">, today: string, lastEditable: string): CellState {
  if (day.date < today) return "past";
  if (day.date > lastEditable) return "locked";
  return day.closed ? "closed" : "open";
}

export function isEditable(date: string, today: string, lastEditable: string): boolean {
  return date >= today && date <= lastEditable;
}

/** The earliest window start that still shows today as its first editable column. */
export function previousStart(start: string, size: number): string {
  return addDays(start, -size);
}

export function nextStart(start: string, size: number): string {
  return addDays(start, size);
}

export interface RangeForm {
  start: string;
  end: string;
  roomTypeIds: string[];
  weekdays: number[];
}

/** i18n key of what is wrong with a date range and selection, or null when it is fine. */
export function rangeProblem(form: RangeForm, today: string, lastEditable: string, maxDays: number): string | null {
  if (!form.start || !form.end) return "calendar.form.needDates";
  if (form.end < form.start) return "calendar.form.reversed";
  if (form.start < today) return "calendar.form.past";
  if (form.end > lastEditable) return "calendar.form.beyond";
  if (daysBetween(form.start, form.end) + 1 > maxDays) return "calendar.form.tooLong";
  if (form.roomTypeIds.length === 0) return "calendar.form.needRoom";
  if (form.weekdays.length === 0) return "calendar.form.needWeekday";
  const matches = windowDates(form.start, daysBetween(form.start, form.end) + 1).some((date) =>
    form.weekdays.includes(weekdayIndex(date)),
  );
  return matches ? null : "calendar.form.noMatch";
}

/** Whole nights from what a person typed (1…365), or null. */
export function parseNights(input: string): number | null {
  if (!/^\d{1,3}$/.test(input.trim())) return null;
  const nights = Number(input.trim());
  return nights >= 1 && nights <= MAX_MIN_STAY ? nights : null;
}

/** `weekdays` for the request: omitted when every day is chosen. */
export function weekdaysForRequest(weekdays: number[]): number[] | undefined {
  return weekdays.length === WEEKDAYS.length ? undefined : [...weekdays].sort((a, b) => a - b);
}

const THOUSAND = 1_000;
const MILLION = 1_000_000;
const COMPACT_UNITS: Record<Locale, { thousand: string; million: string; decimal: string }> = {
  id: { thousand: "rb", million: "jt", decimal: "," },
  en: { thousand: "k", million: "m", decimal: "." },
};

/** A price short enough for a calendar cell: "750rb", "1,25jt" (id) or "750k", "1.25m" (en). */
export function compactRupiah(value: number | string, locale: Locale): string {
  const amount = Math.trunc(Number(value));
  if (!Number.isFinite(amount)) return "";
  const unit = COMPACT_UNITS[locale];
  const scaled = (divisor: number, suffix: string) => {
    const text = (Math.round((amount / divisor) * 100) / 100).toString().replace(".", unit.decimal);
    return `${text}${suffix}`;
  };
  if (amount >= MILLION) return scaled(MILLION, unit.million);
  if (amount >= THOUSAND) return scaled(THOUSAND, unit.thousand);
  return String(amount);
}

/** Today's date where the property is, falling back to the viewer's own date. */
export function todayIn(timeZone: string, now: Date = new Date()): string {
  try {
    return new Intl.DateTimeFormat("en-CA", { timeZone }).format(now);
  } catch {
    return new Intl.DateTimeFormat("en-CA").format(now);
  }
}
