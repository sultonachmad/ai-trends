"use client";

import { LanguageSwitch } from "@/components/LanguageSwitch";
import { balanceState } from "@/lib/bill-format";
import { shortDate } from "@/lib/booking-format";
import { useLocale } from "@/lib/locale-store";
import { formatRupiah } from "@/lib/money";

export interface PrintableLine {
  description: string;
  quantity: string;
  amount: string;
  isRoom: boolean;
}

interface PrintableBillProps {
  heading: string;
  number: string | null;
  issuedOn: string | null;
  issuer: string;
  taxId: string | null;
  bookingNumber: string;
  guestName: string;
  arrival: string;
  departure: string;
  paidToChannel: boolean;
  lines: PrintableLine[];
  total: string;
  paid: string;
  balance: string;
}

const cell = "py-1 align-top";

/** A bill or receipt laid out for paper; the buttons do not print. */
export function PrintableBill(props: PrintableBillProps) {
  const { t, locale } = useLocale();
  return (
    <div className="mx-auto max-w-xl space-y-4 rounded-lg bg-card p-6 text-sm text-card-foreground print:max-w-none print:rounded-none print:p-0">
      <div className="flex flex-wrap justify-end gap-2 print:hidden">
        <LanguageSwitch />
        <button
          type="button"
          onClick={() => window.print()}
          className="min-h-11 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
        >
          {t("bills.print")}
        </button>
      </div>
      <header>
        <p className="text-lg font-bold">{props.issuer}</p>
        {props.taxId && <p>{t("bills.taxId", { id: props.taxId })}</p>}
        <h1 className="mt-3 text-xl font-bold">{props.heading}</h1>
        {props.number && <p>{t("bills.receiptNumber", { number: props.number })}</p>}
        {props.issuedOn && <p>{shortDate(props.issuedOn, locale)}</p>}
      </header>
      <p>
        {props.guestName} · {props.bookingNumber}
        <br />
        {shortDate(props.arrival, locale)} – {shortDate(props.departure, locale)}
      </p>
      <table className="w-full">
        <tbody className="divide-y divide-border">
          {props.lines.map((line, index) => (
            <tr key={index}>
              <td className={cell}>
                {line.isRoom
                  ? t("bills.roomLine", { room: line.description, count: Number(line.quantity) })
                  : `${line.description}${Number(line.quantity) !== 1 ? ` × ${Number(line.quantity)}` : ""}`}
                {line.isRoom && props.paidToChannel && (
                  <span className="block text-xs">{t("bills.paidToChannel")}</span>
                )}
              </td>
              <td className={`${cell} text-right tabular-nums`}>{formatRupiah(line.amount)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot className="border-t-2 border-border font-medium">
          <tr>
            <td className={cell}>{t("bills.total")}</td>
            <td className={`${cell} text-right tabular-nums`}>{formatRupiah(props.total)}</td>
          </tr>
          <tr>
            <td className={cell}>{t("bills.totalPaid")}</td>
            <td className={`${cell} text-right tabular-nums`}>{formatRupiah(props.paid)}</td>
          </tr>
          <tr className="text-base font-bold">
            <td className={cell}>{t(`bills.balance.${balanceState(props.balance)}`)}</td>
            <td className={`${cell} text-right tabular-nums`}>
              {formatRupiah(String(Math.abs(Number(props.balance))))}
            </td>
          </tr>
        </tfoot>
      </table>
      {!props.number && <p className="text-xs">{t("bills.notReceipt")}</p>}
    </div>
  );
}
