"use client";

/**
 * Settings — the bank account guests transfer to, and the deposit for direct bookings.
 * Reachable at `/settings`. Every member can see it; only the owner can change it.
 */

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import { LanguageSwitch } from "@/components/LanguageSwitch";
import { BookingTermsSection } from "@/components/settings/BookingTermsSection";
import { useLocale } from "@/lib/locale-store";
import { bankFormProblem, type BankForm } from "@/lib/proof-format";
import { fetchBankAccount, saveBankAccount, type BankAccount } from "@/lib/settings-api";
import { fetchOnboardingStatus } from "@/lib/workspace-api";

const ONBOARDING_PATH = "/onboarding";
const EMPTY: BankForm = { bank_name: "", account_number: "", account_holder: "" };
const inputClass =
  "w-full rounded-md border border-border bg-card px-3 py-2 text-sm text-card-foreground focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-60";

const errorText = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));
const toForm = (account: BankAccount): BankForm => ({
  bank_name: account.bank_name ?? "",
  account_number: account.account_number ?? "",
  account_holder: account.account_holder ?? "",
});
const orNull = (value: string) => (value.trim() === "" ? null : value.trim());

export default function SettingsPage() {
  const router = useRouter();
  const { t } = useLocale();
  const [form, setForm] = useState<BankForm>(EMPTY);
  const [canEdit, setCanEdit] = useState(false);
  const [ready, setReady] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const status = await fetchOnboardingStatus();
        if (cancelled) return;
        if (!status.has_workspace) {
          router.replace(ONBOARDING_PATH);
          return;
        }
        const account = await fetchBankAccount();
        if (cancelled) return;
        setForm(toForm(account));
        setCanEdit(account.can_edit);
        setReady(true);
      } catch (cause) {
        if (!cancelled) setLoadError(errorText(cause));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  const change = (field: keyof BankForm, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
    setSaved(false);
    setError(null);
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const problem = bankFormProblem(form);
    if (problem) return setError(t(problem));
    setBusy(true);
    setError(null);
    try {
      const account = await saveBankAccount({
        bank_name: orNull(form.bank_name),
        account_number: orNull(form.account_number),
        account_holder: orNull(form.account_holder),
      });
      setForm(toForm(account));
      setSaved(true);
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy(false);
    }
  };

  if (loadError) {
    return (
      <p role="alert" className="p-8 text-sm text-destructive">
        {t("common.loadFailed", { reason: loadError })}
      </p>
    );
  }
  if (!ready) {
    return <p className="p-8 text-sm text-muted-foreground">{t("common.loading")}</p>;
  }

  const fields: { name: keyof BankForm; label: string; placeholder?: string; numeric?: boolean }[] = [
    { name: "bank_name", label: t("settings.bank.name"), placeholder: t("settings.bank.namePlaceholder") },
    { name: "account_number", label: t("settings.bank.number"), numeric: true },
    { name: "account_holder", label: t("settings.bank.holder") },
  ];

  return (
    <div className="mx-auto max-w-xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">{t("settings.title")}</h1>
        <LanguageSwitch />
      </div>
      <section className="rounded-xl border border-border bg-card p-6 text-card-foreground shadow-sm">
        <h2 className="text-lg font-semibold">{t("settings.bank.title")}</h2>
        <p className="mb-4 mt-1 text-sm text-muted-foreground">{t("settings.bank.intro")}</p>
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          {fields.map((field) => (
            <div key={field.name}>
              <label htmlFor={`bank-${field.name}`} className="mb-1 block text-sm font-medium">
                {field.label}
              </label>
              <input
                id={`bank-${field.name}`}
                value={form[field.name]}
                disabled={!canEdit || busy}
                inputMode={field.numeric ? "numeric" : undefined}
                autoComplete="off"
                maxLength={80}
                placeholder={field.placeholder}
                onChange={(event) => change(field.name, event.target.value)}
                className={inputClass}
              />
            </div>
          ))}
          {!canEdit && (
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
      <BookingTermsSection />
    </div>
  );
}
