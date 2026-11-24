"use client";

import { useEffect, useState, type FormEvent } from "react";

import { inputClass } from "@/components/rooms/RoomTypeDialog";
import { lineLabelKey } from "@/lib/bill-format";
import { shortDate } from "@/lib/booking-format";
import { CHARGE_CATEGORIES, type ChargeCategory } from "@/lib/bills-api";
import { useLocale } from "@/lib/locale-store";
import { formatRupiah } from "@/lib/money";
import { checkTaxForm, examplePrice, type TaxForm } from "@/lib/tax-format";
import { fetchTaxSettings, saveTaxSettings, type TaxSettings } from "@/lib/taxes-api";
import { todayIn } from "@/lib/calendar-grid";
import { fetchWorkspace } from "@/lib/workspace-api";

const EXAMPLE = 500000;
const label = "mb-1 block text-sm font-medium";
const errorText = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));

function toForm(settings: TaxSettings, today: string): TaxForm {
  return {
    regionCode: settings.region_code ?? "",
    pbjt: settings.confirmed ? String(Number(settings.pbjt_pct)) : "10",
    service: settings.confirmed ? String(Number(settings.service_pct)) : "0",
    pbjtOnService: settings.pbjt_on_service,
    mode: settings.price_mode,
    untaxed: (settings.confirmed ? settings.untaxed_categories : ["transport"]) as ChargeCategory[],
    effectiveFrom: today,
    confirmed: false,
  };
}

