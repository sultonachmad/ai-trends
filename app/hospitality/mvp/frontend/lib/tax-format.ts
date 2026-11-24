/** Pure helpers for tax settings. The server repeats every check. */

import type { ChargeCategory } from "@/lib/bills-api";
import type { PriceMode, TaxSettingsInput } from "@/lib/taxes-api";

export const PBJT_MAX = 10; // UU HKPD caps hotel PBJT at 10%
export const SERVICE_MAX = 15;

export interface TaxForm {
  regionCode: string;
  pbjt: string;
  service: string;
  pbjtOnService: boolean;
  mode: PriceMode;
  untaxed: ChargeCategory[];
  effectiveFrom: string;
  confirmed: boolean;
}

type Checked<T> = { ok: true; value: T } | { ok: false; key: string };
const fail = (key: string): { ok: false; key: string } => ({ ok: false, key });

function percent(text: string, max: number): string | null {
  const plain = text.trim().replace(",", ".");
  if (!/^\d{1,2}(\.\d{1,2})?$/.test(plain)) return null;
  return Number(plain) <= max ? plain : null;
}

export function checkTaxForm(form: TaxForm, today: string): Checked<TaxSettingsInput> {
  if (!form.regionCode) return fail("settings.taxes.needRegion");
  const pbjt = percent(form.pbjt, PBJT_MAX);
  const service = percent(form.service, SERVICE_MAX);
  if (pbjt === null || service === null) return fail("settings.taxes.badRate");
  if (!form.effectiveFrom || form.effectiveFrom < today) return fail("settings.taxes.badDate");
  if (!form.confirmed) return fail("settings.taxes.needConfirm");
  return {
    ok: true,
    value: {
      region_code: form.regionCode,
      pbjt_pct: pbjt,
      service_pct: service,
      pbjt_on_service: form.pbjtOnService,
      price_mode: form.mode,
      untaxed_categories: form.untaxed,
      effective_from: form.effectiveFrom,
      confirmed: true,
    },
  };
}

const round = (value: number) => Math.round(value);

/** The same maths as the server's tax engine, for the example on the settings page. */
export function examplePrice(
  amount: number,
  pbjtPct: number,
  servicePct: number,
  pbjtOnService: boolean,
  mode: PriceMode,
) {
  const s = servicePct / 100;
  const p = pbjtPct / 100;
  if (mode === "plus_plus") {
    const service = round(amount * s);
    const pbjt = round((pbjtOnService ? amount + service : amount) * p);
    return { base: amount, service, pbjt, total: amount + service + pbjt };
  }
  const factor = pbjtOnService ? (1 + s) * (1 + p) : 1 + s + p;
  const base = round(amount / factor);
  const service = round(base * s);
  return { base, service, pbjt: amount - base - service, total: amount };
}
