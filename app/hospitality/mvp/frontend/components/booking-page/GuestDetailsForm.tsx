"use client";

import { useRef, useState, type FormEvent } from "react";

import { RoomPlate } from "@/components/booking-page/RoomPlate";
import {
  stayFocus,
  stayInput,
  stayLabel,
  stayPrimaryButton,
  staySecondaryButton,
} from "@/components/booking-page/stay-classes";
import { shortDate } from "@/lib/booking-format";
import {
  changedTotal,
  errorCode,
  freeCancelUntil,
  newCheckoutKey,
  rememberBookingPath,
  termsKey,
} from "@/lib/booking-page-format";
import {
  submitCheckout,
  type RateOption,
  type RoomResult,
  type StayQuery,
} from "@/lib/booking-page-api";
import { useLocale } from "@/lib/locale-store";
import { formatRupiah } from "@/lib/money";

interface GuestDetailsFormProps {
  slug: string;
  stay: StayQuery;
  room: RoomResult;
  option: RateOption;
  depositPercent: number;
  holdMinutes: number;
  whatsapp: string | null;
  roomOrder: readonly string[];
  onBack: () => void;
  onPriceChanged: () => void;
}

/** Name, WhatsApp number, deposit or full, and the terms; then on to payment. */
export function GuestDetailsForm({
  slug,
  stay,
  room,
  option,
  depositPercent,
  holdMinutes,
  whatsapp,
  roomOrder,
  onBack,
  onPriceChanged,
}: GuestDetailsFormProps) {
  const { t, locale } = useLocale();
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [choice, setChoice] = useState<"deposit" | "full">("deposit");
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newPrice, setNewPrice] = useState<string | null>(null);
  // One key per attempt: a double tap or a retry after a lost answer is the same booking.
  const attempt = useRef({ key: newCheckoutKey(), signature: "" });

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const signature = JSON.stringify([name.trim(), phone.trim(), choice, locale]);
    if (attempt.current.signature !== signature) {
      attempt.current = { key: newCheckoutKey(), signature };
    }
    try {
      const result = await submitCheckout(slug, {
        ...stay,
        idempotency_key: attempt.current.key,
        room_type_id: room.id,
        rate_plan_id: option.rate_plan_id,
        guest_name: name.trim(),
        guest_phone: phone.trim(),
        pay_choice: choice,
        expected_total: option.total,
        accepted_terms: accepted,
        language: locale,
      });
      rememberBookingPath(result.pay_url, result.booking_path);
      window.location.assign(result.pay_url);
    } catch (cause) {
      const code = errorCode(cause);
      if (code === "price_changed") setNewPrice(changedTotal(cause));
      setError(t(`book.error.${code}`, { phone: whatsapp ?? "" }));
      setBusy(false);
    }
  };

  const until = freeCancelUntil(stay.arrival, option.free_cancellation_days);
  const due = choice === "full" ? option.total : option.deposit;
  const payLabel = t("book.continuePay", { amount: formatRupiah(due) });
  return (
    <form
      onSubmit={(event) => void submit(event)}
      className="grid gap-x-12 gap-y-8 pt-6 min-[744px]:grid-cols-[minmax(0,1fr)_320px] lg:grid-cols-[minmax(0,1fr)_372px]"
    >
      <div className="space-y-6">
        <button
          type="button"
          disabled={busy}
          onClick={onBack}
          className={`-ml-1 min-h-11 px-1 text-type-button text-stay-ink underline-offset-4 hover:underline disabled:text-stay-muted-soft ${stayFocus}`}
        >
          ‹ {t("book.back")}
        </button>
        <h1 className="text-type-display-xl">{t("book.guestDetails")}</h1>
        <div>
          <label htmlFor="guest-name" className={stayLabel}>
            {t("book.name")}
          </label>
          <input
            id="guest-name"
            required
            maxLength={120}
            autoComplete="name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            className={stayInput}
          />
        </div>
        <div>
          <label htmlFor="guest-phone" className={stayLabel}>
            {t("book.phone")}
          </label>
          <input
            id="guest-phone"
            required
            type="tel"
            inputMode="tel"
            autoComplete="tel"
            maxLength={24}
            placeholder="08…"
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            className={stayInput}
          />
          <p className="mt-2 text-type-caption-sm text-stay-muted">{t("book.phoneHint")}</p>
        </div>
        <fieldset className="space-y-3 border-t border-stay-hairline pt-6">
          <legend className="float-left mb-3 w-full text-type-display-sm">{t("book.payHow")}</legend>
          {(["deposit", "full"] as const).map((value) => (
            <label
              key={value}
              className="clear-both flex min-h-14 cursor-pointer items-center gap-3 rounded-stay-sm border border-stay-hairline p-4 text-type-body-sm transition-colors hover:border-stay-ink has-[:checked]:border-stay-ink has-[:checked]:bg-stay-surface-soft has-[:checked]:outline-1 has-[:checked]:outline-stay-ink has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-stay-ink"
            >
              <input
                type="radio"
                name="pay-choice"
                className="h-5 w-5 shrink-0 accent-stay-ink"
                checked={choice === value}
                onChange={() => setChoice(value)}
              />
              <span>
                {value === "deposit"
                  ? t("book.payDeposit", {
                      percent: depositPercent,
                      amount: formatRupiah(option.deposit),
                    })
                  : t("book.payFull", { amount: formatRupiah(option.total) })}
              </span>
            </label>
          ))}
        </fieldset>
        <p className="rounded-stay-sm bg-stay-surface-soft p-4 text-type-body-sm text-stay-body">
          {t(termsKey(option), { date: until ? shortDate(until, locale) : "" })}{" "}
          {t("book.holdNote", { minutes: holdMinutes })}
        </p>
        <label className="flex min-h-11 cursor-pointer items-start gap-3 text-type-body-sm text-stay-body">
          <input
            type="checkbox"
            required
            className="mt-0.5 h-5 w-5 shrink-0 accent-stay-ink"
            checked={accepted}
            onChange={(event) => setAccepted(event.target.checked)}
          />
          <span>{t("book.acceptTerms")}</span>
        </label>
        {error && (
          <div role="alert" className="space-y-2 text-type-body-sm text-stay-error">
            <p>{error}</p>
            {newPrice && (
              <button type="button" onClick={onPriceChanged} className={staySecondaryButton}>
                {t("book.seeNewPrice", { amount: formatRupiah(newPrice) })}
              </button>
            )}
          </div>
        )}
      </div>
      {/* Not an <aside>: the root layout reads any aside as the staff sidebar. */}
      <div className="min-[744px]:pt-16">
        <div className="space-y-4 rounded-stay-md border border-stay-hairline bg-stay-canvas p-6 shadow-stay min-[744px]:sticky min-[744px]:top-6">
          <div className="flex gap-4">
            <RoomPlate id={room.id} order={roomOrder} className="h-24 w-24 shrink-0 rounded-stay-sm" />
            <div className="min-w-0">
              <h2 className="text-type-title">{room.name}</h2>
              <p className="mt-1 text-type-body-sm text-stay-muted">{option.name}</p>
              <p className="text-type-body-sm text-stay-muted">
                {shortDate(stay.arrival, locale)} – {shortDate(stay.departure, locale)}
              </p>
            </div>
          </div>
          <dl className="space-y-2 border-t border-stay-hairline pt-4 text-type-body-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-stay-muted">{t("book.total")}</dt>
              <dd>{formatRupiah(option.total)}</dd>
            </div>
            <div className="flex justify-between gap-4 text-type-title">
              <dt>{t("book.dueNow")}</dt>
              <dd>{formatRupiah(due)}</dd>
            </div>
          </dl>
          <p className="text-type-caption-sm text-stay-muted">{t("book.allIn")}</p>
          <button
            type="submit"
            disabled={busy || !accepted}
            className={`hidden w-full min-[744px]:block ${stayPrimaryButton}`}
          >
            {payLabel}
          </button>
        </div>
      </div>
      <div className="fixed inset-x-0 bottom-0 z-20 border-t border-stay-hairline bg-stay-canvas px-4 py-3 min-[744px]:hidden">
        <button type="submit" disabled={busy || !accepted} className={`w-full ${stayPrimaryButton}`}>
          {payLabel}
        </button>
      </div>
    </form>
  );
}
