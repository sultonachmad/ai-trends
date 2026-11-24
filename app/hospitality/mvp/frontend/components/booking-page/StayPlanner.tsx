"use client";

import type { FormEvent } from "react";

import { stayLabel, stayPrimaryButton, stayFocus } from "@/components/booking-page/stay-classes";
import { addDays } from "@/lib/booking-page-format";
import { useLocale } from "@/lib/locale-store";

const FORM_ID = "stay-search";
const MAX_GUESTS = 50;

interface StepperProps {
  label: string;
  value: number;
  min: number;
  onChange: (value: number) => void;
}

function GuestStepper({ label, value, min, onChange }: StepperProps) {
  const { t } = useLocale();
  const button = `flex h-10 w-10 items-center justify-center rounded-full border border-stay-border-strong bg-stay-canvas text-lg text-stay-ink transition-colors hover:border-stay-ink aria-disabled:cursor-not-allowed aria-disabled:border-stay-hairline aria-disabled:text-stay-muted-soft ${stayFocus}`;
  // aria-disabled, not disabled: a button that hits its limit must keep keyboard focus.
  const atMin = value <= min;
  const atMax = value >= MAX_GUESTS;
  return (
    <div className="flex items-center justify-between py-2">
      <span className="text-type-body">{label}</span>
      <div className="flex items-center gap-3">
        <button
          type="button"
          aria-label={t("book.fewer", { label })}
          aria-disabled={atMin}
          onClick={() => {
            if (!atMin) onChange(value - 1);
          }}
          className={button}
        >
          −
        </button>
        <output aria-live="polite" className="w-6 text-center text-type-body">
          {value}
        </output>
        <button
          type="button"
          aria-label={t("book.more", { label })}
          aria-disabled={atMax}
          onClick={() => {
            if (!atMax) onChange(value + 1);
          }}
          className={button}
        >
          +
        </button>
      </div>
    </div>
  );
}

interface StayPlannerProps {
  today: string;
  lastArrival: string;
  arrival: string;
  departure: string;
  adults: number;
  childCount: number;
  nights: number;
  tooLong: boolean;
  busy: boolean;
  onArrival: (value: string) => void;
  onDeparture: (value: string) => void;
  onAdults: (value: number) => void;
  onChildren: (value: number) => void;
  onSubmit: (event: FormEvent) => void;
}

/** The reservation card; on phones its button moves to a bar fixed at the bottom. */
export function StayPlanner({
  today,
  lastArrival,
  arrival,
  departure,
  adults,
  childCount,
  nights,
  tooLong,
  busy,
  onArrival,
  onDeparture,
  onAdults,
  onChildren,
  onSubmit,
}: StayPlannerProps) {
  const { t } = useLocale();
  const disabled = busy || nights < 1 || tooLong;
  const cta = t(busy ? "book.searching" : "book.search");
  const summary = nights > 0 ? t("book.nights", { nights }) : t("book.pickDates");
  const dateClass =
    "w-full bg-transparent text-type-body-sm text-stay-ink focus:outline-none";
  const segment =
    "block min-w-0 p-3 focus-within:rounded-stay-sm focus-within:outline-2 focus-within:-outline-offset-2 focus-within:outline-stay-ink";
  return (
    <>
      <form
        id={FORM_ID}
        onSubmit={onSubmit}
        className="space-y-4 rounded-stay-md border border-stay-hairline bg-stay-canvas p-6 shadow-stay"
      >
        <div>
          <h2 className="text-type-display-sm">{t("book.planTitle")}</h2>
          <p className="mt-1 text-type-body-sm text-stay-muted">{summary}</p>
        </div>
        <div className="grid grid-cols-2 divide-x divide-stay-hairline rounded-stay-sm border border-stay-border-strong">
          <label className={segment}>
            <span className="block text-type-micro">{t("book.arrival")}</span>
            <input
              type="date"
              required
              min={today}
              max={lastArrival}
              value={arrival}
              onChange={(event) => onArrival(event.target.value)}
              className={dateClass}
            />
          </label>
          <label className={segment}>
            <span className="block text-type-micro">{t("book.departure")}</span>
            <input
              type="date"
              required
              min={arrival ? addDays(arrival, 1) : today}
              value={departure}
              onChange={(event) => onDeparture(event.target.value)}
              className={dateClass}
            />
          </label>
        </div>
        <fieldset>
          <legend className={stayLabel}>{t("book.guests")}</legend>
          <GuestStepper label={t("book.adults")} value={adults} min={1} onChange={onAdults} />
          <GuestStepper label={t("book.children")} value={childCount} min={0} onChange={onChildren} />
        </fieldset>
        {tooLong && (
          <p role="alert" className="text-type-body-sm text-stay-error">
            {t("book.error.stay_too_long")}
          </p>
        )}
        <button
          type="submit"
          disabled={disabled}
          className={`hidden w-full min-[744px]:block ${stayPrimaryButton}`}
        >
          {cta}
        </button>
      </form>
      <div className="fixed inset-x-0 bottom-0 z-20 flex items-center justify-between gap-4 border-t border-stay-hairline bg-stay-canvas px-4 py-3 min-[744px]:hidden">
        <p className="min-w-0 truncate text-type-title">{summary}</p>
        <button type="submit" form={FORM_ID} disabled={disabled} className={`shrink-0 ${stayPrimaryButton}`}>
          {cta}
        </button>
      </div>
    </>
  );
}
