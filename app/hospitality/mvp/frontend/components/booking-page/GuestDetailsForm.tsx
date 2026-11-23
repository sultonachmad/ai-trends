"use client";

import { useRef, useState, type FormEvent } from "react";

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

const inputClass =
  "w-full rounded-md border border-border bg-card px-3 py-2 text-base text-card-foreground focus:outline-none focus:ring-2 focus:ring-primary";
const labelClass = "mb-1 block text-sm font-medium";

interface GuestDetailsFormProps {
  slug: string;
  stay: StayQuery;
  room: RoomResult;
  option: RateOption;
  depositPercent: number;
  holdMinutes: number;
  whatsapp: string | null;
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
  return (
    <form
      onSubmit={(event) => void submit(event)}
      className="space-y-4 rounded-xl border border-border bg-card p-4 text-card-foreground shadow-sm"
    >
      <div>
        <h2 className="text-lg font-semibold">{room.name}</h2>
        <p className="text-sm text-muted-foreground">
          {option.name} · {shortDate(stay.arrival, locale)} – {shortDate(stay.departure, locale)}
        </p>
        <p className="mt-1 font-bold">{formatRupiah(option.total)}</p>
        <p className="text-xs text-muted-foreground">{t("book.allIn")}</p>
      </div>
      <div>
        <label htmlFor="guest-name" className={labelClass}>
          {t("book.name")}
        </label>
        <input
          id="guest-name"
          required
          maxLength={120}
          autoComplete="name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          className={inputClass}
        />
      </div>
      <div>
        <label htmlFor="guest-phone" className={labelClass}>
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
          className={inputClass}
        />
        <p className="mt-1 text-xs text-muted-foreground">{t("book.phoneHint")}</p>
      </div>
      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">{t("book.payHow")}</legend>
        {(["deposit", "full"] as const).map((value) => (
          <label
            key={value}
            className="flex min-h-11 cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm"
          >
            <input
              type="radio"
              name="pay-choice"
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
      <p className="rounded-lg bg-muted px-3 py-2 text-sm">
        {t(termsKey(option), { date: until ? shortDate(until, locale) : "" })}{" "}
        {t("book.holdNote", { minutes: holdMinutes })}
      </p>
      <label className="flex min-h-11 cursor-pointer items-start gap-2 text-sm">
        <input
          type="checkbox"
          required
          className="mt-1"
          checked={accepted}
          onChange={(event) => setAccepted(event.target.checked)}
        />
        <span>{t("book.acceptTerms")}</span>
      </label>
      {error && (
        <div role="alert" className="space-y-2 text-sm text-destructive">
          <p>{error}</p>
          {newPrice && (
            <button
              type="button"
              onClick={onPriceChanged}
              className="min-h-11 rounded-md border border-border px-3 py-1 text-foreground hover:bg-accent"
            >
              {t("book.seeNewPrice", { amount: formatRupiah(newPrice) })}
            </button>
          )}
        </div>
      )}
      <div className="flex flex-wrap justify-between gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={onBack}
          className="min-h-11 rounded-md bg-secondary px-4 py-2 text-sm text-secondary-foreground disabled:opacity-50"
        >
          {t("book.back")}
        </button>
        <button
          type="submit"
          disabled={busy || !accepted}
          className="min-h-11 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {t("book.continuePay", { amount: formatRupiah(due) })}
        </button>
      </div>
    </form>
  );
}
