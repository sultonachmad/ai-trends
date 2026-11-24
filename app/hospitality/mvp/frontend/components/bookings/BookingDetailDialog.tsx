"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import { RefundDoneForm } from "@/components/bookings/RefundDoneForm";
import { Dialog } from "@/components/Dialog";
import { inputClass } from "@/components/rooms/RoomTypeDialog";
import {
  isOpen,
  paymentBadgeClass,
  paymentStateKey,
  shortDate,
  stayRange,
} from "@/lib/booking-format";
import { checkPayment, NOTE_MAX, type PaymentForm } from "@/lib/booking-forms";
import {
  cancelBooking,
  fetchBooking,
  PAYMENT_METHODS,
  recordPayment,
  removePayment,
  type BookingDetail,
  type PaymentMethod,
} from "@/lib/bookings-api";
import { useLocale } from "@/lib/locale-store";
import { formatRupiah } from "@/lib/money";

interface BookingDetailDialogProps {
  /** The booking to show; null closes the dialog. */
  bookingId: string | null;
  /** Today at the property. */
  today: string;
  /** Whether the viewer may change or cancel bookings (bookings:edit). */
  canEdit: boolean;
  onClose: () => void;
  /** Something about the booking changed: the list behind should refresh. */
  onChanged: () => void;
  onEdit: (booking: BookingDetail) => void;
  /** Open the booking's bill; absent when the viewer cannot see bills. */
  onOpenBill?: (bookingId: string) => void;
}

const STAGED: readonly string[] = ["in_house", "checked_out", "no_show"];
const secondary = "rounded-md border border-border px-3 py-1.5 text-sm hover:bg-accent disabled:opacity-50";
const errorText = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));