/** Region, service charge, PBJT and price mode. Nothing is taxed until the owner confirms. */
export function TaxSection({ canEdit }: { canEdit: boolean }) {
  const { t, locale } = useLocale();
  const [settings, setSettings] = useState<TaxSettings | null>(null);
  const [form, setForm] = useState<TaxForm | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [today, setToday] = useState("");

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchTaxSettings(), fetchWorkspace()])
      .then(([found, workspace]) => {
        if (cancelled) return;
        const now = todayIn(workspace.property.timezone);
        setToday(now);
        setSettings(found);
        setForm(toForm(found, now));
      })
      .catch((cause) => {
        if (!cancelled) setError(errorText(cause));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const change = (patch: Partial<TaxForm>) => {
    setSaved(false);
    setForm((current) => (current ? { ...current, ...patch } : current));
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!form) return;
    const checked = checkTaxForm(form, today);
    if (!checked.ok) return setError(t(checked.key));
    setBusy(true);
    setError(null);
    try {
      const updated = await saveTaxSettings(checked.value);
      setSettings(updated);
      setForm({ ...toForm(updated, today), confirmed: false });
      setSaved(true);
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy(false);
    }
  };

  const editable = canEdit && (settings?.can_edit ?? false);
  const example =
    form && Number.isFinite(Number(form.pbjt.replace(",", "."))) && Number.isFinite(Number(form.service.replace(",", ".")))
      ? examplePrice(
          EXAMPLE,
          Number(form.pbjt.replace(",", ".")),
          Number(form.service.replace(",", ".")),
          form.pbjtOnService,
          form.mode,
        )
      : null;
  return (
    <section className="rounded-xl border border-border bg-card p-6 text-card-foreground shadow-sm">
      <h2 className="text-lg font-semibold">{t("settings.taxes.title")}</h2>
      <p className="mb-4 mt-1 text-sm text-muted-foreground">{t("settings.taxes.intro")}</p>
      {settings && !settings.confirmed && (
        <p role="status" className="mb-4 rounded-lg bg-accent px-3 py-2 text-sm text-accent-foreground">
          {t("settings.taxes.notSet")}
        </p>
      )}
      {settings && !settings.can_edit && (
        <p className="mb-4 text-sm text-muted-foreground">{t("settings.taxes.ownerOnly")}</p>
      )}
      {settings?.upcoming && (
        <p className="mb-4 text-sm">
          {t("settings.taxes.upcoming", {
            date: shortDate(settings.upcoming.effective_from, locale),
            pbjt: Number(settings.upcoming.pbjt_pct),
            service: Number(settings.upcoming.service_pct),
          })}
        </p>
      )}
      {!form ? (
        <p className="text-sm text-muted-foreground">{error ?? t("common.loading")}</p>
      ) : (
        <form onSubmit={(event) => void onSubmit(event)} noValidate className="space-y-4">
          <fieldset disabled={!editable || busy} className="space-y-4">
            <div>
              <label htmlFor="tax-region" className={label}>{t("settings.taxes.region")}</label>
              <select
                id="tax-region"
                value={form.regionCode}
                onChange={(event) => change({ regionCode: event.target.value })}
                className={inputClass}
              >
                <option value="">{t("settings.taxes.chooseRegion")}</option>
                {settings?.regions.map((region) => (
                  <option key={region.code} value={region.code}>
                    {region.code === "other"
                      ? t("settings.taxes.otherRegion")
                      : `${region.name}, ${region.province}`}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-xs text-muted-foreground">{t("settings.taxes.unverified")}</p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="tax-pbjt" className={label}>{t("settings.taxes.pbjt")}</label>
                <input
                  id="tax-pbjt"
                  inputMode="decimal"
                  value={form.pbjt}
                  onChange={(event) => change({ pbjt: event.target.value })}
                  className={inputClass}
                />
              </div>
              <div>
                <label htmlFor="tax-service" className={label}>{t("settings.taxes.service")}</label>
                <input
                  id="tax-service"
                  inputMode="decimal"
                  value={form.service}
                  onChange={(event) => change({ service: event.target.value })}
                  className={inputClass}
                />
              </div>
            </div>
            <label className="flex min-h-11 items-center gap-3 text-sm">
              <input
                type="checkbox"
                checked={form.pbjtOnService}
                onChange={(event) => change({ pbjtOnService: event.target.checked })}
              />
              {t("settings.taxes.pbjtOnService")}
            </label>
            <fieldset className="space-y-2">
              <legend className={label}>{t("settings.taxes.mode")}</legend>
              {(["nett", "plus_plus"] as const).map((mode) => (
                <label key={mode} className="flex min-h-11 items-start gap-3 rounded-md border border-border px-3 py-2 text-sm">
                  <input
                    type="radio"
                    name="tax-mode"
                    checked={form.mode === mode}
                    onChange={() => change({ mode })}
                    className="mt-1"
                  />
                  <span>
                    <span className="block font-medium">{t(`settings.taxes.mode.${mode}`)}</span>
                    <span className="text-xs text-muted-foreground">{t(`settings.taxes.mode.${mode}.hint`)}</span>
                  </span>
                </label>
              ))}
            </fieldset>
            {example && (
              <p className="rounded-lg bg-muted px-3 py-2 text-sm">
                {t("settings.taxes.example", {
                  base: formatRupiah(String(example.base)),
                  service: formatRupiah(String(example.service)),
                  pbjt: formatRupiah(String(example.pbjt)),
                  total: formatRupiah(String(example.total)),
                })}
              </p>
            )}
            <fieldset>
              <legend className={label}>{t("settings.taxes.taxed")}</legend>
              <div className="grid gap-2 sm:grid-cols-2">
                {CHARGE_CATEGORIES.map((category) => (
                  <label key={category} className="flex min-h-11 items-center gap-3 text-sm">
                    <input
                      type="checkbox"
                      checked={!form.untaxed.includes(category)}
                      onChange={(event) =>
                        change({
                          untaxed: event.target.checked
                            ? form.untaxed.filter((name) => name !== category)
                            : [...form.untaxed, category],
                        })
                      }
                    />
                    {t(lineLabelKey(category))}
                  </label>
                ))}
              </div>
            </fieldset>
            <div>
              <label htmlFor="tax-from" className={label}>{t("settings.taxes.from")}</label>
              <input
                id="tax-from"
                type="date"
                min={today}
                value={form.effectiveFrom}
                onChange={(event) => change({ effectiveFrom: event.target.value })}
                className={inputClass}
              />
              <p className="mt-1 text-xs text-muted-foreground">{t("settings.taxes.modeNote")}</p>
            </div>
            <label className="flex min-h-11 items-start gap-3 rounded-md border border-primary/40 px-3 py-2 text-sm">
              <input
                type="checkbox"
                checked={form.confirmed}
                onChange={(event) => change({ confirmed: event.target.checked })}
                className="mt-1"
              />
              {t("settings.taxes.confirm")}
            </label>
          </fieldset>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          {saved && (
            <p role="status" className="text-sm">
              {t("settings.taxes.saved")}
            </p>
          )}
          {editable && (
            <button
              type="submit"
              disabled={busy}
              className="min-h-11 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {t("settings.taxes.save")}
            </button>
          )}
        </form>
      )}
    </section>
  );
}
