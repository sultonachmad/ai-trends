"use client";

import { shortDate } from "@/lib/booking-format";
import { useLocale } from "@/lib/locale-store";
import { taxTotal } from "@/lib/maintenance-format";
import { formatRupiah } from "@/lib/money";
import type { TaxMonth } from "@/lib/tax-summary-api";

const card = "space-y-1 rounded-lg border border-border bg-card p-3 text-sm";

function Line({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex justify-between gap-3">
      <span>{label}</span>
      <span className="whitespace-nowrap tabular-nums">{value}</span>
    </div>
  );
}

/** A month's totals, the channel part, and the days. */
export function TaxMonthView({ month }: { month: TaxMonth }) {
  const { t, locale } = useLocale();
  const { totals } = month;
  const channelTax = Number(totals.channel_service) + Number(totals.channel_pbjt);
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <section aria-labelledby="tax-due" className={card}>
          <h2 id="tax-due" className="font-semibold">{t("tax.total")}</h2>
          <p className="text-2xl font-bold tabular-nums">{formatRupiah(String(taxTotal(totals)))}</p>
          <Line label={t("tax.service")} value={formatRupiah(totals.service)} />
          <Line label={t("tax.pbjt")} value={formatRupiah(totals.pbjt)} />
        </section>
        <section aria-labelledby="tax-base" className={card}>
          <h2 id="tax-base" className="font-semibold">{t("tax.revenue")}</h2>
          <Line label={t("tax.roomNights")} value={totals.room_nights} />
          <Line label={t("tax.roomBase")} value={formatRupiah(totals.room_base)} />
          <Line label={t("tax.extrasBase")} value={formatRupiah(totals.extras_base)} />
          <Line label={t("tax.untaxed")} value={formatRupiah(totals.untaxed)} />
        </section>
      </div>
      {totals.channel_nights > 0 && (
        <section aria-labelledby="tax-channel" className={`${card} border-dashed`}>
          <h2 id="tax-channel" className="font-semibold">{t("tax.channel.title")}</h2>
          <p className="text-muted-foreground">{t("tax.channel.note")}</p>
          <Line label={t("tax.roomNights")} value={totals.channel_nights} />
          <Line label={t("tax.roomBase")} value={formatRupiah(totals.channel_base)} />
          <Line label={t("tax.channel.tax")} value={formatRupiah(String(channelTax))} />
        </section>
      )}
      <section aria-labelledby="tax-days" className="space-y-2">
        <h2 id="tax-days" className="font-semibold">{t("tax.byDay")}</h2>
        {month.days.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("tax.none")}</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted text-left">
                <tr>
                  <th scope="col" className="p-2">{t("tax.date")}</th>
                  <th scope="col" className="p-2 text-right">{t("tax.roomNights")}</th>
                  <th scope="col" className="p-2 text-right">{t("tax.service")}</th>
                  <th scope="col" className="p-2 text-right">{t("tax.pbjt")}</th>
                </tr>
              </thead>
              <tbody>
                {month.days.map((day) => (
                  <tr key={day.date} className="border-t border-border">
                    <td className="whitespace-nowrap p-2">{shortDate(day.date, locale)}</td>
                    <td className="p-2 text-right tabular-nums">{day.room_nights}</td>
                    <td className="whitespace-nowrap p-2 text-right tabular-nums">{formatRupiah(day.service)}</td>
                    <td className="whitespace-nowrap p-2 text-right tabular-nums">{formatRupiah(day.pbjt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
