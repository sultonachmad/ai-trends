/**
 * Property settings calls (backend: app/routers/settings.py).
 */

import { request } from "@/lib/api-client";

export interface BankAccount {
  bank_name: string | null;
  account_number: string | null;
  account_holder: string | null;
  /** Only the property owner may change these. */
  can_edit: boolean;
}

export type BankAccountInput = Omit<BankAccount, "can_edit">;

const path = "/api/settings/bank-account";

export const fetchBankAccount = () => request<BankAccount>(path);
export const saveBankAccount = (input: BankAccountInput) =>
  request<BankAccount>(path, { method: "PUT", body: JSON.stringify(input) });
