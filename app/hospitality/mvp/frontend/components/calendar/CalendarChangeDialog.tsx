"use client";

import { useEffect, useState, type FormEvent } from "react";

import { Dialog } from "@/components/Dialog";
import { inputClass } from "@/components/rooms/RoomTypeDialog";
import {
  changeCalendar,
  type Calendar,
  type CalendarChange,
  type CalendarChangeInput,
} from "@/lib/calendar-api";
import {
  parseNights,
  rangeProblem,
  weekdayName,
  weekdaysForRequest,
  WEEKDAYS,
} from "@/lib/calendar-grid";
import { useLocale } from "@/lib/locale-store";
import { formatRupiah, parseRupiah } from "@/lib/money";
import type { PriceBounds } from "@/lib/room-forms";

export type ChangeKind = CalendarChange["kind"];
const KINDS: readonly ChangeKind[] = [
  "set_price",
  "clear_price",
  "close",
  "open",
  "set_min_stay",
  "clear_min_stay",
];
const WEEKEND_NIGHTS = [4, 5]; // Friday and Saturday

/** What the dialog starts with: one clicked cell, or a blank bulk change. */
export interface ChangeDraft {
  start: string;
  end: string;
  roomTypeIds: string[];
  kind: ChangeKind;
  ratePlanId?: string;
  amount?: string;
  nights?: string;
}

interface CalendarChangeDialogProps {
  open: boolean;
  draft: ChangeDraft;
  calendar: Calendar;
  bounds: PriceBounds;
  /** Most days one change may cover (property setting). */
  maxDays: number;
  onClose: () => void;
  onApplied: (result: { dates: number; room_types: number }) => void;
}

interface FormState extends ChangeDraft {
  weekdays: number[];
}

type Built = { input: CalendarChangeInput } | { problem: string };

