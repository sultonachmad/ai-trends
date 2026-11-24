/** Pure helpers for the guest ID form: what staff typed, and what the server refused. */

import { ApiError } from "@/lib/api-client";
import { deskErrorKey } from "@/lib/front-desk-format";
import {
  GENDERS,
  VISA_TYPES,
  type ConfirmIdInput,
  type DocType,
  type Gender,
  type ReadFields,
  type VisaType,
} from "@/lib/guest-ids-api";

export const INDONESIA = "ID";
export const GUEST_ID_ERROR_CODES = [
  "stay_closed",
  "guest_not_on_booking",
  "id_not_found",
  "id_number_cleared",
  "id_image_gone",
  "scan_not_usable",
  "main_guest_removal",
  "too_many_guests",
  "image_empty",
  "image_too_large",
  "not_an_image",
  "id_invalid",
  "id_missing",
  "no_id_permission",
  "number_on_other_guest",
  "too_many_scans",
  "try_again",
  "id_unreadable",
] as const;
export const ID_PROBLEM_CODES = [
  "doc_type",
  "name_missing",
  "birth_date_future",
  "nationality",
  "nik_format",
  "nik_region",
  "nik_birth_date",
  "nik_birth_date_mismatch",
  "nik_serial",
  "nik_gender",
  "ktp_not_indonesian",
  "passport_format",
  "nationality_missing",
  "expiry_missing",
  "expired",
  "visa_missing",
  "visa_type",
  "entry_missing",
  "entry_future",
] as const;

export interface IdForm {
  docType: DocType;
  number: string;
  fullName: string;
  birthDate: string;
  gender: Gender | "";
  nationality: string;
  expiresOn: string;
  visaType: VisaType | "";
  entryDate: string;
}

export const emptyIdForm = (docType: DocType): IdForm => ({
  docType,
  number: "",
  fullName: "",
  birthDate: "",
  gender: "",
  nationality: docType === "ktp" ? INDONESIA : "",
  expiresOn: "",
  visaType: "",
  entryDate: "",
});

const isGender = (value: string | null): value is Gender =>
  (GENDERS as readonly string[]).includes(value ?? "");
const isVisa = (value: string | null): value is VisaType =>
  (VISA_TYPES as readonly string[]).includes(value ?? "");

/** The form with what a reader (or an earlier stay) suggested; blanks keep what was there. */
export function formFromRead(form: IdForm, read: ReadFields): IdForm {
  return {
    ...form,
    number: read.number ?? form.number,
    fullName: read.full_name ?? form.fullName,
    birthDate: read.birth_date ?? form.birthDate,
    gender: isGender(read.gender) ? read.gender : form.gender,
    nationality: read.nationality ?? form.nationality,
    expiresOn: read.expires_on ?? form.expiresOn,
    visaType: isVisa(read.visa_type) ? read.visa_type : form.visaType,
    entryDate: read.entry_date ?? form.entryDate,
  };
}

/** A passport of anyone but an Indonesian needs visa type and entry date. */
export const needsVisa = (form: Pick<IdForm, "docType" | "nationality">) =>
  form.docType === "passport" && form.nationality.trim().toUpperCase() !== INDONESIA;

type Checked = { ok: true; value: ConfirmIdInput } | { ok: false; key: string };

interface ConfirmContext {
  guestId: string | null;
  scanId: string | null;
  checked: boolean;
}

function missingKey(form: IdForm, checked: boolean): string | null {
  if (!checked) return "guestid.needChecked";
  if (!form.number.trim()) return "guestid.needNumber";
  if (!form.fullName.trim()) return "guestid.needName";
  if (form.docType === "passport" && !form.nationality.trim()) return "guestid.needNationality";
  if (form.docType === "passport" && !form.expiresOn) return "guestid.needExpiry";
  if (needsVisa(form) && !form.visaType) return "guestid.needVisa";
  if (needsVisa(form) && !form.entryDate) return "guestid.needEntry";
  return null;
}

/** What the server takes, or the key of the first thing still missing. */
export function checkIdForm(form: IdForm, context: ConfirmContext): Checked {
  const missing = missingKey(form, context.checked);
  if (missing) return { ok: false, key: missing };
  const visa = needsVisa(form);
  return {
    ok: true,
    value: {
      guest_id: context.guestId,
      doc_type: form.docType,
      number: form.number.trim(),
      full_name: form.fullName.trim(),
      birth_date: form.birthDate || null,
      gender: form.gender || null,
      nationality: form.nationality.trim().toUpperCase() || null,
      expires_on: form.docType === "passport" ? form.expiresOn || null : null,
      visa_type: visa ? form.visaType || null : null,
      entry_date: visa ? form.entryDate || null : null,
      scan_id: context.scanId,
      checked: true,
    },
  };
}

function detailOf(cause: unknown): { code?: string; problems?: unknown } | null {
  if (!(cause instanceof ApiError) || typeof cause.detail !== "object" || !cause.detail) {
    return null;
  }
  return cause.detail as { code?: string; problems?: unknown };
}

/** i18n key of a guest ID or front desk refusal; null for anything else. */
export function guestIdErrorKey(cause: unknown): string | null {
  const code = detailOf(cause)?.code;
  if (code && (GUEST_ID_ERROR_CODES as readonly string[]).includes(code)) {
    return `guestid.error.${code}`;
  }
  return deskErrorKey(cause);
}

export interface FieldProblem {
  field: string;
  key: string;
}

/** The fields the server found wrong, with the text to show next to each. */
export function idProblems(cause: unknown): FieldProblem[] {
  const problems = detailOf(cause)?.problems;
  if (!Array.isArray(problems)) return [];
  return problems.map((problem: { code?: string; field?: string }) => ({
    field: String(problem.field ?? ""),
    key: (ID_PROBLEM_CODES as readonly string[]).includes(problem.code ?? "")
      ? `guestid.problem.${problem.code}`
      : "guestid.problem.unknown",
  }));
}
