/** Pure helpers for the channel report. Dates are "YYYY-MM-DD" at the property. */

export const PERIOD_PRESETS = ["this_month", "last_month", "last_30"] as const;
export type PeriodPreset = (typeof PERIOD_PRESETS)[number];
export const MAX_REPORT_DAYS = 366;

const DAY_MS = 86_400_000;
const utc = (iso: string) => Date.parse(`${iso}T00:00:00Z`);
const isoOf = (ms: number) => new Date(ms).toISOString().slice(0, 10);

/** Today's date in a time zone. */
export function todayIn(timeZone: string, now: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone }).format(now);
}

export function periodFor(preset: PeriodPreset, today: string): { from: string; to: string } {
  const [year, month] = today.split("-").map(Number);
  if (preset === "last_30") return { from: isoOf(utc(today) - 29 * DAY_MS), to: today };
  if (preset === "last_month") {
    return {
      from: isoOf(Date.UTC(year, month - 2, 1)),
      to: isoOf(Date.UTC(year, month - 1, 0)),
    };
  }
  return { from: isoOf(Date.UTC(year, month - 1, 1)), to: isoOf(Date.UTC(year, month, 0)) };
}

/** i18n key of what is wrong with a custom period, or null. */
export function periodProblem(from: string, to: string): string | null {
  if (!from || !to) return "reports.period.needDates";
  if (to < from) return "reports.period.reversed";
  if ((utc(to) - utc(from)) / DAY_MS + 1 > MAX_REPORT_DAYS) return "reports.period.tooLong";
  return null;
}

/** A bar width that stays between 0 and 100 whatever the server sends. */
export function barWidth(share: string): string {
  const value = Number(share);
  return `${Number.isFinite(value) ? Math.min(Math.max(value, 0), 100) : 0}%`;
}

export function percentLabel(value: string): string {
  return `${value.replace(".", ",")}%`;
}
