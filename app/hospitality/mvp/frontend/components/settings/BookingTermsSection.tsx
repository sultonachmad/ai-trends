"use client";

import { useEffect, useState, type FormEvent } from "react";

import { useLocale } from "@/lib/locale-store";
import { parseWhole } from "@/lib/room-forms";
import { fetchBookingTerms, saveBookingTerms } from "@/lib/settings-api";

const MIN_PERCENT = 10;
const MAX_PERCENT = 100;
const errorText = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));

/** The deposit ("DP") share for direct bookings. Everyone sees it; the owner edits it. */
export function BookingTermsSection() {
  const { t } = useLocale();
  const [percent, setPercent] = useState("");
  const [canEdit, setCanEdit] = useState(false);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchBookingTerms()
      .then((terms) => {
        if (cancelled) return;
        setPercent(String(terms.deposit_percent));
        setCanEdit(terms.can_edit);
        setReady(true);
      })
      .catch((cause) => {
        if (!cancelled) setError(errorText(cause));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const value = parseWhole(percent, MIN_PERCENT, MAX_PERCENT);
    if (value === null) return setError(t("settings.terms.bad"));
    setBusy(true);
    setError(null);
    try {
      const terms = await saveBookingTerms(value);
      setPercent(String(terms.deposit_percent));
      setSaved(true);
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-xl border border-border bg-card p-6 text-card-foreground shadow-sm">
      <h2 className="text-lg font-semibold">{t("settings.terms.title")}</h2>
      <p className="mb-4 mt-1 text-sm text-muted-foreground">{t("settings.terms.intro")}</p>
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <div>
          <label htmlFor="terms-deposit" className="mb-1 block text-sm font-medium">
            {t("settings.terms.deposit")}
          </label>
          <input
            id="terms-deposit"
            inputMode="numeric"
            value={percent}
            disabled={!ready || !canEdit || busy}
            onChange={(event) => {
              setPercent(event.target.value);
              setSaved(false);
              setError(null);
            }}
            className="w-28 rounded-md border border-border bg-card px-3 py-2 text-sm text-card-foreground focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-60"
          />
        </div>
        {ready && !canEdit && (
          <p className="text-sm text-muted-foreground">{t("settings.bank.ownerOnly")}</p>
        )}
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        {saved && (
          <p role="status" className="text-sm font-medium">
            {t("settings.bank.saved")}
          </p>
        )}
        {canEdit && (
          <button
            type="submit"
            disabled={busy}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {t("settings.bank.save")}
          </button>
        )}
      </form>
    </section>
  );
}
