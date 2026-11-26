"use client";

import type { DaySummary, Drawer } from "@/lib/end-of-day-api";
import { useLocale } from "@/lib/locale-store";
import { formatRupiah } from "@/lib/money";

const card = "space-y-1 rounded-lg border border-border bg-card p-3 text-sm";

function Line({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex justify-between gap-3">
      <span>{label}</span>
      <span className="whitespace-nowrap tabular-nums">{value}</span>
    </div>
  );
}

/** The day's figures: rooms, guests, extras, money and cash drawers. */
export function DaySummaryView({ summary, drawers }: { summary: DaySummary; drawers: Drawer[] }) {
  const { t } = useLocale();
  const { rooms, movements, money } = summary;
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <section aria-labelledby="eod-rooms" className={card}>
        <h3 id="eod-rooms" className="font-semibold">{t("endofday.rooms")}</h3>
        <p className="text-2xl font-bold tabular-nums">{rooms.occupancy_pct}%</p>
        <p className="text-muted-foreground">{t("endofday.sold", { sold: rooms.sold, available: rooms.available })}</p>
        <Line label={t("endofday.revenue")} value={formatRupiah(rooms.revenue)} />
        <Line label={t("endofday.adr")} value={formatRupiah(rooms.adr)} />
        <Line label={t("endofday.revpar")} value={formatRupiah(rooms.revpar)} />
      </section>
      <section aria-labelledby="eod-guests" className={card}>
        <h3 id="eod-guests" className="font-semibold">{t("endofday.movements")}</h3>
        <Line label={t("endofday.arrivals")} value={movements.arrivals} />
        <Line label={t("endofday.departures")} value={movements.departures} />
        <Line label={t("endofday.noShows")} value={movements.no_shows} />
        <Line label={t("endofday.cancellations")} value={movements.cancellations} />
        {summary.left_unpaid.count > 0 && (
          <p className="text-destructive">
            {t("endofday.leftUnpaid", {
              count: summary.left_unpaid.count,
              amount: formatRupiah(summary.left_unpaid.amount),
            })}
          </p>
        )}
      </section>
      <section aria-labelledby="eod-money" className={card}>
        <h3 id="eod-money" className="font-semibold">{t("endofday.money")}</h3>
        {money.received.map((row) => (
          <Line key={row.method} label={t(`drawer.method.${row.method}`)} value={formatRupiah(row.amount)} />
        ))}
        <div className="border-t border-border pt-1 font-semibold">
          <Line label={t("endofday.received")} value={formatRupiah(money.received_total)} />
        </div>
        <Line label={t("endofday.online")} value={formatRupiah(money.online)} />
        <Line label={t("endofday.deposits")} value={formatRupiah(money.deposits)} />
        {money.paid_out.length > 0 && (
          <div className="border-t border-border pt-1">
            <p className="font-medium">{t("endofday.out")}</p>
            {money.paid_out.map((row) => (
              <Line
                key={`${row.kind}-${row.method}`}
                label={`${t(`endofday.kind.${row.kind}`)} · ${t(`drawer.method.${row.method}`)}`}
                value={`− ${formatRupiah(row.amount)}`}
              />
            ))}
          </div>
        )}
      </section>
      <section aria-labelledby="eod-extras" className={card}>
        <h3 id="eod-extras" className="font-semibold">{t("endofday.extras")}</h3>
        {summary.extras.length === 0 ? (
          <p className="text-muted-foreground">-</p>
        ) : (
          summary.extras.map((row) => (
            <Line key={row.category} label={t(`bills.category.${row.category}`)} value={formatRupiah(row.amount)} />
          ))
        )}
      </section>
      <section aria-labelledby="eod-drawers" className={`${card} sm:col-span-2`}>
        <h3 id="eod-drawers" className="font-semibold">{t("endofday.drawers")}</h3>
        {drawers.length === 0 ? (
          <p className="text-muted-foreground">{t("endofday.noDrawers")}</p>
        ) : (
          <ul className="space-y-1">
            {drawers.map((drawer) => (
              <li key={drawer.id} className={drawer.variance && Number(drawer.variance) !== 0 ? "text-destructive" : ""}>
                {drawer.status === "open"
                  ? t("endofday.drawerOpenLine", { name: drawer.staff_name, expected: formatRupiah(drawer.expected_cash) })
                  : t("endofday.drawerLine", {
                      name: drawer.staff_name,
                      expected: formatRupiah(drawer.expected_cash),
                      counted: formatRupiah(drawer.counted_cash ?? "0"),
                      variance: formatRupiah(drawer.variance ?? "0"),
                    })}
                {drawer.notes && <span className="block text-xs text-muted-foreground">{drawer.notes}</span>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
