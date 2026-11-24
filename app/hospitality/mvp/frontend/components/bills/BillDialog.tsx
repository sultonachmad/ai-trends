"use client";

import { useEffect, useRef, useState } from "react";

import { BILL_FORMS, BillForm, type BillFormKind } from "@/components/bills/BillForms";
import { Dialog } from "@/components/Dialog";
import { inputClass } from "@/components/rooms/RoomTypeDialog";
import { balanceState, billErrorKey, checkReason, lineLabelKey, TEXT_MAX } from "@/lib/bill-format";
import { shortDate, stayRange } from "@/lib/booking-format";
import { fetchBill, voidLine, type Bill, type BillLine } from "@/lib/bills-api";
import { useLocale } from "@/lib/locale-store";
import { formatRupiah } from "@/lib/money";
import { useCan } from "@/lib/rbac-store";

interface BillDialogProps {
  /** The booking whose bill to show; null closes the dialog. */
  bookingId: string | null;
  today: string;
  onClose: () => void;
  /** Something on the bill changed: lists behind should refresh. */
  onChanged: () => void;
}

const secondary =
  "min-h-11 rounded-md border border-border px-3 py-2 text-sm hover:bg-accent disabled:opacity-50";
const row = "flex justify-between gap-3 py-1";

function Line({
  line,
  canVoid,
  onVoid,
}: {
  line: BillLine;
  canVoid: boolean;
  onVoid: (line: BillLine) => void;
}) {
  const { t } = useLocale();
  const detail =
    line.unit_price && Number(line.quantity) !== 1
      ? ` · ${Number(line.quantity)} × ${formatRupiah(line.unit_price)}`
      : "";
  return (
    <li className="flex items-start justify-between gap-3 py-2">
      <div className={line.voided ? "text-muted-foreground line-through" : ""}>
        <p className="font-medium">{t(lineLabelKey(line.category))}</p>
        <p className="text-xs">
          {line.description}
          {detail}
        </p>
        {line.voided && line.void_reason && (
          <p className="text-xs no-underline">{t("bills.voided", { reason: line.void_reason })}</p>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <span className="tabular-nums">{formatRupiah(line.amount)}</span>
        {canVoid && line.can_void && (
          <button
            type="button"
            onClick={() => onVoid(line)}
            aria-label={`${t("bills.void")}: ${line.description}`}
            className={secondary}
          >
            {t("bills.void")}
          </button>
        )}
      </div>
    </li>
  );
}

/** A booking's bill: room nights, extras, payments, balance and receipts. */
export function BillDialog({ bookingId, today, onClose, onChanged }: BillDialogProps) {
  const { t, locale } = useLocale();
  const canEdit = useCan("bills:edit");
  const canChangePrice = useCan("bookings:edit");
  const [bill, setBill] = useState<Bill | null>(null);
  const [form, setForm] = useState<BillFormKind | null>(null);
  const [voiding, setVoiding] = useState<BillLine | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const request = useRef(0);

  useEffect(() => {
    setBill(null);
    setForm(null);
    setVoiding(null);
    setError(null);
    if (!bookingId) return;
    const id = ++request.current;
    fetchBill(bookingId)
      .then((found) => {
        if (id === request.current) setBill(found);
      })
      .catch((cause) => {
        if (id === request.current) setError(cause instanceof Error ? cause.message : String(cause));
      });
  }, [bookingId]);

  const act = async (change: () => Promise<Bill>) => {
    const id = request.current; // a reply for another booking's bill is dropped
    setBusy(true);
    setError(null);
    try {
      const changed = await change();
      if (id !== request.current) return false;
      setBill(changed);
      onChanged();
      return true;
    } catch (cause) {
      if (id !== request.current) return false;
      const key = billErrorKey(cause);
      setError(key ? t(key) : cause instanceof Error ? cause.message : String(cause));
      return false;
    } finally {
      setBusy(false);
    }
  };

  const confirmVoid = async () => {
    if (!bill || !voiding) return;
    const why = checkReason(reason);
    if (!why.ok) return setError(t(why.key));
    if (await act(() => voidLine(bill.booking_id, voiding.id, why.value))) {
      setVoiding(null);
      setReason("");
    }
  };

  const state = bill ? balanceState(bill.balance) : "settled";
  const allowed = BILL_FORMS.filter(
    (kind) => canChangePrice || (kind !== "discount" && kind !== "correction"),
  );
  const forms = bill?.closed ? allowed.filter((kind) => kind === "payment") : allowed;
  return (
    <Dialog
      open={bookingId !== null}
      onClose={() => !busy && onClose()}
      title={bill ? t("bills.title", { number: bill.number }) : t("bills.titlePlain")}
    >
      {!bill ? (
        <p className="text-sm text-muted-foreground">{error ?? t("common.loading")}</p>
      ) : (
        <div className="space-y-4 text-sm">
          <div>
            <p className="text-base font-semibold">{bill.guest_name}</p>
            <p className="text-muted-foreground">
              {stayRange(bill.arrival, bill.departure, locale)} · {bill.room_type}
            </p>
            {bill.left_unpaid && (
              <p className="mt-1 font-medium text-destructive">{t("bills.leftUnpaid")}</p>
            )}
          </div>
          <section aria-labelledby="bill-room" className="rounded-lg bg-muted p-3">
            <h3 id="bill-room" className="font-medium">
              {t("bills.room", { count: bill.room_nights.length })}
            </h3>
            <ul>
              {bill.room_nights.map((night) => (
                <li key={night.date} className={row}>
                  <span>{shortDate(night.date, locale)}</span>
                  <span className="tabular-nums">{formatRupiah(night.amount)}</span>
                </li>
              ))}
            </ul>
            {bill.paid_to_channel && (
              <p className="mt-1 font-medium">{t("bills.paidToChannel")}</p>
            )}
          </section>
          {bill.lines.length > 0 && (
            <section aria-labelledby="bill-extras">
              <h3 id="bill-extras" className="font-medium">{t("bills.extras")}</h3>
              <ul className="divide-y divide-border">
                {bill.lines.map((line) => (
                  <Line key={line.id} line={line} canVoid={canEdit} onVoid={setVoiding} />
                ))}
              </ul>
            </section>
          )}
          {bill.payments.length > 0 && (
            <section aria-labelledby="bill-payments">
              <h3 id="bill-payments" className="font-medium">{t("bills.payments")}</h3>
              <ul>
                {bill.payments.map((payment) => (
                  <li key={payment.id} className={row}>
                    <span>
                      {shortDate(payment.received_on, locale)} ·{" "}
                      {t(`bookings.pay.method.${payment.method}`)}
                    </span>
                    <span className="tabular-nums">{formatRupiah(payment.amount)}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
          <dl className="rounded-lg border border-border p-3">
            <div className={row}>
              <dt>{t("bills.totalRoom")}</dt>
              <dd className="tabular-nums">
                {bill.paid_to_channel ? t("bills.channel") : formatRupiah(bill.room_total)}
              </dd>
            </div>
            <div className={row}>
              <dt>{t("bills.totalExtras")}</dt>
              <dd className="tabular-nums">{formatRupiah(bill.extras_total)}</dd>
            </div>
            {bill.taxes.confirmed && !bill.taxes.included && (
              <>
                <div className={row}>
                  <dt>{t("bills.service")}</dt>
                  <dd className="tabular-nums">{formatRupiah(bill.taxes.service)}</dd>
                </div>
                <div className={row}>
                  <dt>{t("bills.pbjt")}</dt>
                  <dd className="tabular-nums">{formatRupiah(bill.taxes.pbjt)}</dd>
                </div>
              </>
            )}
            <div className={row}>
              <dt>{t("bills.totalPaid")}</dt>
              <dd className="tabular-nums">{formatRupiah(bill.paid)}</dd>
            </div>
            <div className={`${row} border-t border-border pt-2 text-base font-semibold`}>
              <dt>{t(`bills.balance.${state}`)}</dt>
              <dd className="tabular-nums">{formatRupiah(String(Math.abs(Number(bill.balance))))}</dd>
            </div>
          </dl>
          {bill.taxes.confirmed && bill.taxes.included && (
            <p className="text-xs text-muted-foreground">
              {t("bills.taxIncluded", {
                service: formatRupiah(bill.taxes.service),
                pbjt: formatRupiah(bill.taxes.pbjt),
              })}
            </p>
          )}
          {voiding && (
            <div className="space-y-2 rounded-lg border border-destructive/40 p-3">
              <label htmlFor="bill-void-reason" className="block font-medium">
                {t("bills.voidReason", { line: voiding.description })}
              </label>
              <input
                id="bill-void-reason"
                maxLength={TEXT_MAX}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                className={inputClass}
              />
              <div className="flex gap-2">
                <button type="button" disabled={busy} onClick={() => void confirmVoid()} className={secondary}>
                  {t("bills.void")}
                </button>
                <button type="button" disabled={busy} onClick={() => setVoiding(null)} className={secondary}>
                  {t("frontdesk.back")}
                </button>
              </div>
            </div>
          )}
          {canEdit && bill.status !== "tentative" && bill.status !== "cancelled" && (
            <section aria-label={t("bills.actions")} className="space-y-3">
              <div className="flex flex-wrap gap-2">
                {forms.map((kind) => (
                  <button
                    key={kind}
                    type="button"
                    aria-pressed={form === kind}
                    onClick={() => {
                      setError(null);
                      setForm(form === kind ? null : kind);
                    }}
                    className={`${secondary} ${form === kind ? "border-primary bg-accent" : ""}`}
                  >
                    {t(`bills.${kind}.open`)}
                  </button>
                ))}
              </div>
              {form && (
                <BillForm
                  key={form}
                  kind={form}
                  bookingId={bill.booking_id}
                  today={today}
                  busy={busy}
                  onSubmit={act}
                  onProblem={setError}
                />
              )}
            </section>
          )}
          {error && (
            <p role="alert" className="text-destructive">
              {error}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            {bill.receipts.map((receipt) => (
              <a
                key={receipt.id}
                href={`/receipts/${receipt.id}`}
                target="_blank"
                rel="noopener noreferrer"
                className={secondary}
              >
                {t(receipt.replaced ? "bills.receiptReplaced" : "bills.receipt", {
                  number: receipt.number,
                })}
              </a>
            ))}
            {!bill.closed && (
              <a href={`/bills/${bill.booking_id}`} target="_blank" rel="noopener noreferrer" className={secondary}>
                {t("bills.printBill")}
              </a>
            )}
          </div>
        </div>
      )}
      <div className="mt-4 flex justify-end">
        <button type="button" disabled={busy} onClick={onClose} className={secondary}>
          {t("proofs.close")}
        </button>
      </div>
    </Dialog>
  );
}
