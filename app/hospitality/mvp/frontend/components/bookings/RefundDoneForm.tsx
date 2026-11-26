"use client";

import { useState, type FormEvent } from "react";

import { markRefundDone, type BookingDetail } from "@/lib/bookings-api";
import { useLocale } from "@/lib/locale-store";
import { parseRupiah } from "@/lib/money";
import { ApiError } from "@/lib/api-client";

const inputClass =
  "w-full rounded-md border border-border bg-card px-2 py-1.5 text-sm text-card-foreground focus:outline-none focus:ring-2 focus:ring-primary";

/** The server's refusal, shown in the staff member's language. */
const OVER_PAID_DETAIL = "Refunds cannot add up to more than the guest paid.";

interface RefundDoneFormProps {
  bookingId: string;
  today: string;
  busy: boolean;
  onSubmit: (change: () => Promise<BookingDetail>) => Promise<boolean>;
  onProblem: (message: string) => void;
}

/** Record a refund the guest was sent outside the product. */
export function RefundDoneForm({ bookingId, today, busy, onSubmit, onProblem }: RefundDoneFormProps) {
  const { t } = useLocale();
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(today);
  const [note, setNote] = useState("");
  const [method, setMethod] = useState<"bank_transfer" | "cash" | "other">("bank_transfer");

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const parsed = parseRupiah(amount);
    if (parsed === null) return onProblem(t("bookings.pay.badAmount"));
    if (!date) return onProblem(t("bookings.pay.needDate"));
    if (date > today) return onProblem(t("bookings.refund.futureDate"));
    await onSubmit(() =>
      markRefundDone(bookingId, {
        amount: parsed,
        refunded_on: date,
        method,
        ...(note.trim() ? { note: note.trim() } : {}),
      }).catch((cause: unknown) => {
        if (cause instanceof ApiError && cause.message === OVER_PAID_DETAIL) {
          throw new Error(t("bookings.refund.tooMuch"));
        }
        throw cause;
      }),
    );
  };

  return (
    <form
      onSubmit={(event) => void submit(event)}
      noValidate
      className="space-y-2 rounded-lg border border-border p-3"
    >
      <p className="font-medium">{t("bookings.refund.title")}</p>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label htmlFor="refund-amount" className="mb-1 block text-xs">
            {t("bookings.refund.amount")}
          </label>
          <input
            id="refund-amount"
            inputMode="numeric"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            className={inputClass}
          />
        </div>
        <div>
          <label htmlFor="refund-date" className="mb-1 block text-xs">
            {t("bookings.refund.date")}
          </label>
          <input
            id="refund-date"
            type="date"
            max={today}
            value={date}
            onChange={(event) => setDate(event.target.value)}
            className={inputClass}
          />
        </div>
      </div>
      <div>
        <label htmlFor="refund-method" className="mb-1 block text-xs">
          {t("bookings.refund.method")}
        </label>
        <select
          id="refund-method"
          value={method}
          onChange={(event) => setMethod(event.target.value as typeof method)}
          className={inputClass}
        >
          {(["bank_transfer", "cash", "other"] as const).map((option) => (
            <option key={option} value={option}>
              {t(`drawer.method.${option}`)}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor="refund-note" className="mb-1 block text-xs">
          {t("bookings.refund.note")}
        </label>
        <input
          id="refund-note"
          maxLength={1000}
          placeholder={t("bookings.refund.notePlaceholder")}
          value={note}
          onChange={(event) => setNote(event.target.value)}
          className={inputClass}
        />
      </div>
      <button
        type="submit"
        disabled={busy}
        className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
      >
        {t("bookings.refund.submit")}
      </button>
    </form>
  );
}