/** One booking: stay, price per night, money received, and the actions on it. */
export function BookingDetailDialog({
  bookingId,
  today,
  canEdit,
  onClose,
  onChanged,
  onEdit,
  onOpenBill,
}: BookingDetailDialogProps) {
  const { t, locale } = useLocale();
  const [booking, setBooking] = useState<BookingDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [reason, setReason] = useState("");
  const [payment, setPayment] = useState<PaymentForm>({
    amount: "",
    method: "cash",
    receivedOn: today,
    note: "",
  });
  const loadRequest = useRef(0);

  useEffect(() => {
    setBooking(null);
    setError(null);
    setCancelling(false);
    setReason("");
    setPayment({ amount: "", method: "cash", receivedOn: today, note: "" });
    if (bookingId === null) return;
    const request = ++loadRequest.current;
    fetchBooking(bookingId)
      .then((loaded) => {
        if (request === loadRequest.current) setBooking(loaded);
      })
      .catch((cause) => {
        if (request === loadRequest.current) setError(errorText(cause));
      });
  }, [bookingId, today]);

  // Run a change, show the booking as the server now has it, and tell the list.
  const act = async (change: () => Promise<BookingDetail>) => {
    setBusy(true);
    setError(null);
    try {
      setBooking(await change());
      onChanged();
      return true;
    } catch (cause) {
      setError(errorText(cause));
      return false;
    } finally {
      setBusy(false);
    }
  };

  const onPay = async (event: FormEvent) => {
    event.preventDefault();
    if (!booking) return;
    if (!canEdit) return;
    const checked = checkPayment(payment, today);
    if (!checked.ok) return setError(t(checked.problem.key, checked.problem.vars));
    if (await act(() => recordPayment(booking.id, checked.value))) {
      setPayment({ amount: "", method: "cash", receivedOn: today, note: "" });
    }
  };

  const onCancel = async () => {
    if (!booking) return;
    if (await act(() => cancelBooking(booking.id, reason.trim() || undefined))) {
      setCancelling(false);
    }
  };

  const close = () => {
    if (!busy) onClose();
  };
  const title = booking ? t("bookings.detail.title", { number: booking.number }) : t("bookings.title");
  const terms = (detail: BookingDetail) => {
    if (!detail.terms) return "—";
    if (detail.terms.non_refundable) return t("rates.terms.nonRefundable");
    const days = detail.terms.free_cancellation_days ?? 0;
    return days === 0 ? t("rates.terms.freeUntilArrival") : t("rates.terms.free", { days });
  };

  return (
    <Dialog open={bookingId !== null} onClose={close} title={title}>
      {!booking && !error && <p className="text-sm text-muted-foreground">{t("common.loading")}</p>}
      {booking && (
        <div className="space-y-4 text-sm">
          <div>
            <p className="text-lg font-semibold">{booking.guest.name}</p>
            {booking.guest.phone && <p className="text-muted-foreground">{booking.guest.phone}</p>}
            <p className="mt-1 text-xs text-muted-foreground">
              {t("bookings.detail.booked", {
                date: shortDate(booking.created_at.slice(0, 10), locale),
                source: booking.source.is_direct
                  ? t(`bookings.source.${booking.source.code}`)
                  : booking.source.name,
              })}
            </p>
          </div>
          {STAGED.includes(booking.status) && (
            <p role="status" className="rounded-lg bg-muted px-3 py-2 font-medium">
              {t(`bookings.status.${booking.status}`)}
            </p>
          )}
          {booking.assigned_rooms.length > 0 && (
            <p>{t("bookings.detail.rooms", { rooms: booking.assigned_rooms.join(", ") })}</p>
          )}
          {booking.status === "cancelled" && (
            <p className="rounded-lg bg-muted px-3 py-2 font-medium">
              {t("bookings.detail.cancelledOn", {
                date: shortDate((booking.cancelled_at ?? "").slice(0, 10), locale),
              })}
              {booking.cancel_note && (
                <span className="block font-normal">
                  {t("bookings.detail.cancelNote", { reason: booking.cancel_note })}
                </span>
              )}
            </p>
          )}
          {booking.status === "tentative" && booking.hold_expires_at && (
            <p role="status" className="rounded-lg bg-muted px-3 py-2">
              {t("bookings.heldUntil", {
                time: new Date(booking.hold_expires_at).toLocaleString(
                  locale === "id" ? "id-ID" : "en-GB",
                  { dateStyle: "medium", timeStyle: "short" },
                ),
              })}
            </p>
          )}
          {booking.refund_due && (
            <p role="status" className="rounded-lg bg-destructive/10 px-3 py-2 text-destructive">
              {t("bookings.refundDueHint")}
            </p>
          )}
          {booking.refund_due && canEdit && (
            <RefundDoneForm
              bookingId={booking.id}
              today={today}
              busy={busy}
              onSubmit={act}
              onProblem={setError}
            />
          )}
          {booking.refund_done && (
            <p role="status" className="rounded-lg bg-muted px-3 py-2">
              {t("bookings.refund.recorded", {
                amount: formatRupiah(booking.refund_done.amount),
                date: shortDate(booking.refund_done.refunded_on, locale),
              })}
              {booking.refund_done.note && (
                <span className="block text-xs text-muted-foreground">
                  {booking.refund_done.note}
                </span>
              )}
            </p>
          )}
          {booking.confirmation_status === "failed" && (
            <p role="status" className="rounded-lg bg-destructive/10 px-3 py-2 text-destructive">
              {t("bookings.confirmationFailedHint")}
            </p>
          )}
          {booking.overbooking_risk && (
            <p role="status" className="rounded-lg bg-destructive/10 px-3 py-2 text-destructive">
              <span className="font-semibold">{t("bookings.risk")}.</span> {t("bookings.riskHint")}
            </p>
          )}
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
            <dt className="text-muted-foreground">{t("bookings.col.stay")}</dt>
            <dd>
              {stayRange(booking.arrival, booking.departure, locale)} ·{" "}
              {t("bookings.nights", { count: booking.nights })}
            </dd>
            <dt className="text-muted-foreground">{t("bookings.col.room")}</dt>
            <dd>
              {t("bookings.unitsOf", { count: booking.units, room: booking.room_type.name })} ·{" "}
              {booking.rate_plan.name}
            </dd>
            <dt className="text-muted-foreground">{t("bookings.col.guest")}</dt>
            <dd>
              {t("bookings.adults", { count: booking.adults })}
              {booking.children > 0 && `, ${t("bookings.children", { count: booking.children })}`}
            </dd>
            {booking.channel_reference && (
              <>
                <dt className="text-muted-foreground">{t("bookings.channel.title")}</dt>
                <dd>{t("bookings.channel.reference", { ref: booking.channel_reference })}</dd>
              </>
            )}
            <dt className="text-muted-foreground">{t("bookings.detail.terms")}</dt>
            <dd>{terms(booking)}</dd>
            {booking.notes && (
              <>
                <dt className="text-muted-foreground">{t("bookings.detail.notes")}</dt>
                <dd className="whitespace-pre-wrap">{booking.notes}</dd>
              </>
            )}
          </dl>

          <section aria-labelledby="booking-nightly">
            <h3 id="booking-nightly" className="mb-1 font-semibold">
              {t("bookings.detail.nightly")}
            </h3>
            <ul className="max-h-32 overflow-y-auto rounded-lg border border-border">
              {booking.nightly.map((night) => (
                <li key={night.date} className="flex justify-between px-3 py-1 tabular-nums">
                  <span>{shortDate(night.date, locale)}</span>
                  <span>{formatRupiah(night.amount)}</span>
                </li>
              ))}
            </ul>
          </section>

          <section aria-labelledby="booking-money" className="space-y-2">
            <h3 id="booking-money" className="font-semibold">
              {t("bookings.detail.payments")}
            </h3>
            <dl className="grid grid-cols-3 gap-2 rounded-lg bg-muted p-3 text-center">
              {(
                [
                  ["bookings.detail.total", booking.total_amount],
                  ["bookings.detail.paid", booking.paid_amount],
                  ["bookings.detail.balance", booking.balance_due],
                ] as const
              ).map(([label, amount]) => (
                <div key={label}>
                  <dt className="text-xs text-muted-foreground">{t(label)}</dt>
                  <dd className="font-semibold tabular-nums">{formatRupiah(amount)}</dd>
                </div>
              ))}
            </dl>
            <p>
              <span
                className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${paymentBadgeClass(
                  booking.payment_state,
                )}`}
              >
                {t(paymentStateKey(booking.payment_state))}
              </span>
            </p>
            {booking.payments.length === 0 ? (
              <p className="text-muted-foreground">{t("bookings.detail.noPayments")}</p>
            ) : (
              <ul className="divide-y divide-border rounded-lg border border-border">
                {booking.payments.map((entry) => (
                  <li key={entry.id} className="flex items-center justify-between gap-2 px-3 py-2">
                    <span>
                      <span className="font-medium tabular-nums">{formatRupiah(entry.amount)}</span>{" "}
                      · {t(`bookings.pay.method.${entry.method}`)} ·{" "}
                      {shortDate(entry.received_on, locale)}
                      {entry.note && (
                        <span className="block text-xs text-muted-foreground">{entry.note}</span>
                      )}
                    </span>
                    <button
                      type="button"
                      disabled={busy}
                      aria-label={t("bookings.pay.removeLabel", {
                        amount: formatRupiah(entry.amount),
                      })}
                      hidden={!canEdit || !entry.removable}
                      onClick={() => void act(() => removePayment(booking.id, entry.id))}
                      className="text-xs font-medium text-destructive hover:underline disabled:opacity-50"
                    >
                      {t("bookings.pay.remove")}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {canEdit && booking.status !== "tentative" && (
            <form onSubmit={onPay} noValidate className="space-y-2 rounded-lg border border-border p-3">
              <p className="font-medium">{t("bookings.pay.title")}</p>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label htmlFor="pay-amount" className="mb-1 block text-xs">
                    {t("bookings.pay.amount")}
                  </label>
                  <input
                    id="pay-amount"
                    inputMode="numeric"
                    autoComplete="off"
                    value={payment.amount}
                    onChange={(event) => setPayment({ ...payment, amount: event.target.value })}
                    className={inputClass}
                  />
                </div>
                <div>
                  <label htmlFor="pay-method" className="mb-1 block text-xs">
                    {t("bookings.pay.method")}
                  </label>
                  <select
                    id="pay-method"
                    value={payment.method}
                    onChange={(event) =>
                      setPayment({ ...payment, method: event.target.value as PaymentMethod })
                    }
                    className={inputClass}
                  >
                    {PAYMENT_METHODS.map((method) => (
                      <option key={method} value={method}>
                        {t(`bookings.pay.method.${method}`)}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="pay-date" className="mb-1 block text-xs">
                    {t("bookings.pay.date")}
                  </label>
                  <input
                    id="pay-date"
                    type="date"
                    max={today}
                    value={payment.receivedOn}
                    onChange={(event) => setPayment({ ...payment, receivedOn: event.target.value })}
                    className={inputClass}
                  />
                </div>
                <div>
                  <label htmlFor="pay-note" className="mb-1 block text-xs">
                    {t("bookings.pay.note")}
                  </label>
                  <input
                    id="pay-note"
                    maxLength={NOTE_MAX}
                    value={payment.note}
                    onChange={(event) => setPayment({ ...payment, note: event.target.value })}
                    className={inputClass}
                  />
                </div>
              </div>
              <button type="submit" disabled={busy} className={secondary}>
                {t("bookings.pay.save")}
              </button>
            </form>
            )}
          </section>

          {cancelling && (
            <div className="space-y-2 rounded-lg border border-destructive/40 p-3">
              <p>{t("bookings.detail.cancelHint")}</p>
              <label htmlFor="cancel-reason" className="block text-xs">
                {t("bookings.detail.cancelReason")}
              </label>
              <input
                id="cancel-reason"
                maxLength={NOTE_MAX}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                className={inputClass}
              />
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void onCancel()}
                  className="rounded-md bg-destructive/15 px-3 py-1.5 text-sm font-medium text-destructive hover:bg-destructive/25 disabled:opacity-50"
                >
                  {t("bookings.detail.cancelConfirm")}
                </button>
                <button type="button" disabled={busy} onClick={() => setCancelling(false)} className={secondary}>
                  {t("bookings.detail.keep")}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
      {error && (
        <p role="alert" className="mt-3 text-sm text-destructive">
          {error}
        </p>
      )}
      <div className="mt-4 flex flex-wrap justify-end gap-2">
        {booking && onOpenBill && (
          <button type="button" disabled={busy} onClick={() => onOpenBill(booking.id)} className={secondary}>
            {t("bills.open")}
          </button>
        )}
        {booking && canEdit && (isOpen(booking) || booking.status === "tentative") && !cancelling && (
          <>
            <button type="button" disabled={busy} onClick={() => setCancelling(true)} className={secondary}>
              {t("bookings.detail.cancel")}
            </button>
            {isOpen(booking) && (
              <button type="button" disabled={busy} onClick={() => onEdit(booking)} className={secondary}>
                {t("bookings.detail.edit")}
              </button>
            )}
          </>
        )}
        <button
          type="button"
          onClick={close}
          disabled={busy}
          className="rounded-md bg-secondary px-4 py-2 text-sm text-secondary-foreground disabled:opacity-50"
        >
          {t("proofs.close")}
        </button>
      </div>
    </Dialog>
  );
}
