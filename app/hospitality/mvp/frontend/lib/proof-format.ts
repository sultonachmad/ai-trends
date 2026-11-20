/**
 * Pure helpers for transfer proofs: file checks before upload, labels, form checks.
 */

export const ACCEPTED_PROOF_TYPES = ["image/jpeg", "image/png", "image/webp"] as const;
export const PROOF_ACCEPT_ATTRIBUTE = ACCEPTED_PROOF_TYPES.join(",");
export const DEFAULT_MAX_PROOF_MB = 5;
const BYTES_PER_MB = 1024 * 1024;

/** i18n key of what is wrong with a chosen file, or null when it can be uploaded. */
export function proofFileProblem(
  file: { type: string; size: number } | null,
  maxMb: number = DEFAULT_MAX_PROOF_MB,
): string | null {
  if (!file) return "proofs.file.missing";
  if (!(ACCEPTED_PROOF_TYPES as readonly string[]).includes(file.type)) return "proofs.file.type";
  if (file.size === 0) return "proofs.file.empty";
  if (file.size > maxMb * BYTES_PER_MB) return "proofs.file.tooLarge";
  return null;
}

export function proofStateKey(state: string): string {
  return `proofs.state.${state}`;
}

/** Tailwind classes for a proof state badge (semantic theme colours only). */
export function proofBadgeClass(state: string): string {
  if (state === "approved") return "bg-primary text-primary-foreground";
  if (state === "awaiting" || state === "awaiting_second") return "bg-accent text-accent-foreground";
  return "bg-muted text-muted-foreground";
}

const ACCOUNT_NUMBER = /^[0-9]{5,30}$/;
const MIN_BANK_TEXT = 2;

export interface BankForm {
  bank_name: string;
  account_number: string;
  account_holder: string;
}

/**
 * i18n key of what is wrong with the bank account form, or null when it can be saved.
 * All three empty is valid: it switches manual transfer off.
 */
export function bankFormProblem(form: BankForm): string | null {
  const values = [form.bank_name.trim(), form.account_number.trim(), form.account_holder.trim()];
  if (values.every((value) => value === "")) return null;
  if (values.some((value) => value === "")) return "settings.bank.incomplete";
  if (!ACCOUNT_NUMBER.test(values[1])) return "settings.bank.badNumber";
  if (values[0].length < MIN_BANK_TEXT || values[2].length < MIN_BANK_TEXT) {
    return "settings.bank.incomplete";
  }
  return null;
}

/** Minimum length of a rejection reason (the backend enforces the same). */
export const MIN_REASON_LENGTH = 3;

/** The property's upload limit from the workspace settings, or the default. */
export function maxProofMb(settings: Record<string, unknown>): number {
  const value = settings.proof_max_upload_mb;
  return typeof value === "number" && value > 0 ? value : DEFAULT_MAX_PROOF_MB;
}
