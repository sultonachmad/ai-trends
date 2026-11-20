"use client";

import { useState, type FormEvent } from "react";

import { ApiError } from "@/lib/api-client";
import { Dialog } from "@/components/Dialog";
import { LinkQuotaNotice } from "@/components/payments/LinkQuotaNotice";
import { isBlocked, quotaState, type LinkUsage } from "@/lib/link-quota";
import { useLocale } from "@/lib/locale-store";
import { formatRupiah, parseRupiah } from "@/lib/money";
import { createPaymentLink, type CreatedLink } from "@/lib/payment-links-api";

const DESCRIPTION_MAX = 200;
/** Hours offered in "valid for"; the empty value means the property's default. */
const EXPIRY_CHOICES = [2, 24, 72, 168] as const;
const HOURS_PER_DAY = 24;
const FORBIDDEN = 403;
const inputClass =
  "w-full rounded-md border border-border bg-card px-3 py-2 text-sm text-card-foreground focus:outline-none focus:ring-2 focus:ring-primary";

interface CreateLinkDialogProps {
  open: boolean;
  onClose: () => void;
  onCreated: (created: CreatedLink) => void;
  /** When set, the link is sent into this conversation. */
  conversationId?: string;
  /** The property's allowed range (workspace settings); the server enforces it too. */
  limits?: AmountLimits;
  /** This month's usage against the plan limit; at the limit the form is not offered. */
  quota?: LinkUsage;
  /** The server refused for the limit (the screen was out of date): re-read the usage. */
  onLimitReached?: () => void;
}

export interface AmountLimits {
  min: number;
  max: number;
}

/** Allowed amount range from the workspace's business settings, when present. */
export function amountLimits(settings: Record<string, string | number>): AmountLimits | undefined {
  const min = Number(settings.payment_link_min_amount_idr);
  const max = Number(settings.payment_link_max_amount_idr);
  return Number.isFinite(min) && Number.isFinite(max) ? { min, max } : undefined;
}

/** Form for a new payment link: amount, purpose, optional down-payment total, validity. */
export function CreateLinkDialog({
  open,
  onClose,
  onCreated,
  conversationId,
  limits,
  quota,
  onLimitReached,
}: CreateLinkDialogProps) {
  const { t } = useLocale();
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [isDeposit, setIsDeposit] = useState(false);
  const [total, setTotal] = useState("");
  const [expiry, setExpiry] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setAmount("");
    setDescription("");
    setIsDeposit(false);
    setTotal("");
    setExpiry("");
    setError(null);
  };

  const close = () => {
    if (busy) return;
    reset();
    onClose();
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const payNow = parseRupiah(amount);
    if (payNow === null) return setError(t("links.form.badAmount"));
    if (limits && (payNow < limits.min || payNow > limits.max)) {
      return setError(
        t("links.form.outOfRange", {
          min: formatRupiah(limits.min),
          max: formatRupiah(limits.max),
        }),
      );
    }
    const purpose = description.trim();
    if (purpose === "") return setError(t("links.form.needDescription"));
    const fullTotal = isDeposit ? parseRupiah(total) : null;
    if (isDeposit && (fullTotal === null || fullTotal < payNow)) {
      return setError(t("links.form.badTotal"));
    }
    setBusy(true);
    setError(null);
    try {
      const created = await createPaymentLink({
        amount: payNow,
        description: purpose,
        ...(fullTotal !== null ? { total_amount: fullTotal } : {}),
        ...(expiry ? { expires_in_hours: Number(expiry) } : {}),
        ...(conversationId ? { conversation_id: conversationId } : {}),
      });
      reset();
      onCreated(created);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
      if (cause instanceof ApiError && cause.status === FORBIDDEN) onLimitReached?.();
    } finally {
      setBusy(false);
    }
  };

  const expiryLabel = (hours: number) =>
    hours % HOURS_PER_DAY === 0 && hours > HOURS_PER_DAY
      ? t("links.form.days", { value: hours / HOURS_PER_DAY })
      : t("links.form.hours", { value: hours });

  if (quota && isBlocked(quotaState(quota))) {
    return (
      <Dialog open={open} onClose={close} title={t("quota.reachedTitle")}>
        <div className="space-y-4">
          <LinkQuotaNotice usage={quota} />
          <div className="flex justify-end">
            <button
              type="button"
              onClick={close}
              className="rounded-md bg-secondary px-4 py-2 text-sm text-secondary-foreground"
            >
              {t("quota.close")}
            </button>
          </div>
        </div>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onClose={close} title={t("links.new")}>
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {quota && <LinkQuotaNotice usage={quota} compact />}
        <div>
          <label htmlFor="link-amount" className="mb-1 block text-sm font-medium">
            {t("links.form.amount")}
          </label>
          <input
            id="link-amount"
            inputMode="numeric"
            autoComplete="off"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            aria-describedby="link-amount-hint"
            className={inputClass}
          />
          <p id="link-amount-hint" className="mt-1 text-xs text-muted-foreground">
            {t("links.form.amountHint")}
          </p>
        </div>
        <div>
          <label htmlFor="link-description" className="mb-1 block text-sm font-medium">
            {t("links.form.description")}
          </label>
          <input
            id="link-description"
            maxLength={DESCRIPTION_MAX}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder={t("links.form.descriptionPlaceholder")}
            className={inputClass}
          />
        </div>
        <div className="space-y-2">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={isDeposit}
              onChange={(event) => setIsDeposit(event.target.checked)}
              className="h-4 w-4"
            />
            {t("links.form.isDeposit")}
          </label>
          {isDeposit && (
            <div>
              <label htmlFor="link-total" className="mb-1 block text-sm font-medium">
                {t("links.form.total")}
              </label>
              <input
                id="link-total"
                inputMode="numeric"
                autoComplete="off"
                value={total}
                onChange={(event) => setTotal(event.target.value)}
                className={inputClass}
              />
            </div>
          )}
        </div>
        <div>
          <label htmlFor="link-expiry" className="mb-1 block text-sm font-medium">
            {t("links.form.expiry")}
          </label>
          <select
            id="link-expiry"
            value={expiry}
            onChange={(event) => setExpiry(event.target.value)}
            className={inputClass}
          >
            <option value="">{t("links.form.expiryDefault")}</option>
            {EXPIRY_CHOICES.map((hours) => (
              <option key={hours} value={hours}>
                {expiryLabel(hours)}
              </option>
            ))}
          </select>
        </div>
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
            {t("links.keep")}
          </button>
          <button
            type="submit"
            disabled={busy}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {conversationId ? t("links.form.createAndSend") : t("links.form.create")}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
