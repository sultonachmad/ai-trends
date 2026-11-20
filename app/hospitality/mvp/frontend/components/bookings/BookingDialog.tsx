"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import { Dialog } from "@/components/Dialog";
import { inputClass } from "@/components/rooms/RoomTypeDialog";
import { ApiError } from "@/lib/api-client";
import { shortDate } from "@/lib/booking-format";
import {
  changesFor,
  checkBooking,
  NAME_MAX,
  NOTES_MAX,
  stayOf,
  type BookingForm,
} from "@/lib/booking-forms";
import {
  createBooking,
  quoteBooking,
  shortDatesOf,
  STAFF_SOURCES,
  updateBooking,
  type Booking,
  type BookingDetail,
  type BookingQuote,
  type BookingSourceCode,
} from "@/lib/bookings-api";
import { addDays } from "@/lib/calendar-grid";
import { useLocale } from "@/lib/locale-store";
import { formatRupiah } from "@/lib/money";
import type { RatePlan } from "@/lib/rate-plans-api";
import type { RoomType } from "@/lib/rooms-api";

const QUOTE_DELAY_MS = 300;

/** Who the booking is for, when it is started from a chat. */
export interface BookingPrefill {
  guestName: string;
  guestPhone: string;
  conversationId: string;
}

interface BookingDialogProps {
  open: boolean;
  onClose: () => void;
  onSaved: (booking: BookingDetail) => void;
  /** The booking to change; omitted to enter a new one. */
  booking?: Booking;
  rooms: RoomType[];
  plans: RatePlan[];
  /** Today at the property. */
  today: string;
  prefill?: BookingPrefill;
}

const isStaffSource = (code: string): code is BookingSourceCode =>
  (STAFF_SOURCES as readonly string[]).includes(code);

function formOf(props: BookingDialogProps): BookingForm {
  const { booking, prefill, today, rooms } = props;
  if (booking) {
    return {
      arrival: booking.arrival,
      departure: booking.departure,
      roomTypeId: booking.room_type.id,
      ratePlanId: booking.rate_plan.id,
      units: String(booking.units),
      adults: String(booking.adults),
      children: String(booking.children),
      guestName: booking.guest.name,
      guestPhone: booking.guest.phone ?? "",
      source: isStaffSource(booking.source.code) ? booking.source.code : "other",
      total: booking.price_edited ? String(Math.trunc(Number(booking.total_amount))) : "",
      notes: booking.notes ?? "",
    };
  }
  // With one room type, or one rate plan selling it, there is nothing to choose.
  const roomTypeId = rooms.length === 1 ? rooms[0].id : "";
  const selling = props.plans.filter((plan) =>
    plan.prices.some((price) => price.room_type_id === roomTypeId),
  );
  return {
    arrival: today,
    departure: addDays(today, 1),
    roomTypeId,
    ratePlanId: selling.length === 1 ? selling[0].id : "",
    units: "1",
    adults: "2",
    children: "0",
    guestName: prefill?.guestName ?? "",
    guestPhone: prefill?.guestPhone ?? "",
    source: "whatsapp",
    total: "",
    notes: "",
  };
}

