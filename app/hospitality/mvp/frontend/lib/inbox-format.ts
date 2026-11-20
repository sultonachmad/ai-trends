/**
 * Pure helpers for the inbox: merging fresh data into what is on screen, and
 * showing times. No React, no network — covered by inbox-format.test.ts.
 */

import type { Locale } from "@/lib/i18n";

const INTL_LOCALE: Record<Locale, string> = { id: "id-ID", en: "en-GB" };
const DAY_MS = 24 * 60 * 60 * 1000;

interface HasId {
  id: string;
}

/** Fresh rows replace rows with the same id; rows only in `current` are kept. */
function mergeById<T extends HasId>(current: readonly T[], fresh: readonly T[]): T[] {
  const freshIds = new Set(fresh.map((row) => row.id));
  return [...fresh, ...current.filter((row) => !freshIds.has(row.id))];
}

/** Conversations with newest activity first, after merging a freshly fetched page. */
export function mergeConversations<T extends HasId & { last_message_at: string | null }>(
  current: readonly T[],
  fresh: readonly T[],
): T[] {
  return mergeById(current, fresh).sort((a, b) =>
    (b.last_message_at ?? "").localeCompare(a.last_message_at ?? ""),
  );
}

/**
 * Apply a freshly fetched first page to the list on screen.
 *
 * The first page is the truth for everything at least as recent as its oldest row:
 * a row on screen in that range but missing from `fresh` has left the list (resolved,
 * reopened elsewhere) and is dropped. Older rows, loaded with "show older", are kept.
 * When the server has no further page, `fresh` is the whole list.
 */
export function applyFirstPage<T extends HasId & { last_message_at: string | null }>(
  current: readonly T[],
  fresh: readonly T[],
  hasMore: boolean,
): T[] {
  if (!hasMore || fresh.length === 0) return [...fresh];
  const oldestFresh = fresh[fresh.length - 1].last_message_at ?? "";
  const freshIds = new Set(fresh.map((row) => row.id));
  const older = current.filter(
    (row) => !freshIds.has(row.id) && (row.last_message_at ?? "") < oldestFresh,
  );
  return [...fresh, ...older];
}

interface ConversationState {
  id: string;
  status: string;
  unread_count: number;
  last_message_at: string | null;
  reply_blocked_reason: string | null;
  guest: { name: string; phone: string | null };
}

/** True when nothing a person can see differs — lets the screen skip a re-render. */
export function sameConversation(a: ConversationState, b: ConversationState): boolean {
  return (
    a.id === b.id &&
    a.status === b.status &&
    a.unread_count === b.unread_count &&
    a.last_message_at === b.last_message_at &&
    a.reply_blocked_reason === b.reply_blocked_reason &&
    a.guest.name === b.guest.name &&
    a.guest.phone === b.guest.phone
  );
}

/** Messages oldest first, appending only ones not already shown. */
export function mergeMessages<T extends HasId & { created_at: string }>(
  current: readonly T[],
  fresh: readonly T[],
): T[] {
  const known = new Set(current.map((message) => message.id));
  const added = fresh.filter((message) => !known.has(message.id));
  if (added.length === 0) return current as T[];
  return [...current, ...added].sort((a, b) => a.created_at.localeCompare(b.created_at));
}

function dayKey(date: Date, timeZone?: string): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

/** Whole calendar days between two instants in `timeZone` (0 = same day). */
export function daysApart(earlier: Date, later: Date, timeZone?: string): number {
  const toUtcMidnight = (date: Date) => Date.parse(`${dayKey(date, timeZone)}T00:00:00Z`);
  return Math.round((toUtcMidnight(later) - toUtcMidnight(earlier)) / DAY_MS);
}

/** Clock time, e.g. 14:05. */
export function formatClock(iso: string, locale: Locale, timeZone?: string): string {
  return new Intl.DateTimeFormat(INTL_LOCALE[locale], {
    timeZone,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(iso));
}

/** Short date, e.g. 3 Nov. */
export function formatShortDate(iso: string, locale: Locale, timeZone?: string): string {
  return new Intl.DateTimeFormat(INTL_LOCALE[locale], {
    timeZone,
    day: "numeric",
    month: "short",
  }).format(new Date(iso));
}

/** For the conversation list: the time today, otherwise the date. */
export function formatListTime(
  iso: string | null,
  locale: Locale,
  now: Date = new Date(),
  timeZone?: string,
): string {
  if (!iso) return "";
  return daysApart(new Date(iso), now, timeZone) === 0
    ? formatClock(iso, locale, timeZone)
    : formatShortDate(iso, locale, timeZone);
}

export type DayLabel = { kind: "today" } | { kind: "yesterday" } | { kind: "date"; text: string };

/** Heading shown above the first message of each day in a thread. */
export function dayLabel(
  iso: string,
  locale: Locale,
  now: Date = new Date(),
  timeZone?: string,
): DayLabel {
  const apart = daysApart(new Date(iso), now, timeZone);
  if (apart === 0) return { kind: "today" };
  if (apart === 1) return { kind: "yesterday" };
  return { kind: "date", text: formatShortDate(iso, locale, timeZone) };
}

/** True when `message` starts a new calendar day compared with the one before it. */
export function startsNewDay(
  previousIso: string | null,
  currentIso: string,
  timeZone?: string,
): boolean {
  if (previousIso === null) return true;
  return daysApart(new Date(previousIso), new Date(currentIso), timeZone) !== 0;
}
