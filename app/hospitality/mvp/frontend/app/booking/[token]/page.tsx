"use client";

/**
 * The guest's private booking page — `/booking/<token>`, from the WhatsApp confirmation
 * or the payment page. No sign-in: view the booking, finish paying or cancel it.
 */

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { LanguageSwitch } from "@/components/LanguageSwitch";
import { ApiError } from "@/lib/api-client";
import { shortDate } from "@/lib/booking-format";
import {
  cancelGuestBooking,
  fetchGuestBooking,
  type GuestBooking,
} from "@/lib/booking-page-api";
import { errorCode, freeCancelUntil } from "@/lib/booking-page-format";
import { useLocale } from "@/lib/locale-store";
import { formatRupiah } from "@/lib/money";
import { usePolling } from "@/lib/use-polling";

const POLL_MS = 5000;
const cardClass = "space-y-4 rounded-xl border border-border bg-card p-4 text-card-foreground shadow-sm";

export default function GuestBookingPage() {
  const { token } = useParams<{ token: string }>();
  const { t, locale } = useLocale();
  const [booking, setBooking] = useState<GuestBooking | null>(null);
  const [missing, setMissing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [acceptNoRefund, setAcceptNoRefund] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setBooking(await fetchGuestBooking(token));
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 404) setMissing(true);
      else throw cause;
    }
  }, [token]);

  useEffect(() => {
    load().catch(() => setError(t("book.loadFailed")));
  }, [load, t]);
  usePolling(load, POLL_MS, booking?.status === "awaiting_payment");

  const cancel = async () => {
    setBusy(true);
    setError(null);
    try {
      setBooking(await cancelGuestBooking(token, acceptNoRefund));
      setConfirming(false);
    } catch (cause) {
      setError(t(`book.error.${errorCode(cause)}`, { phone: "" }));
      await load().catch(() => undefined); // show what the booking is now
    } finally {
      setBusy(false);
    }
  };

  const shell = (content: React.ReactNode) => (
    <div className="mx-auto min-h-screen max-w-xl space-y-4 bg-background p-4 text-foreground">
      <div className="flex justify-end">
        <LanguageSwitch />
      </div>
      {content}
    </div>
  );
  if (missing) return shell(<p role="alert">{t("book.manage.notFound")}</p>);
  if (!booking) {
    return shell(
      error ? (
        <p role="alert">{error}</p>
      ) : (
        <p className="text-muted-foreground">{t("common.loading")}</p>
      ),
    );
  }

  const until = freeCancelUntil(booking.arrival, booking.free_cancellation_days);
  const losesMoney = Number(booking.paid) > 0 && !booking.refund_if_cancelled;
  const whatsappUrl = booking.property_whatsapp
    ? `https://wa.me/${booking.property_whatsapp.replace(/\D/g, "")}`
    : null;
  return shell(
    <section className={cardClass}>
      <header>
        <h1 className="text-xl font-bold">{booking.property_name}</h1>
        <p className="text-sm text-muted-foreground">
          {t("book.manage.number", { number: booking.number })}
        </p>
        <p role="status" className="mt-2 font-semibold">
          {t(`book.manage.status.${booking.status}`)}
        </p>
      </header>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        <dt className="text-muted-foreground">{t("book.manage.stay")}</dt>
        <dd>
          {shortDate(booking.arrival, locale)} – {shortDate(booking.departure, locale)} ·{" "}
          {t("book.manage.nights", { count: booking.nights })}
        </dd>
        <dt className="text-muted-foreground">{t("book.manage.room")}</dt>
        <dd>
          {booking.room_name} · {booking.plan_name}
        </dd>
        <dt className="text-muted-foreground">{t("book.manage.guest")}</dt>
        <dd>
          {booking.guest_name}
          {booking.phone_hint ? ` · ${booking.phone_hint}` : ""}
        </dd>
        <dt className="text-muted-foreground">{t("book.manage.total")}</dt>
        <dd>{formatRupiah(booking.total)}</dd>
        <dt className="text-muted-foreground">{t("book.manage.paid")}</dt>
        <dd>{formatRupiah(booking.paid)}</dd>
        <dt className="text-muted-foreground">{t("book.manage.balance")}</dt>
        <dd>{formatRupiah(booking.balance)}</dd>
      </dl>
      <p className="rounded-lg bg-muted px-3 py-2 text-sm">
        {booking.non_refundable
          ? t("book.terms.nonRefundable")
          : t("book.terms.free", { date: until ? shortDate(until, locale) : "" })}
      </p>
      {booking.refund_due && (
        <p role="status" className="rounded-lg bg-muted px-3 py-2 text-sm font-medium">
          {t("book.manage.refundDue")}
        </p>
      )}
      {booking.pay_url && (
        <a
          href={booking.pay_url}
          className="block min-h-11 rounded-md bg-primary px-4 py-3 text-center text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          {t("book.manage.finishPaying")}
        </a>
      )}
      {whatsappUrl && (
        <a
          href={whatsappUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="block min-h-11 rounded-md border border-border px-4 py-3 text-center text-sm hover:bg-accent"
        >
          {t("book.manage.contact")}
        </a>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      {booking.can_cancel && !confirming && (
        <button
          type="button"
          onClick={() => setConfirming(true)}
          className="min-h-11 w-full rounded-md border border-border px-4 py-2 text-sm text-destructive hover:bg-accent"
        >
          {t("book.manage.cancel")}
        </button>
      )}
      {booking.can_cancel && confirming && (
        <div className="space-y-3 rounded-lg border border-destructive/40 p-3 text-sm">
          <p>
            {booking.refund_if_cancelled
              ? t("book.manage.cancelRefund", { amount: formatRupiah(booking.paid) })
              : losesMoney
                ? t("book.manage.cancelNoRefund", { amount: formatRupiah(booking.paid) })
                : t("book.manage.cancelUnpaid")}
          </p>
          {losesMoney && (
            <label className="flex min-h-11 cursor-pointer items-start gap-2">
              <input
                type="checkbox"
                className="mt-1"
                checked={acceptNoRefund}
                onChange={(event) => setAcceptNoRefund(event.target.checked)}
              />
              <span>{t("book.manage.acceptNoRefund")}</span>
            </label>
          )}
          <div className="flex flex-wrap justify-end gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => setConfirming(false)}
              className="min-h-11 rounded-md bg-secondary px-4 py-2 text-secondary-foreground disabled:opacity-50"
            >
              {t("book.manage.keep")}
            </button>
            <button
              type="button"
              disabled={busy || (losesMoney && !acceptNoRefund)}
              onClick={() => void cancel()}
              className="min-h-11 rounded-md bg-destructive px-4 py-2 font-medium text-destructive-foreground disabled:opacity-50"
            >
              {t("book.manage.confirmCancel")}
            </button>
          </div>
        </div>
      )}
    </section>,
  );
}
