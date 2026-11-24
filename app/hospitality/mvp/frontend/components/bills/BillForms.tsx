"use client";

import { useState, type FormEvent } from "react";

import { inputClass } from "@/components/rooms/RoomTypeDialog";
import { checkCharge, checkCorrection, checkReason, lineLabelKey, TEXT_MAX } from "@/lib/bill-format";
import { checkPayment } from "@/lib/booking-forms";
import {
  CHARGE_CATEGORIES,
  giveDiscount,
  payBill,
  postCharge,
  postCorrection,
  type Bill,
  type ChargeCategory,
} from "@/lib/bills-api";
import { PAYMENT_METHODS, type PaymentMethod } from "@/lib/bookings-api";
import { useLocale } from "@/lib/locale-store";
import { parseRupiah } from "@/lib/money";

export type BillFormKind = "charge" | "payment" | "discount" | "correction";
export const BILL_FORMS: readonly BillFormKind[] = ["charge", "payment", "discount", "correction"];

interface BillFormProps {
  kind: BillFormKind;
  bookingId: string;
  today: string;
  busy: boolean;
  onSubmit: (change: () => Promise<Bill>) => Promise<boolean>;
  onProblem: (message: string) => void;
}

const primary =
  "min-h-11 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50";
const label = "mb-1 block text-xs font-medium";

/** One small form on the bill: an extra, a payment, a discount or a correction. */
export function BillForm({ kind, bookingId, today, busy, onSubmit, onProblem }: BillFormProps) {
  const { t } = useLocale();
  const [category, setCategory] = useState<ChargeCategory>("food_drinks");
  const [description, setDescription] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState<PaymentMethod>("cash");
  const [receivedOn, setReceivedOn] = useState(today);
  const [reason, setReason] = useState("");

  const reset = () => {
    setDescription("");
    setQuantity("1");
    setAmount("");
    setReason("");
  };

  const build = (): (() => Promise<Bill>) | null => {
    if (kind === "charge") {
      const checked = checkCharge({ category, description, quantity, unitPrice: amount });
      if (!checked.ok) return onProblem(t(checked.key)), null;
      return () => postCharge(bookingId, checked.value);
    }
    if (kind === "payment") {
      const checked = checkPayment({ amount, method, receivedOn, note: reason }, today);
      if (!checked.ok) return onProblem(t(checked.problem.key, checked.problem.vars)), null;
      return () => payBill(bookingId, checked.value);
    }
    const why = checkReason(reason);
    if (!why.ok) return onProblem(t(why.key)), null;
    if (kind === "discount") {
      const value = parseRupiah(amount);
      if (value === null) return onProblem(t("bookings.pay.badAmount")), null;
      return () => giveDiscount(bookingId, value, why.value);
    }
    const signed = checkCorrection(amount);
    if (!signed.ok) return onProblem(t(signed.key)), null;
    return () => postCorrection(bookingId, signed.value, why.value);
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const change = build();
    if (change && (await onSubmit(change))) reset();
  };

  return (
    <form onSubmit={(event) => void submit(event)} noValidate className="space-y-3">
      {kind === "charge" && (
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label htmlFor="bill-category" className={label}>{t("bills.charge.category")}</label>
            <select
              id="bill-category"
              value={category}
              onChange={(event) => setCategory(event.target.value as ChargeCategory)}
              className={inputClass}
            >
              {CHARGE_CATEGORIES.map((name) => (
                <option key={name} value={name}>{t(lineLabelKey(name))}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="bill-description" className={label}>{t("bills.charge.description")}</label>
            <input
              id="bill-description"
              maxLength={TEXT_MAX}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label htmlFor="bill-quantity" className={label}>{t("bills.charge.quantity")}</label>
            <input
              id="bill-quantity"
              inputMode="numeric"
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
              className={inputClass}
            />
          </div>
        </div>
      )}
      {kind === "payment" && (
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label htmlFor="bill-method" className={label}>{t("bookings.pay.method")}</label>
            <select
              id="bill-method"
              value={method}
              onChange={(event) => setMethod(event.target.value as PaymentMethod)}
              className={inputClass}
            >
              {PAYMENT_METHODS.map((name) => (
                <option key={name} value={name}>{t(`bookings.pay.method.${name}`)}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="bill-received" className={label}>{t("bookings.pay.date")}</label>
            <input
              id="bill-received"
              type="date"
              max={today}
              value={receivedOn}
              onChange={(event) => setReceivedOn(event.target.value)}
              className={inputClass}
            />
          </div>
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor="bill-amount" className={label}>
            {t(kind === "charge" ? "bills.charge.unitPrice" : `bills.${kind}.amount`)}
          </label>
          <input
            id="bill-amount"
            inputMode={kind === "correction" ? "text" : "numeric"}
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            className={inputClass}
          />
        </div>
        {kind !== "charge" && (
          <div>
            <label htmlFor="bill-reason" className={label}>
              {t(kind === "payment" ? "bookings.pay.note" : "bills.reason")}
            </label>
            <input
              id="bill-reason"
              maxLength={TEXT_MAX}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              className={inputClass}
            />
          </div>
        )}
      </div>
      {kind === "correction" && (
        <p className="text-xs text-muted-foreground">{t("bills.correction.hint")}</p>
      )}
      <button type="submit" disabled={busy} className={primary}>
        {t(`bills.${kind}.save`)}
      </button>
    </form>
  );
}