/** Change price, closed dates or minimum stay for a date range, weekdays and room types. */
export function CalendarChangeDialog({
  open,
  draft,
  calendar,
  bounds,
  maxDays,
  onClose,
  onApplied,
}: CalendarChangeDialogProps) {
  const { t, locale } = useLocale();
  const [form, setForm] = useState<FormState>({ ...draft, weekdays: [...WEEKDAYS] });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Start from the clicked cell (or a blank change) each time the dialog opens.
  useEffect(() => {
    if (!open) return;
    setForm({ ...draft, weekdays: [...WEEKDAYS] });
    setError(null);
  }, [open, draft]);

  const rooms = calendar.room_types;
  const plans = [
    ...new Map(rooms.flatMap((room) => room.rate_plans).map((plan) => [plan.id, plan])).values(),
  ];
  const needsPlan = form.kind === "set_price" || form.kind === "clear_price";
  const toggle = (list: "roomTypeIds" | "weekdays", value: string | number) =>
    setForm((current) => {
      const items = current[list] as (string | number)[];
      const next = items.includes(value) ? items.filter((item) => item !== value) : [...items, value];
      return { ...current, [list]: next };
    });

  const change = (): CalendarChange | string => {
    if (needsPlan) {
      const planId = form.ratePlanId ?? "";
      if (planId === "") return t("calendar.form.needPlan");
      const sold = rooms
        .filter((room) => form.roomTypeIds.includes(room.id))
        .every((room) => room.rate_plans.some((plan) => plan.id === planId));
      if (!sold) return t("calendar.form.planNotSold");
      if (form.kind === "clear_price") return { kind: "clear_price", rate_plan_id: planId };
      const amount = parseRupiah(form.amount ?? "");
      if (amount === null || amount < bounds.min || amount > bounds.max) {
        return t("calendar.form.badPrice", {
          min: formatRupiah(bounds.min),
          max: formatRupiah(bounds.max),
        });
      }
      return { kind: "set_price", rate_plan_id: planId, amount };
    }
    if (form.kind === "set_min_stay") {
      const nights = parseNights(form.nights ?? "");
      return nights === null ? t("calendar.form.badNights") : { kind: "set_min_stay", nights };
    }
    return { kind: form.kind } as CalendarChange;
  };

  const build = (): Built => {
    // The weekday chips are only offered for a range; a single date is changed whatever its day.
    const weekdays = form.start === form.end ? [...WEEKDAYS] : form.weekdays;
    const problem = rangeProblem(
      { ...form, weekdays },
      calendar.today,
      calendar.last_editable_date,
      maxDays,
    );
    if (problem) return { problem: t(problem, { max: maxDays, date: calendar.last_editable_date }) };
    const built = change();
    if (typeof built === "string") return { problem: built };
    return {
      input: {
        start: form.start,
        end: form.end,
        weekdays: weekdaysForRequest(weekdays),
        room_type_ids: form.roomTypeIds,
        change: built,
      },
    };
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const built = build();
    if ("problem" in built) return setError(built.problem);
    setBusy(true);
    setError(null);
    try {
      onApplied(await changeCalendar(built.input));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  };

  const close = () => {
    if (!busy) onClose();
  };
  const chip = (on: boolean) =>
    `rounded-md border px-2 py-1 text-sm ${
      on ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card hover:bg-accent"
    }`;

  return (
    <Dialog open={open} onClose={close} title={t("calendar.dialog.title")}>
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <div className="grid grid-cols-2 gap-3">
          {(["start", "end"] as const).map((field) => (
            <div key={field}>
              <label htmlFor={`change-${field}`} className="mb-1 block text-sm font-medium">
                {t(field === "start" ? "calendar.dialog.from" : "calendar.dialog.to")}
              </label>
              <input
                id={`change-${field}`}
                type="date"
                value={form[field]}
                min={calendar.today}
                max={calendar.last_editable_date}
                onChange={(event) => setForm({ ...form, [field]: event.target.value })}
                className={inputClass}
              />
            </div>
          ))}
        </div>
        {form.start !== form.end && (
          <fieldset>
            <legend className="mb-1 text-sm font-medium">{t("calendar.dialog.weekdays")}</legend>
            <div className="flex flex-wrap gap-1">
              {WEEKDAYS.map((day) => (
                <button
                  key={day}
                  type="button"
                  aria-pressed={form.weekdays.includes(day)}
                  aria-label={weekdayName(day, locale, "long")}
                  onClick={() => toggle("weekdays", day)}
                  className={chip(form.weekdays.includes(day))}
                >
                  {weekdayName(day, locale)}
                </button>
              ))}
            </div>
            <div className="mt-2 flex flex-wrap gap-3 text-sm">
              <button
                type="button"
                onClick={() => setForm({ ...form, weekdays: [...WEEKDAYS] })}
                className="font-medium text-primary hover:underline"
              >
                {t("calendar.dialog.everyDay")}
              </button>
              <button
                type="button"
                onClick={() => setForm({ ...form, weekdays: WEEKEND_NIGHTS })}
                className="font-medium text-primary hover:underline"
              >
                {t("calendar.dialog.weekend")}
              </button>
            </div>
          </fieldset>
        )}
        <fieldset>
          <legend className="mb-1 text-sm font-medium">{t("calendar.dialog.rooms")}</legend>
          <div className="flex flex-wrap gap-1">
            {rooms.map((room) => (
              <button
                key={room.id}
                type="button"
                aria-pressed={form.roomTypeIds.includes(room.id)}
                onClick={() => toggle("roomTypeIds", room.id)}
                className={chip(form.roomTypeIds.includes(room.id))}
              >
                {room.name}
              </button>
            ))}
          </div>
        </fieldset>
        <div>
          <label htmlFor="change-kind" className="mb-1 block text-sm font-medium">
            {t("calendar.dialog.what")}
          </label>
          <select
            id="change-kind"
            value={form.kind}
            onChange={(event) => setForm({ ...form, kind: event.target.value as ChangeKind })}
            className={inputClass}
          >
            {KINDS.map((kind) => (
              <option key={kind} value={kind}>
                {t(`calendar.kind.${kind}`)}
              </option>
            ))}
          </select>
        </div>
        {needsPlan && (
          <div>
            <label htmlFor="change-plan" className="mb-1 block text-sm font-medium">
              {t("calendar.dialog.plan")}
            </label>
            <select
              id="change-plan"
              value={form.ratePlanId ?? ""}
              onChange={(event) => setForm({ ...form, ratePlanId: event.target.value })}
              className={inputClass}
            >
              <option value="" disabled>
                —
              </option>
              {plans.map((plan) => (
                <option key={plan.id} value={plan.id}>
                  {plan.name}
                </option>
              ))}
            </select>
          </div>
        )}
        {form.kind === "set_price" && (
          <div>
            <label htmlFor="change-amount" className="mb-1 block text-sm font-medium">
              {t("calendar.dialog.price")}
            </label>
            <input
              id="change-amount"
              inputMode="numeric"
              autoComplete="off"
              value={form.amount ?? ""}
              onChange={(event) => setForm({ ...form, amount: event.target.value })}
              className={inputClass}
            />
          </div>
        )}
        {form.kind === "set_min_stay" && (
          <div>
            <label htmlFor="change-nights" className="mb-1 block text-sm font-medium">
              {t("calendar.dialog.nights")}
            </label>
            <input
              id="change-nights"
              inputMode="numeric"
              value={form.nights ?? ""}
              onChange={(event) => setForm({ ...form, nights: event.target.value })}
              aria-describedby="change-nights-hint"
              className={`${inputClass} max-w-28`}
            />
            <p id="change-nights-hint" className="mt-1 text-xs text-muted-foreground">
              {t("calendar.dialog.nightsHint")}
            </p>
          </div>
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
            {t("calendar.dialog.cancel")}
          </button>
          <button
            type="submit"
            disabled={busy}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {t("calendar.dialog.apply")}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
