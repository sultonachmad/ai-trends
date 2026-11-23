"use client";

/** Channel report — bookings, nights, revenue, commission and net revenue by source. */

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { LanguageSwitch } from "@/components/LanguageSwitch";
import { ChannelReportTable } from "@/components/reports/ChannelReportTable";
import { ApiError } from "@/lib/api-client";
import { useLocale } from "@/lib/locale-store";
import { fetchChannelReport, type ChannelReport } from "@/lib/reports-api";
import {
  PERIOD_PRESETS,
  periodFor,
  periodProblem,
  todayIn,
  type PeriodPreset,
} from "@/lib/report-format";
import { fetchOnboardingStatus, fetchWorkspace } from "@/lib/workspace-api";

const cardClass = "rounded-xl border border-border bg-card p-4 text-card-foreground shadow-sm";
const inputClass =
  "rounded-md border border-border bg-card px-3 py-2 text-sm text-card-foreground focus:outline-none focus:ring-2 focus:ring-primary";
const FORBIDDEN = 403;
const errorText = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));

export default function ReportsPage() {
  const router = useRouter();
  const { t } = useLocale();
  const [today, setToday] = useState<string | null>(null);
  const [preset, setPreset] = useState<PeriodPreset | "custom">("this_month");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [report, setReport] = useState<ChannelReport | null>(null);
  const [noAccess, setNoAccess] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const status = await fetchOnboardingStatus();
        if (cancelled) return;
        if (!status.has_workspace) {
          router.replace("/onboarding");
          return;
        }
        const workspace = await fetchWorkspace();
        if (cancelled) return;
        const now = todayIn(workspace.property.timezone);
        const period = periodFor("this_month", now);
        setToday(now);
        setFrom(period.from);
        setTo(period.to);
      } catch (cause) {
        if (!cancelled) setError(errorText(cause));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  const problem = today ? periodProblem(from, to) : null;

  useEffect(() => {
    if (!today) return;
    // Figures on screen always belong to the period shown, so clear them first.
    const id = ++requestId.current;
    setReport(null);
    setError(null);
    if (problem) {
      setLoading(false);
      return;
    }
    setLoading(true);
    fetchChannelReport(from, to)
      .then((found) => {
        if (id === requestId.current) setReport(found);
      })
      .catch((cause) => {
        if (id !== requestId.current) return;
        if (cause instanceof ApiError && cause.status === FORBIDDEN) setNoAccess(true);
        else setError(errorText(cause));
      })
      .finally(() => {
        if (id === requestId.current) setLoading(false);
      });
  }, [today, from, to, problem]);

  const choose = (next: PeriodPreset) => {
    if (!today) return;
    const period = periodFor(next, today);
    setPreset(next);
    setFrom(period.from);
    setTo(period.to);
  };

  if (noAccess) {
    return <p role="alert" className="p-8 text-sm">{t("reports.noAccess")}</p>;
  }
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">{t("reports.title")}</h1>
        <LanguageSwitch />
      </div>
      <p className="max-w-3xl text-sm text-muted-foreground">{t("reports.intro")}</p>
      <section className={`${cardClass} space-y-3`} aria-label={t("reports.periodLabel")}>
        <div className="flex flex-wrap gap-2">
          {PERIOD_PRESETS.map((name) => (
            <button
              key={name}
              type="button"
              aria-pressed={preset === name}
              onClick={() => choose(name)}
              className={`min-h-10 rounded-md border px-3 py-1 text-sm ${
                preset === name
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border hover:bg-accent"
              }`}
            >
              {t(`reports.preset.${name}`)}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="report-from" className="mb-1 block text-sm font-medium">
              {t("reports.from")}
            </label>
            <input
              id="report-from"
              type="date"
              value={from}
              onChange={(event) => {
                setPreset("custom");
                setFrom(event.target.value);
              }}
              className={inputClass}
            />
          </div>
          <div>
            <label htmlFor="report-to" className="mb-1 block text-sm font-medium">
              {t("reports.to")}
            </label>
            <input
              id="report-to"
              type="date"
              value={to}
              onChange={(event) => {
                setPreset("custom");
                setTo(event.target.value);
              }}
              className={inputClass}
            />
          </div>
        </div>
        {problem && (
          <p role="alert" className="text-sm text-destructive">
            {t(problem)}
          </p>
        )}
      </section>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {t("common.loadFailed", { reason: error })}
        </p>
      )}
      <section className={cardClass} aria-busy={loading} aria-label={t("reports.title")}>
        {problem || error ? (
          <p className="text-sm text-muted-foreground">{t("reports.noFigures")}</p>
        ) : !report ? (
          <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
        ) : report.rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("reports.empty")}</p>
        ) : (
          <ChannelReportTable report={report} />
        )}
      </section>
      <p className="max-w-3xl text-xs text-muted-foreground">{t("reports.notes")}</p>
    </div>
  );
}