/** Enter or change a booking; the price and availability follow the form as it changes. */
export function BookingDialog(props: BookingDialogProps) {
  const { open, onClose, onSaved, booking, rooms, plans, prefill } = props;
  const { t, locale } = useLocale();
  const [form, setForm] = useState<BookingForm>(() => formOf(props));
  const [quote, setQuote] = useState<BookingQuote | null>(null);
  const [quoteError, setQuoteError] = useState<string | null>(null);
  const [bookAnyway, setBookAnyway] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const quoteRequest = useRef(0);

  // Start from the booking being changed (or a blank form) each time the dialog opens.
  useEffect(() => {
    if (!open) return;
    setForm(formOf({ open, onClose, onSaved, booking, rooms, plans, today: props.today, prefill }));
    setQuote(null);
    setQuoteError(null);
    setBookAnyway(false);
    setError(null);
    // The form must not reset while the person is typing: only opening restarts it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, booking?.id]);

  const sellingPlans = plans.filter((plan) =>
    plan.prices.some((price) => price.room_type_id === form.roomTypeId),
  );
  const stay = stayOf(form);
  const stayKey = stay ? JSON.stringify(stay) : null;

  // Ask for the price and availability shortly after the stay stops changing.
  useEffect(() => {
    // Whatever was shown belonged to another stay: drop it, and any answer still on its way.
    const request = ++quoteRequest.current;
    setQuote(null);
    setQuoteError(null);
    setBookAnyway(false);
    if (!open || stayKey === null) return;
    const timer = setTimeout(() => {
      quoteBooking(JSON.parse(stayKey), booking?.id)
        .then((result) => {
          if (request !== quoteRequest.current) return; // the stay changed meanwhile
          setQuote(result);
          setQuoteError(null);
        })
        .catch((cause) => {
          if (request !== quoteRequest.current) return;
          setQuote(null);
          setQuoteError(cause instanceof Error ? cause.message : String(cause));
        });
    }, QUOTE_DELAY_MS);
    return () => clearTimeout(timer);
  }, [open, stayKey, booking?.id]);

  const set = <K extends keyof BookingForm>(field: K, value: BookingForm[K]) =>
    setForm((current) => ({ ...current, [field]: value }));

  const chooseRoom = (roomTypeId: string) => {
    const stillSold = plans.some(
      (plan) =>
        plan.id === form.ratePlanId &&
        plan.prices.some((price) => price.room_type_id === roomTypeId),
    );
    const only = plans.filter((plan) =>
      plan.prices.some((price) => price.room_type_id === roomTypeId),
    );
    setForm((current) => ({
      ...current,
      roomTypeId,
      ratePlanId: stillSold ? current.ratePlanId : only.length === 1 ? only[0].id : "",
    }));
  };

  const close = () => {
    if (!busy) onClose();
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const checked = checkBooking(form, quote?.max_guests ?? null);
    if (!checked.ok) return setError(t(checked.problem.key, checked.problem.vars));
    if ((quote?.short_dates.length ?? 0) > 0 && !bookAnyway) {
      return setError(t("bookings.form.mustConfirm"));
    }
    // Consent counts only for the nights the person was shown as full.
    const consent = bookAnyway && (quote?.short_dates.length ?? 0) > 0;
    const input = { ...checked.value, allow_overbooking: consent };
    setBusy(true);
    setError(null);
    try {
      const saved = booking
        ? await updateBooking(booking.id, changesFor(input, booking.price_edited))
        : await createBooking({
            ...input,
            ...(prefill ? { conversation_id: prefill.conversationId } : {}),
          });
      onSaved(saved);
    } catch (cause) {
      const short = cause instanceof ApiError ? shortDatesOf(cause.detail) : null;
      if (short !== null) {
        // Someone took a unit in the meantime: show which nights and ask again.
        setError(t("bookings.form.mustConfirm"));
        setBookAnyway(false);
        setQuote((current) => (current ? { ...current, short_dates: short } : current));
      } else {
        setError(cause instanceof Error ? cause.message : String(cause));
      }
    } finally {
      setBusy(false);
    }
  };

  const dates = (list: string[]) => list.map((date) => shortDate(date, locale)).join(", ");
  const field = (id: string, label: string, control: React.ReactNode) => (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium">
        {label}
      </label>
      {control}
    </div>
  );
  const numberInput = (id: string, name: "units" | "adults" | "children") => (
    <input
      id={id}
      inputMode="numeric"
      value={form[name]}
      onChange={(event) => set(name, event.target.value)}
      className={inputClass}
    />
  );

  return (
    <Dialog
      open={open}
      onClose={close}
      title={booking ? t("bookings.form.titleEdit") : t("bookings.form.titleNew")}
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {prefill && !booking && (
          <p className="rounded-lg bg-muted px-3 py-2 text-sm">
            {t("bookings.form.fromChat", { name: prefill.guestName })}
          </p>
        )}
        <div className="grid grid-cols-2 gap-3">
          {field(
            "booking-arrival",
            t("bookings.form.arrival"),
            <input
              id="booking-arrival"
              type="date"
              value={form.arrival}
              onChange={(event) => set("arrival", event.target.value)}
              className={inputClass}
            />,
          )}
          {field(
            "booking-departure",
            t("bookings.form.departure"),
            <input
              id="booking-departure"
              type="date"
              value={form.departure}
              min={form.arrival ? addDays(form.arrival, 1) : undefined}
              onChange={(event) => set("departure", event.target.value)}
              className={inputClass}
            />,
          )}
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {field(
            "booking-room",
            t("bookings.form.room"),
            <select
              id="booking-room"
              value={form.roomTypeId}
              onChange={(event) => chooseRoom(event.target.value)}
              className={inputClass}
            >
              <option value="">{t("bookings.form.choose")}</option>
              {rooms.map((room) => (
                <option key={room.id} value={room.id}>
                  {room.name}
                </option>
              ))}
            </select>,
          )}
          {field(
            "booking-plan",
            t("bookings.form.plan"),
            <select
              id="booking-plan"
              value={form.ratePlanId}
              onChange={(event) => set("ratePlanId", event.target.value)}
              disabled={form.roomTypeId === ""}
              className={inputClass}
            >
              <option value="">{t("bookings.form.choose")}</option>
              {sellingPlans.map((plan) => (
                <option key={plan.id} value={plan.id}>
                  {plan.name}
                </option>
              ))}
            </select>,
          )}
        </div>
        <div className="grid grid-cols-3 gap-3">
          {field("booking-units", t("bookings.form.units"), numberInput("booking-units", "units"))}
          {field("booking-adults", t("bookings.form.adults"), numberInput("booking-adults", "adults"))}
          {field(
            "booking-children",
            t("bookings.form.children"),
            numberInput("booking-children", "children"),
          )}
        </div>

        <div aria-live="polite" className="space-y-2 rounded-lg bg-muted px-3 py-2 text-sm">
          {stay === null && <p className="text-muted-foreground">{t("bookings.form.needDates")}</p>}
          {stay !== null && quote === null && !quoteError && (
            <p className="text-muted-foreground">{t("bookings.form.pricing")}</p>
          )}
          {quoteError && <p className="text-destructive">{quoteError}</p>}
          {quote && (
            <>
              <p className="font-medium">
                {t("bookings.form.price", {
                  amount: formatRupiah(quote.total_amount),
                  nights: quote.nights.length,
                })}
              </p>
              {quote.closed_dates.length > 0 && (
                <p>{t("bookings.form.closed", { dates: dates(quote.closed_dates) })}</p>
              )}
              {quote.min_stay !== null && (
                <p>{t("bookings.form.minStay", { nights: quote.min_stay })}</p>
              )}
              {quote.short_dates.length > 0 && (
                <>
                  <p className="font-medium text-destructive">
                    {t("bookings.form.short", { dates: dates(quote.short_dates) })}
                  </p>
                  <label className="flex items-start gap-2">
                    <input
                      type="checkbox"
                      checked={bookAnyway}
                      onChange={(event) => setBookAnyway(event.target.checked)}
                      className="mt-1"
                    />
                    {t("bookings.form.bookAnyway")}
                  </label>
                </>
              )}
            </>
          )}
        </div>

        {field(
          "booking-guest",
          t("bookings.form.guestName"),
          <input
            id="booking-guest"
            value={form.guestName}
            maxLength={NAME_MAX}
            autoComplete="off"
            onChange={(event) => set("guestName", event.target.value)}
            className={inputClass}
          />,
        )}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label htmlFor="booking-phone" className="mb-1 block text-sm font-medium">
              {t("bookings.form.guestPhone")}
            </label>
            <input
              id="booking-phone"
              inputMode="tel"
              value={form.guestPhone}
              autoComplete="off"
              onChange={(event) => set("guestPhone", event.target.value)}
              aria-describedby="booking-phone-hint"
              className={inputClass}
            />
            <p id="booking-phone-hint" className="mt-1 text-xs text-muted-foreground">
              {t("bookings.form.phoneHint")}
            </p>
          </div>
          {field(
            "booking-source",
            t("bookings.form.source"),
            <select
              id="booking-source"
              value={form.source}
              onChange={(event) => set("source", event.target.value as BookingSourceCode)}
              className={inputClass}
            >
              {STAFF_SOURCES.map((source) => (
                <option key={source} value={source}>
                  {t(`bookings.source.${source}`)}
                </option>
              ))}
            </select>,
          )}
        </div>
        <div>
          <label htmlFor="booking-total" className="mb-1 block text-sm font-medium">
            {t("bookings.form.total")}
          </label>
          <input
            id="booking-total"
            inputMode="numeric"
            autoComplete="off"
            value={form.total}
            placeholder={quote ? formatRupiah(quote.total_amount).replace("Rp ", "") : undefined}
            onChange={(event) => set("total", event.target.value)}
            aria-describedby="booking-total-hint"
            className={inputClass}
          />
          <p id="booking-total-hint" className="mt-1 text-xs text-muted-foreground">
            {t("bookings.form.totalHint")}
          </p>
        </div>
        {field(
          "booking-notes",
          t("bookings.form.notes"),
          <textarea
            id="booking-notes"
            rows={2}
            value={form.notes}
            maxLength={NOTES_MAX}
            onChange={(event) => set("notes", event.target.value)}
            className={inputClass}
          />,
        )}
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={close}
            disabled={busy}
            className="rounded-md bg-secondary px-4 py-2 text-sm text-secondary-foreground disabled:opacity-50"
          >
            {t("rooms.form.cancel")}
          </button>
          <button
            type="submit"
            disabled={busy}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {t("rooms.form.save")}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
