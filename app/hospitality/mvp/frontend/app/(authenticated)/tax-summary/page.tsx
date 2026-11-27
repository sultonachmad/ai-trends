"use client";

/** Monthly tax — service charge and PBJT of a month, from the guest bills, with downloads. */

import { useCallback, useEffect, useRef, useState } from "react";

import { LanguageSwitch } from "@/components/LanguageSwitch";
import { TaxMonthView } from "@/components/reports/TaxMonthView";
import { ApiError } from "@/lib/api-client";
import { useLocale } from "@/lib/locale-store";
import { monthOf, shiftMonth } from "@/lib/maintenance-format";
import { todayIn } from "@/lib/report-format";
import { downloadTaxFile, fetchTaxMonth, type TaxMonth } from "@/lib/tax-summary-api";
import { fetchWorkspace } from "@/lib/workspace-api";

const FORBIDDEN = 403;
const button = "min-h-11 rounded-md border border-border px-3 py-2 text-sm hover:bg-accent disabled:opacity-50";

export default function TaxSummaryPage() {
  const { t } = useLocale();
  const [month, setMonth] = useState<string | null>(null);
  const [summary, setSummary] = useState<TaxMonth | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [noAccess, setNoAccess] = useState(false);
  const requestId = useRef(0);

  useEffect(() => {
    fetchWorkspace()
      .then((workspace) => setMonth(monthOf(todayIn(workspace.property.timezone))))
      .catch(() => setError(t("tax.loadError")));
  }, [t]);

  const load = useCallback(
    async (chosen: string) => {
      const id = ++requestId.current;
      setError(null);
      try {
        const found = await fetchTaxMonth(chosen);
        if (id === requestId.current) setSummary(found);
      } catch (cause) {
        if (id !== requestId.current) return;
        if (cause instanceof ApiError && cause.status === FORBIDDEN) setNoAccess(true);
        else setError(t("tax.loadError"));
      }
    },
    [t],
  );
  useEffect(() => {
    if (month) void load(month);
  }, [month, load]);

  const download = async (kind: "days" | "bookings") => {
    if (!month) return;
    setBusy(true);
    try {
      const url = URL.createObjectURL(await downloadTaxFile(month, kind));
      const link = document.createElement("a");
      link.href = url;
      link.download = `tax-${month}-${kind}.csv`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch {
      setError(t("tax.loadError"));
    } finally {
      setBusy(false);
    }
  };

  if (noAccess) return <p role="alert" className="p-8 text-sm">{t("frontdesk.noAccess")}</p>;
  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{t("tax.title")}</h1>
          <p className="text-sm text-muted-foreground">{t("tax.subtitle")}</p>
        </div>
        <LanguageSwitch />
      </div>
      {month && (
        <div className="flex flex-wrap items-end gap-2">
          <button type="button" onClick={() => setMonth(shiftMonth(month, -1))} className={button} aria-label={t("tax.prev")}>
            ‹
          </button>
          <label className="space-y-1 text-sm">
            <span className="block">{t("tax.month")}</span>
            <input
              type="month"
              value={month}
              onChange={(e) => e.target.value && setMonth(e.target.value)}
              className="min-h-11 rounded-md border border-border bg-background px-3"
            />
          </label>
          <button type="button" onClick={() => setMonth(shiftMonth(month, 1))} className={button} aria-label={t("tax.next")}>
            ›
          </button>
        </div>
      )}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {!summary ? (
        <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
      ) : !summary.is_set ? (
        <p role="status" className="rounded-lg bg-accent px-3 py-2 text-sm text-accent-foreground">{t("tax.notSet")}</p>
      ) : (
        <>
          <p
            role="status"
            className={`rounded-lg px-3 py-2 text-sm ${
              summary.draft ? "bg-destructive/10 text-destructive" : "bg-primary/10 text-primary"
            }`}
          >
            {summary.draft
              ? t("tax.draft", { closed: summary.closed_days, days: summary.days_in_month })
              : t("tax.final")}
          </p>
          <TaxMonthView month={summary} />
          <div className="flex flex-wrap gap-2">
            <button type="button" disabled={busy} onClick={() => void download("days")} className={button}>
              {t("tax.download.days")}
            </button>
            <button type="button" disabled={busy} onClick={() => void download("bookings")} className={button}>
              {t("tax.download.bookings")}
            </button>
          </div>
          <p className="text-xs text-muted-foreground">{t("tax.basis")}</p>
          <p className="text-xs text-muted-foreground">{t("tax.verify")}</p>
        </>
      )}
    </div>
  );
}
