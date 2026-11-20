"use client";

/**
 * Public pay page — a guest opens `/pay/<token>` from the link they were sent.
 * No sign-in: the token in the path is the credential. Bahasa Indonesia by default,
 * with an English switch. The state is re-checked on a timer, so "paid" appears by
 * itself once the gateway reports the payment.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";

import { LanguageSwitch } from "@/components/LanguageSwitch";
import { PaymentInstructions } from "@/components/payments/PaymentInstructions";
import { ApiError } from "@/lib/api-client";
import {
  fetchPublicLink,
  simulatePayment,
  startPayment,
  type PayInstructions,
  type PublicLink,
} from "@/lib/checkout-api";
import { useLocale } from "@/lib/locale-store";
import { formatRupiah } from "@/lib/money";
import { timeLeft, timeLeftKey } from "@/lib/payment-link-format";
import { usePolling } from "@/lib/use-polling";

const POLL_MS = 3000;
const NOT_FOUND_STATUS = 404;
const VIRTUAL_ACCOUNT = "virtual_account";

const errorText = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));
const cardClass = "rounded-xl border border-border bg-card p-6 text-card-foreground shadow-sm";

export default function PayPage() {
  const { token } = useParams<{ token: string }>();
  const { t } = useLocale();
  const [link, setLink] = useState<PublicLink | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [method, setMethod] = useState("qris");
  const [bank, setBank] = useState("");
  const [instructions, setInstructions] = useState<PayInstructions | null>(null);
  const [choosing, setChoosing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // Bumped by every guest action; a poll that started before it is out of date.
  const actionCount = useRef(0);

  const refresh = useCallback(async () => {
    const startedAt = actionCount.current;
    try {
      const fresh = await fetchPublicLink(token);
      if (startedAt !== actionCount.current) return;
      setLink(fresh);
      setLoadError(null);
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === NOT_FOUND_STATUS) {
        setNotFound(true);
        return;
      }
      throw cause;
    }
  }, [token]);

  // After a page reload, show the instructions the server already holds — but never
  // replace what the guest has chosen in this visit with the server's "latest" attempt.
  useEffect(() => {
    if (!link) return;
    if (link.state !== "pending") {
      setInstructions(null);
      return;
    }
    setInstructions((current) => current ?? link.instructions);
  }, [link]);

  usePolling(
    refresh,
    POLL_MS,
    !notFound && (link === null || link.state === "pending"),
    (cause) => {
      if (link === null) setLoadError(errorText(cause));
    },
    token,
  );

  const act = async (action: () => Promise<void>) => {
    if (busy) return;
    setBusy(true);
    setActionError(null);
    actionCount.current += 1;
    try {
      await action();
    } catch (cause) {
      setActionError(errorText(cause));
      await refresh().catch(() => undefined); // the link may have just expired or been paid
    } finally {
      actionCount.current += 1; // polls that overlapped the action are out of date too
      setBusy(false);
    }
  };

  const choose = () =>
    act(async () => {
      const selectedBank = method === VIRTUAL_ACCOUNT ? bank || link?.banks[0] : undefined;
      setInstructions(await startPayment(token, method, selectedBank));
      setChoosing(false);
    });

  const simulate = () =>
    act(async () => setLink(await simulatePayment(token, instructions?.reference)));

  const frame = (content: React.ReactNode) => (
    <div className="mx-auto max-w-md space-y-4 py-6">
      <div className="flex justify-end">
        <LanguageSwitch />
      </div>
      {content}
      <p className="text-center text-xs text-muted-foreground">{t("pay.secure")}</p>
    </div>
  );

  if (notFound) {
    return frame(
      <section className={cardClass}>
        <h1 className="text-xl font-bold">{t("pay.notFoundTitle")}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{t("pay.notFoundBody")}</p>
      </section>,
    );
  }
  if (!link) {
    return frame(
      <section className={cardClass}>
        {loadError ? (
          <p role="alert" className="text-sm text-destructive">
            {t("common.loadFailed", { reason: loadError })}
          </p>
        ) : (
          <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
        )}
      </section>,
    );
  }

  const amount = formatRupiah(link.amount);
  const summary = (
    <header className="space-y-1">
      <p className="text-sm text-muted-foreground">{t("pay.to", { property: link.property_name })}</p>
      <h1 className="text-3xl font-bold">{amount}</h1>
      {link.total_amount && (
        <p className="text-sm text-muted-foreground">
          {t("links.dpOf", { total: formatRupiah(link.total_amount) })}
        </p>
      )}
      {link.description && <p className="text-sm">{link.description}</p>}
    </header>
  );

  if (link.state !== "pending") {
    const titleKey =
      link.state === "paid"
        ? "pay.paidTitle"
        : link.state === "expired"
          ? "pay.expiredTitle"
          : "pay.cancelledTitle";
    return frame(
      <section className={`${cardClass} space-y-4`} aria-live="polite">
        {summary}
        <div className="rounded-lg bg-muted p-4">
          <h2 className="text-lg font-semibold">{t(titleKey)}</h2>
          <p className="mt-1 text-sm">
            {link.state === "paid"
              ? t("pay.paidBody", { property: link.property_name, amount })
              : t("pay.askNew", { property: link.property_name })}
          </p>
        </div>
      </section>,
    );
  }

  const left = timeLeft(link.expires_at);
  const showInstructions = instructions !== null && !choosing;
  return frame(
    <section className={`${cardClass} space-y-5`}>
      {summary}
      {left && (
        <p className="text-xs text-muted-foreground">{t(timeLeftKey(left), { value: left.value })}</p>
      )}

      {showInstructions ? (
        <div className="space-y-4">
          <PaymentInstructions instructions={instructions} />
          <p role="status" className="text-sm text-muted-foreground">
            {t("pay.waiting")}
          </p>
          <button
            type="button"
            onClick={() => setChoosing(true)}
            className="text-sm font-medium text-primary hover:underline"
          >
            {t("pay.changeMethod")}
          </button>
          {link.simulator_enabled && (
            <button
              type="button"
              onClick={() => void simulate()}
              disabled={busy}
              className="block w-full rounded-md border border-dashed border-border px-4 py-2 text-sm font-medium hover:bg-accent disabled:opacity-50"
            >
              {t("pay.simulate")}
            </button>
          )}
        </div>
      ) : (
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            void choose();
          }}
        >
          <fieldset className="space-y-2">
            <legend className="mb-1 text-base font-semibold">{t("pay.choose")}</legend>
            {link.methods.map((option) => (
              <label
                key={option}
                className="flex items-center gap-3 rounded-lg border border-border p-3 text-sm"
              >
                <input
                  type="radio"
                  name="method"
                  value={option}
                  checked={method === option}
                  onChange={() => setMethod(option)}
                  className="h-4 w-4"
                />
                {t(`pay.method.${option}`)}
              </label>
            ))}
          </fieldset>
          {method === VIRTUAL_ACCOUNT && (
            <div>
              <label htmlFor="pay-bank" className="mb-1 block text-sm font-medium">
                {t("pay.bank")}
              </label>
              <select
                id="pay-bank"
                value={bank || link.banks[0]}
                onChange={(event) => setBank(event.target.value)}
                className="w-full rounded-md border border-border bg-card px-3 py-2 text-sm"
              >
                {link.banks.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </div>
          )}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-md bg-primary px-4 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {t("pay.continue")}
          </button>
        </form>
      )}

      {actionError && (
        <p role="alert" className="text-sm text-destructive">
          {t("inbox.actionFailed", { reason: actionError })}
        </p>
      )}
    </section>,
  );
}
