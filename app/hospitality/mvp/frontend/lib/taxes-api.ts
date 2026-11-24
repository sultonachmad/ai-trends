/** Tax settings calls (backend: app/routers/settings.py, /api/settings/taxes). */

import { request } from "@/lib/api-client";
import type { ChargeCategory } from "@/lib/bills-api";

export type PriceMode = "nett" | "plus_plus";

export interface TaxRegion {
  code: string;
  name: string;
  province: string;
  suggested_pbjt_pct: string;
  verified: boolean;
}

export interface TaxSettings {
  confirmed: boolean;
  /** Only the owner changes taxes. */
  can_edit: boolean;
  region_code: string | null;
  pbjt_pct: string;
  service_pct: string;
  pbjt_on_service: boolean;
  price_mode: PriceMode;
  untaxed_categories: string[];
  effective_from: string | null;
  upcoming: { effective_from: string; pbjt_pct: string; service_pct: string } | null;
  regions: TaxRegion[];
}

export interface TaxSettingsInput {
  region_code: string;
  pbjt_pct: string;
  service_pct: string;
  pbjt_on_service: boolean;
  price_mode: PriceMode;
  untaxed_categories: ChargeCategory[];
  effective_from: string;
  confirmed: true;
}

const url = "/api/settings/taxes";

export const fetchTaxSettings = () => request<TaxSettings>(url);
export const saveTaxSettings = (input: TaxSettingsInput) =>
  request<TaxSettings>(url, { method: "PUT", body: JSON.stringify(input) });
