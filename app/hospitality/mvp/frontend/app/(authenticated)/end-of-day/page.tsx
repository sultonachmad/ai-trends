"use client";

/** End of day: what still needs attention, the day's figures, cash drawers, close or reopen. */

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { DaySummaryView } from "@/components/end-of-day/DaySummaryView";
import { LanguageSwitch } from "@/components/LanguageSwitch";
import { inputClass } from "@/components/rooms/RoomTypeDialog";
import { ApiError } from "@/lib/api-client";
import { shortDate } from "@/lib/booking-format";
import { closeDay, fetchDay, reopenDay, type DayCheck, type DayRead } from "@/lib/end-of-day-api";
import { blockingChecks, dayBefore, problemOf, type Problem } from "@/lib/end-of-day-format";
import { formatClock, formatShortDate } from "@/lib/inbox-format";
import { useLocale } from "@/lib/locale-store";
import { useCan } from "@/lib/rbac-store";
import { todayIn } from "@/lib/report-format";

const FORBIDDEN = 403;
const REASON_MIN = 3;
const secondary =
  "min-h-11 rounded-md border border-border px-4 py-2 text-sm hover:bg-accent disabled:opacity-50";
const primary =
  "min-h-11 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50";
const LINKS: Record<string, string> = {
  arrivals_pending: "/front-desk",
  departures_pending: "/front-desk",
  drawers_open: "/front-desk",
  proofs_waiting: "/transfer-proofs",
  apoa_overdue: "/apoa",
};

function Checklist({ checks }: { checks: DayCheck[] }) {
  const { t } = useLocale();
  if (checks.length === 0) return <p className="text-sm text-muted-foreground">{t("endofday.allClear")}</p>;
  return (
    <ul className="space-y-2">
      {checks.map((check) => (
        <li
          key={check.code}
          className={`rounded-lg border p-3 text-sm ${
            check.level === "blocking" ? "border-destructive bg-destructive/10" : "border-border bg-accent/40"
          }`}
        >
          <p className="text-xs font-medium uppercase tracking-wide">
            {t(check.level === "blocking" ? "endofday.blocking" : "endofday.warning")}
          </p>
          <p className="font-medium">{t(`endofday.check.${check.code}`, { count: check.count })}</p>
          {check.items.length > 0 && (
            <ul className="mt-1 list-disc pl-5 text-xs">
              {check.items.map((item) => (
                <li key={`${item.booking_id ?? ""}-${item.label}`}>{item.label}</li>
              ))}
            </ul>
          )}
          {LINKS[check.code] && (
            <Link href={LINKS[check.code]} className="mt-1 inline-block text-xs underline">
              {t("endofday.goFix")}
            </Link>
          )}
        </li>
      ))}
    </ul>
  );
}

function EndOfDay() {
  const { t, locale } = useLocale();
  const params = useSearchParams();
  const canEdit = useCan("endofday:edit");
  const canOverride = useCan("bookings:edit");
  const browserToday = todayIn(Intl.DateTimeFormat().resolvedOptions().timeZone);
  const [date, setDate] = useState(params.get("date") ?? dayBefore(browserToday));
  const [day, setDay] = useState<DayRead | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [noAccess, setNoAccess] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const request = useRef(0);

  useEffect(() => {
    const ticket = ++request.current;
    setDay(null);
    setReason("");
    setProblem(null);
    fetchDay(date)
      .then((found) => {
        if (ticket === request.current) setDay(found);
      })
      .catch((cause) => {
        if (ticket !== request.current) return;
        if (cause instanceof ApiError && cause.status === FORBIDDEN) setNoAccess(true);
        else setProblem(problemOf(cause));
      });
  }, [date]);

  if (noAccess) return <p role="alert" className="p-8 text-sm">{t("endofday.noAccess")}</p>;
  const today = day?.today ?? browserToday; // the property's date once known
  const blocking = day ? blockingChecks(day.checks) : [];

  const act = async (call: () => Promise<DayRead>) => {
    const ticket = request.current; // a reply for another date is dropped
    setBusy(true);
    setProblem(null);
    try {
      const changed = await call();
      if (ticket !== request.current) return;
      setDay(changed);
      setReason("");
    } catch (cause) {
      if (ticket === request.current) setProblem(problemOf(cause));
    } finally {
      setBusy(false);
    }
  };
  const close = () => {
    if (blocking.length > 0 && reason.trim().length < REASON_MIN) {
      return setProblem({ key: "endofday.needReason" });
    }
    void act(() => closeDay(date, blocking.length > 0 ? reason.trim() : null));
  };
  const reopen = () => {
    if (reason.trim().length < REASON_MIN) return setProblem({ key: "endofday.needReason" });
    void act(() => reopenDay(date, reason.trim()));
  };
  const mayClose = blocking.length === 0 || canOverride;

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">{t("endofday.title")}</h1>
        <LanguageSwitch />
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor="eod-date" className="mb-1 block text-sm font-medium">{t("endofday.date")}</label>
          <input id="eod-date" type="date" value={date} max={today} onChange={(e) => e.target.value && setDate(e.target.value)} className={inputClass} />
        </div>
        {day && (
          <p className="text-sm">
            {shortDate(day.date, locale)} ·{" "}
            {day.status === "closed" && day.closed_at
              ? t("endofday.status.closed", {
                  by: day.closed_by ?? "-",
                  when: `${formatShortDate(day.closed_at, locale)} ${formatClock(day.closed_at, locale)}`,
                })
              : t("endofday.status.open")}
          </p>
        )}
      </div>
      {!day && !problem && <p className="text-sm text-muted-foreground">{t("common.loading")}</p>}
      {day && day.status === "open" && (
        <section aria-labelledby="eod-checks" className="space-y-2">
          <h2 id="eod-checks" className="text-lg font-semibold">{t("endofday.checks")}</h2>
          {day.date >= today ? <p className="text-sm">{t("endofday.notOver")}</p> : <Checklist checks={day.checks} />}
        </section>
      )}
      {day && canEdit && ((day.can_close && mayClose) || day.status === "closed") && (
        <div className="space-y-2 rounded-lg border border-border bg-card p-3 text-sm">
          {(day.status === "closed" || blocking.length > 0) && (
            <>
              <label htmlFor="eod-reason" className="block font-medium">
                {t(day.status === "closed" ? "endofday.reopenReason" : "endofday.overrideReason")}
              </label>
              <input id="eod-reason" maxLength={300} value={reason} onChange={(e) => setReason(e.target.value)} className={inputClass} />
            </>
          )}
          {day.status === "closed" ? (
            <button type="button" disabled={busy} onClick={reopen} className={secondary}>{t("endofday.reopen")}</button>
          ) : (
            <button type="button" disabled={busy} onClick={close} className={primary}>
              {t(blocking.length > 0 ? "endofday.closeAnyway" : "endofday.close")}
            </button>
          )}
        </div>
      )}
      {problem && (
        <p role="alert" className="text-sm text-destructive">
          {"key" in problem ? t(problem.key) : problem.text}
        </p>
      )}
      {day && (
        <section aria-labelledby="eod-summary" className="space-y-2">
          <h2 id="eod-summary" className="text-lg font-semibold">{t("endofday.summary")}</h2>
          <DaySummaryView summary={day.summary} drawers={day.drawers} />
        </section>
      )}
    </div>
  );
}

export default function EndOfDayPage() {
  // useSearchParams needs a Suspense boundary to build.
  return (
    <Suspense fallback={null}>
      <EndOfDay />
    </Suspense>
  );
}
