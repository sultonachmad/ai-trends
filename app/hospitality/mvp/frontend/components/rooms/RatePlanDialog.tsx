"use client";

import { useEffect, useState, type FormEvent } from "react";

import { Dialog } from "@/components/Dialog";
import { inputClass } from "@/components/rooms/RoomTypeDialog";
import { useLocale } from "@/lib/locale-store";
import { formatRupiah } from "@/lib/money";
import {
  createRatePlan,
  updateRatePlan,
  type MealPlan,
  type RatePlan,
} from "@/lib/rate-plans-api";
import { checkRatePlan, type PriceBounds, type RatePlanForm } from "@/lib/room-forms";
import type { RoomType } from "@/lib/rooms-api";

const NAME_MAX = 80;
const MEALS: readonly MealPlan[] = ["room_only", "breakfast"];

interface RatePlanDialogProps {
  open: boolean;
  onClose: () => void;
  onSaved: (plan: RatePlan) => void;
  /** The plan to edit; omitted to create one. */
  plan?: RatePlan;
  /** Room types in use: each can be given a price. */
  rooms: RoomType[];
  bounds: PriceBounds;
  /** The property's default days of free cancellation. */
  defaultFreeDays: number;
}

const wholeRupiah = (amount: string) => String(Math.trunc(Number(amount)));

function formOf(plan: RatePlan | undefined, defaultFreeDays: number): RatePlanForm {
  if (!plan) {
    return {
      name: "",
      mealPlan: "room_only",
      nonRefundable: false,
      freeDays: String(defaultFreeDays),
      prices: {},
    };
  }
  return {
    name: plan.name,
    mealPlan: plan.meal_plan,
    nonRefundable: plan.non_refundable,
    freeDays: String(plan.free_cancellation_days ?? defaultFreeDays),
    prices: Object.fromEntries(
      plan.prices.map((price) => [price.room_type_id, wholeRupiah(price.amount)]),
    ),
  };
}

/** Create or edit a rate plan: name, meals, cancellation terms, a price per room type. */
export function RatePlanDialog({
  open,
  onClose,
  onSaved,
  plan,
  rooms,
  bounds,
  defaultFreeDays,
}: RatePlanDialogProps) {
  const { t } = useLocale();
  const [form, setForm] = useState<RatePlanForm>(() => formOf(undefined, defaultFreeDays));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Start from the plan being edited (or a blank form) each time the dialog opens.
  useEffect(() => {
    if (!open) return;
    setForm(formOf(plan, defaultFreeDays));
    setError(null);
  }, [open, plan, defaultFreeDays]);

  const close = () => {
    if (!busy) onClose();
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const checked = checkRatePlan(form, rooms, bounds, formatRupiah);
    if (!checked.ok) return setError(t(checked.problem.key, checked.problem.vars));
    setBusy(true);
    setError(null);
    try {
      const saved = plan
        ? await updateRatePlan(plan.id, checked.value)
        : await createRatePlan(checked.value);
      onSaved(saved);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  };

  const title = plan ? t("rates.form.titleEdit") : t("rates.form.titleNew");
  return (
    <Dialog open={open} onClose={close} title={title}>
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <div>
          <label htmlFor="plan-name" className="mb-1 block text-sm font-medium">
            {t("rates.form.name")}
          </label>
          <input
            id="plan-name"
            value={form.name}
            maxLength={NAME_MAX}
            autoComplete="off"
            onChange={(event) => setForm({ ...form, name: event.target.value })}
            aria-describedby="plan-name-hint"
            className={inputClass}
          />
          <p id="plan-name-hint" className="mt-1 text-xs text-muted-foreground">
            {t("rates.form.nameHint")}
          </p>
        </div>
        <div>
          <label htmlFor="plan-meal" className="mb-1 block text-sm font-medium">
            {t("rates.form.meal")}
          </label>
          <select
            id="plan-meal"
            value={form.mealPlan}
            onChange={(event) => setForm({ ...form, mealPlan: event.target.value as MealPlan })}
            className={inputClass}
          >
            {MEALS.map((meal) => (
              <option key={meal} value={meal}>
                {t(`rates.meal.${meal}`)}
              </option>
            ))}
          </select>
        </div>
        <fieldset>
          <legend className="mb-1 text-sm font-medium">{t("rates.form.terms")}</legend>
          <div className="space-y-2 text-sm">
            <label className="flex items-center gap-2">
              <input
                type="radio"
                name="plan-terms"
                checked={!form.nonRefundable}
                onChange={() => setForm({ ...form, nonRefundable: false })}
              />
              {t("rates.form.termsFree")}
            </label>
            {!form.nonRefundable && (
              <div className="pl-6">
                <label htmlFor="plan-days" className="mb-1 block text-xs text-muted-foreground">
                  {t("rates.form.freeDays")}
                </label>
                <input
                  id="plan-days"
                  inputMode="numeric"
                  value={form.freeDays}
                  onChange={(event) => setForm({ ...form, freeDays: event.target.value })}
                  className={`${inputClass} max-w-28`}
                />
              </div>
            )}
            <label className="flex items-center gap-2">
              <input
                type="radio"
                name="plan-terms"
                checked={form.nonRefundable}
                onChange={() => setForm({ ...form, nonRefundable: true })}
              />
              {t("rates.terms.nonRefundable")}
            </label>
          </div>
        </fieldset>
        <fieldset>
          <legend className="mb-1 text-sm font-medium">{t("rates.form.prices")}</legend>
          <p className="mb-2 text-xs text-muted-foreground">{t("rates.form.pricesHint")}</p>
          <div className="space-y-2">
            {rooms.map((room) => (
              <div key={room.id} className="flex items-center gap-3">
                <label htmlFor={`plan-price-${room.id}`} className="min-w-0 flex-1 truncate text-sm">
                  {room.name}
                </label>
                <input
                  id={`plan-price-${room.id}`}
                  inputMode="numeric"
                  autoComplete="off"
                  value={form.prices[room.id] ?? ""}
                  onChange={(event) =>
                    setForm({ ...form, prices: { ...form.prices, [room.id]: event.target.value } })
                  }
                  className={`${inputClass} max-w-40 text-right`}
                />
              </div>
            ))}
          </div>
        </fieldset>
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
