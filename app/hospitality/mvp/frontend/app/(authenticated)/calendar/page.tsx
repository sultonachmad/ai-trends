"use client";

/**
 * Calendar — availability, prices, closed dates and minimum stay by date.
 * Reachable at `/calendar`. Room types and rate plans are set up on `/rooms`.
 */

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  CalendarChangeDialog,
  type ChangeDraft,
} from "@/components/calendar/CalendarChangeDialog";
import { CalendarGrid, type CellTarget } from "@/components/calendar/CalendarGrid";
import { LanguageSwitch } from "@/components/LanguageSwitch";
import { fetchCalendar, type Calendar } from "@/lib/calendar-api";
import {
  addDays,
  nextStart,
  previousStart,
  todayIn,
  WIDE_WINDOW_DAYS,
  windowSize,
} from "@/lib/calendar-grid";
import { useLocale } from "@/lib/locale-store";
import { numberSetting } from "@/lib/room-forms";
import { fetchOnboardingStatus, fetchWorkspace, type Workspace } from "@/lib/workspace-api";

const ONBOARDING_PATH = "/onboarding";
const navButton = "rounded-md border border-border bg-card px-3 py-1.5 text-sm hover:bg-accent";
const errorText = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));

const subscribeToResize = (notify: () => void) => {
  window.addEventListener("resize", notify);
  return () => window.removeEventListener("resize", notify);
};

function draftFor(target: CellTarget): ChangeDraft {
  const base = { start: target.date, end: target.date, roomTypeIds: [target.roomTypeId] };
  if (target.row === "availability") return { ...base, kind: target.closed ? "open" : "close" };
  if (target.row === "minStay") {
    return { ...base, kind: "set_min_stay", nights: String(target.minStay ?? 2) };
  }
  return {
    ...base,
    kind: "set_price",
    ratePlanId: target.ratePlanId,
    amount: String(Math.trunc(Number(target.amount))),
  };
}

export default function CalendarPage() {
  const router = useRouter();
  const { t } = useLocale();
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [calendar, setCalendar] = useState<Calendar | null>(null);
  const [start, setStart] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [readError, setReadError] = useState<string | null>(null);
  const [draft, setDraft] = useState<ChangeDraft | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const days = useSyncExternalStore(
    subscribeToResize,
    () => windowSize(window.innerWidth),
    () => WIDE_WINDOW_DAYS,
  );
  const readRequest = useRef(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const status = await fetchOnboardingStatus();
        if (cancelled) return;
        if (!status.has_workspace) {
          router.replace(ONBOARDING_PATH);
          return;
        }
        const loaded = await fetchWorkspace();
        if (cancelled) return;
        setWorkspace(loaded);
        setStart(todayIn(loaded.property.timezone));
      } catch (cause) {
        if (!cancelled) setLoadError(errorText(cause));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  const read = useCallback(async () => {
    if (start === null) return;
    const request = ++readRequest.current;
    try {
      const loaded = await fetchCalendar(start, addDays(start, days - 1));
      if (request !== readRequest.current) return; // a newer window was asked for meanwhile
      setCalendar(loaded);
      setReadError(null);
    } catch (cause) {
      if (request === readRequest.current) setReadError(errorText(cause));
    }
  }, [start, days]);

  useEffect(() => {
    void read();
  }, [read]);

  if (loadError) {
    return (
      <p role="alert" className="p-8 text-sm text-destructive">
        {t("common.loadFailed", { reason: loadError })}
      </p>
    );
  }
  if (!workspace || start === null || (!calendar && !readError)) {
    return <p className="p-8 text-sm text-muted-foreground">{t("common.loading")}</p>;
  }

  const settings = workspace.settings;
  const move = (to: string) => {
    setDone(null);
    setStart(to);
  };
  const blankDraft = (): ChangeDraft => ({
    start: calendar?.today ?? start,
    end: calendar?.today ?? start,
    roomTypeIds: calendar?.room_types.map((room) => room.id) ?? [],
    kind: "set_price",
    ratePlanId: calendar?.room_types.flatMap((room) => room.rate_plans)[0]?.id,
  });

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">{t("calendar.title")}</h1>
        <LanguageSwitch />
      </div>
      {readError && (
        <p role="alert" className="text-sm text-destructive">
          {t("common.loadFailed", { reason: readError })}
        </p>
      )}
      {calendar && calendar.room_types.length === 0 && (
        <p className="rounded-xl border border-border bg-card p-6 text-sm">
          {t("calendar.needSetup")}{" "}
          <Link href="/rooms" className="font-medium text-primary hover:underline">
            {t("calendar.goToRooms")}
          </Link>
        </p>
      )}
      {calendar && calendar.room_types.length > 0 && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => move(previousStart(start, days))} className={navButton}>
                ← {t("calendar.prev")}
              </button>
              <button type="button" onClick={() => move(calendar.today)} className={navButton}>
                {t("calendar.today")}
              </button>
              <button type="button" onClick={() => move(nextStart(start, days))} className={navButton}>
                {t("calendar.next")} →
              </button>
            </div>
            <button
              type="button"
              onClick={() => setDraft(blankDraft())}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              {t("calendar.changeMany")}
            </button>
          </div>
          {done && (
            <p role="status" className="text-sm font-medium">
              {done}
            </p>
          )}
          <CalendarGrid calendar={calendar} onCell={(target) => setDraft(draftFor(target))} />
          <ul className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted-foreground">
            <li>
              <span className="mr-1 inline-block h-3 w-3 rounded-sm bg-primary/10 align-middle ring-1 ring-border" />
              {t("calendar.legend.today")}
            </li>
            <li>
              <span className="mr-1 font-bold text-foreground underline decoration-dotted">750rb</span>
              {t("calendar.legend.changed")}
            </li>
            <li>
              <span className="mr-1 rounded bg-destructive/15 px-1 text-[0.65rem] font-semibold text-destructive">
                {t("calendar.closed")}
              </span>
              {t("calendar.legend.closed")}
            </li>
          </ul>
          <CalendarChangeDialog
            open={draft !== null}
            draft={draft ?? blankDraft()}
            calendar={calendar}
            bounds={{
              min: numberSetting(settings, "room_rate_min_amount_idr", 10_000),
              max: numberSetting(settings, "room_rate_max_amount_idr", 500_000_000),
            }}
            maxDays={numberSetting(settings, "calendar_max_change_days", 365)}
            onClose={() => setDraft(null)}
            onApplied={(result) => {
              setDraft(null);
              setDone(t("calendar.done", { dates: result.dates, rooms: result.room_types }));
              void read();
            }}
          />
        </>
      )}
    </div>
  );
}
