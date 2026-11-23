"use client";

import {
  paymentBadgeClass,
  paymentStateKey,
  stayRange,
  todayNote,
} from "@/lib/booking-format";
import type { Booking } from "@/lib/bookings-api";
import { useLocale } from "@/lib/locale-store";
import { formatRupiah } from "@/lib/money";

interface BookingTableProps {
  bookings: Booking[];
  /** Today at the property. */
  today: string;
  onOpen: (booking: Booking) => void;
}

const badge = "inline-block rounded-full px-2 py-0.5 text-xs font-medium";

function Flags({ booking, today }: { booking: Booking; today: string }) {
  const { t } = useLocale();
  const note = todayNote(booking, today);
  return (
    <>
      {note && (
        <span className={`${badge} bg-accent text-accent-foreground`}>
          {t(`bookings.today.${note}`)}
        </span>
      )}
      {booking.status === "tentative" && (
        <span className={`${badge} bg-accent text-accent-foreground`}>
          {t("bookings.awaitingPayment")}
        </span>
      )}
      {booking.refund_due && (
        <span className={`${badge} bg-destructive/15 text-destructive`}>
          {t("bookings.refundDue")}
        </span>
      )}
      {booking.confirmation_status === "failed" && (
        <span className={`${badge} bg-destructive/15 text-destructive`}>
          {t("bookings.confirmationFailed")}
        </span>
      )}
      {booking.overbooking_risk && (
        <span className={`${badge} bg-destructive/15 text-destructive`} title={t("bookings.riskHint")}>
          {t("bookings.risk")}
        </span>
      )}
      {booking.channel_attention && (
        <span className={`${badge} bg-accent text-accent-foreground`}>
          {t(`bookings.channel.attention.${booking.channel_attention}`)}
        </span>
      )}
    </>
  );
}

function Money({ booking }: { booking: Booking }) {
  const { t } = useLocale();
  return (
    <>
      <span className="font-semibold tabular-nums">{formatRupiah(booking.total_amount)}</span>
      <span className={`${badge} ml-2 ${paymentBadgeClass(booking.payment_state)}`}>
        {t(paymentStateKey(booking.payment_state))}
      </span>
      {booking.payment_state === "partly_paid" && (
        <span className="block text-xs text-muted-foreground">
          {t("bookings.balance", { amount: formatRupiah(booking.balance_due) })}
        </span>
      )}
    </>
  );
}

/** Bookings as a table on wide screens and as stacked rows on a phone. */
export function BookingTable({ bookings, today, onOpen }: BookingTableProps) {
  const { t, locale } = useLocale();
  const stay = (booking: Booking) => stayRange(booking.arrival, booking.departure, locale);
  const room = (booking: Booking) =>
    t("bookings.unitsOf", { count: booking.units, room: booking.room_type.name });

  return (
    <>
      <ul className="divide-y divide-border sm:hidden">
        {bookings.map((booking) => (
          <li key={booking.id}>
            <button
              type="button"
              onClick={() => onOpen(booking)}
              className="block w-full space-y-1 px-4 py-3 text-left hover:bg-accent"
            >
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-semibold">{booking.guest.name}</span>
                <Flags booking={booking} today={today} />
              </span>
              <span className="block text-sm">
                {stay(booking)} · {t("bookings.nights", { count: booking.nights })}
              </span>
              <span className="block text-sm text-muted-foreground">
                {room(booking)} · {booking.number}
              </span>
              <span className="block text-sm">
                <Money booking={booking} />
              </span>
            </button>
          </li>
        ))}
      </ul>
      <div className="relative hidden overflow-x-auto sm:block">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-border text-xs text-muted-foreground">
            <tr>
              <th scope="col" className="px-4 py-2 font-medium">{t("bookings.col.guest")}</th>
              <th scope="col" className="px-4 py-2 font-medium">{t("bookings.col.stay")}</th>
              <th scope="col" className="px-4 py-2 font-medium">{t("bookings.col.room")}</th>
              <th scope="col" className="px-4 py-2 font-medium">{t("bookings.col.total")}</th>
              <th scope="col" className="px-4 py-2">
                <span className="sr-only">{t("bookings.view")}</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {bookings.map((booking) => (
              <tr key={booking.id}>
                <td className="px-4 py-3 align-top">
                  <span className="font-semibold">{booking.guest.name}</span>
                  <span className="block text-xs text-muted-foreground">
                    {booking.number} ·{" "}
                    {booking.source.is_direct
                      ? t(`bookings.source.${booking.source.code}`)
                      : booking.source.name}
                  </span>
                  <span className="mt-1 flex flex-wrap gap-1">
                    <Flags booking={booking} today={today} />
                  </span>
                </td>
                <td className="px-4 py-3 align-top">
                  {stay(booking)}
                  <span className="block text-xs text-muted-foreground">
                    {t("bookings.nights", { count: booking.nights })}
                  </span>
                </td>
                <td className="px-4 py-3 align-top">
                  {room(booking)}
                  <span className="block text-xs text-muted-foreground">
                    {booking.rate_plan.name}
                  </span>
                </td>
                <td className="px-4 py-3 align-top">
                  <Money booking={booking} />
                </td>
                <td className="px-4 py-3 text-right align-top">
                  <button
                    type="button"
                    onClick={() => onOpen(booking)}
                    aria-label={`${t("bookings.view")}: ${booking.guest.name}, ${booking.number}`}
                    className="rounded-md border border-border px-3 py-1 text-sm hover:bg-accent"
                  >
                    {t("bookings.view")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
