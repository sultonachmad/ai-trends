"use client";

import { sourceLabelKey } from "@/lib/booking-format";
import { useLocale } from "@/lib/locale-store";
import { formatRupiah } from "@/lib/money";
import type { ChannelReport, ReportFigures, ReportRow } from "@/lib/reports-api";
import { barWidth, percentLabel } from "@/lib/report-format";

const cell = "px-3 py-2 text-right tabular-nums";
const head = "px-3 py-2 text-right font-medium";

function Figures({ figures }: { figures: ReportFigures }) {
  return (
    <>
      <td className={cell}>{figures.bookings}</td>
      <td className={cell}>{figures.nights}</td>
      <td className={cell}>{formatRupiah(figures.revenue)}</td>
      <td className={cell}>{formatRupiah(figures.average_per_night)}</td>
      <td className={cell}>{percentLabel(figures.cancellation_rate)}</td>
      <td className={cell}>{formatRupiah(figures.commission)}</td>
      <td className={`${cell} font-semibold`}>{formatRupiah(figures.net_revenue)}</td>
    </>
  );
}

function PhoneFigures({ figures }: { figures: ReportFigures }) {
  const { t } = useLocale();
  const items: [string, string][] = [
    [t("reports.col.bookings"), String(figures.bookings)],
    [t("reports.col.nights"), String(figures.nights)],
    [t("reports.col.revenue"), formatRupiah(figures.revenue)],
    [t("reports.col.average"), formatRupiah(figures.average_per_night)],
    [t("reports.col.cancelled"), percentLabel(figures.cancellation_rate)],
    [t("reports.col.commission"), formatRupiah(figures.commission)],
    [t("reports.col.net"), formatRupiah(figures.net_revenue)],
  ];
  return (
    <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-sm">
      {items.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="text-muted-foreground">{label}</dt>
          <dd className="text-right tabular-nums">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Production by source: a table on wide screens, cards on a phone. */
export function ChannelReportTable({ report }: { report: ChannelReport }) {
  const { t } = useLocale();
  const nameOf = (row: ReportRow) =>
    row.is_direct ? t(sourceLabelKey(row.code)) : row.name;
  const summaries: [string, ReportFigures][] = [
    [t("reports.direct"), report.direct],
    [t("reports.channels"), report.channels],
    [t("reports.total"), report.total],
  ];
  return (
    <>
      <ul className="space-y-3 md:hidden">
        {report.rows.map((row) => (
          <li key={row.code} className="space-y-2 rounded-lg border border-border p-3">
            <p className="font-semibold">{nameOf(row)}</p>
            <div className="h-2 rounded bg-muted" aria-hidden="true">
              <div className="h-2 rounded bg-primary" style={{ width: barWidth(row.revenue_share) }} />
            </div>
            <PhoneFigures figures={row} />
          </li>
        ))}
        {summaries.map(([label, figures]) => (
          <li key={label} className="space-y-2 rounded-lg bg-muted p-3">
            <p className="font-semibold">{label}</p>
            <PhoneFigures figures={figures} />
          </li>
        ))}
      </ul>
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full text-sm">
          <caption className="sr-only">{t("reports.title")}</caption>
          <thead className="border-b border-border text-xs text-muted-foreground">
            <tr>
              <th scope="col" className="px-3 py-2 text-left font-medium">
                {t("reports.col.source")}
              </th>
              <th scope="col" className={head}>{t("reports.col.bookings")}</th>
              <th scope="col" className={head}>{t("reports.col.nights")}</th>
              <th scope="col" className={head}>{t("reports.col.revenue")}</th>
              <th scope="col" className={head}>{t("reports.col.average")}</th>
              <th scope="col" className={head}>{t("reports.col.cancelled")}</th>
              <th scope="col" className={head}>{t("reports.col.commission")}</th>
              <th scope="col" className={head}>{t("reports.col.net")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {report.rows.map((row) => (
              <tr key={row.code}>
                <th scope="row" className="min-w-40 px-3 py-2 text-left font-medium">
                  {nameOf(row)}
                  <span className="mt-1 block h-1.5 rounded bg-muted" aria-hidden="true">
                    <span
                      className="block h-1.5 rounded bg-primary"
                      style={{ width: barWidth(row.revenue_share) }}
                    />
                  </span>
                  <span className="text-xs font-normal text-muted-foreground">
                    {t("reports.share", { value: percentLabel(row.revenue_share) })}
                  </span>
                </th>
                <Figures figures={row} />
              </tr>
            ))}
          </tbody>
          <tfoot className="border-t-2 border-border bg-muted/50">
            {summaries.map(([label, figures]) => (
              <tr key={label} className="font-medium">
                <th scope="row" className="px-3 py-2 text-left">{label}</th>
                <Figures figures={figures} />
              </tr>
            ))}
          </tfoot>
        </table>
      </div>
    </>
  );
}
