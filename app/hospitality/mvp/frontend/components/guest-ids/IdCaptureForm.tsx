"use client";

import { useRef, useState } from "react";

import { inputClass } from "@/components/rooms/RoomTypeDialog";
import {
  DOC_TYPES,
  GENDERS,
  VISA_TYPES,
  confirmId,
  scanId,
  type BookingGuests,
  type DocType,
} from "@/lib/guest-ids-api";
import {
  checkIdForm,
  emptyIdForm,
  formFromRead,
  guestIdErrorKey,
  idProblems,
  needsVisa,
  type FieldProblem,
  type IdForm,
} from "@/lib/id-format";
import { useLocale } from "@/lib/locale-store";

interface IdCaptureFormProps {
  bookingId: string;
  /** Whose ID this is; null adds a new guest to the booking. */
  guest: { id: string; name: string } | null;
  onSaved: (guests: BookingGuests) => void;
  onCancel: () => void;
}

const secondary =
  "min-h-11 rounded-md border border-border px-4 py-2 text-sm hover:bg-accent disabled:opacity-50";
const primary =
  "min-h-11 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50";
const ACCEPT = "image/jpeg,image/png,image/webp";
const errorText = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));

type TextField = "number" | "fullName" | "birthDate" | "nationality" | "expiresOn" | "entryDate";
const SERVER_FIELD: Record<string, keyof IdForm> = {
  number: "number",
  full_name: "fullName",
  birth_date: "birthDate",
  gender: "gender",
  nationality: "nationality",
  expires_on: "expiresOn",
  visa_type: "visaType",
  entry_date: "entryDate",
};

/** Photo, reader suggestion, every field for staff to check, and the "checked" tick. */
export function IdCaptureForm({ bookingId, guest, onSaved, onCancel }: IdCaptureFormProps) {
  const { t } = useLocale();
  const [form, setForm] = useState<IdForm>(() => emptyIdForm("ktp"));
  const [scan, setScan] = useState<{ id: string; simulated: boolean } | null>(null);
  const [checked, setChecked] = useState(false);
  const [problems, setProblems] = useState<FieldProblem[]>([]);
  const [busy, setBusy] = useState<"reading" | "saving" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const change = (patch: Partial<IdForm>) => {
    setForm((current) => ({ ...current, ...patch }));
    setChecked(false); // a changed field has not been checked yet
  };
  const chooseType = (docType: DocType) => {
    setForm(emptyIdForm(docType));
    setScan(null);
    setChecked(false);
    setProblems([]);
  };
  const fail = (cause: unknown) => {
    const key = guestIdErrorKey(cause);
    setError(key ? t(key) : errorText(cause));
    setProblems(idProblems(cause));
  };

  const readPhoto = async (file: File | undefined) => {
    if (!file) return;
    setBusy("reading");
    setError(null);
    try {
      const result = await scanId(bookingId, form.docType, file);
      setScan({ id: result.scan_id, simulated: result.reader.simulated });
      setForm((current) => formFromRead(current, result.fields));
      setChecked(false);
    } catch (cause) {
      fail(cause);
    } finally {
      setBusy(null);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const save = async () => {
    const result = checkIdForm(form, { guestId: guest?.id ?? null, scanId: scan?.id ?? null, checked });
    if (!result.ok) {
      setError(t(result.key));
      return;
    }
    setBusy("saving");
    setError(null);
    setProblems([]);
    try {
      onSaved(await confirmId(bookingId, result.value));
    } catch (cause) {
      fail(cause);
    } finally {
      setBusy(null);
    }
  };

  const problemOf = (field: keyof IdForm) =>
    problems.filter((p) => SERVER_FIELD[p.field] === field).map((p) => t(p.key));
  const fieldId = (name: string) => `guest-id-${name}`;
  const text = (name: TextField, label: string, type = "text") => {
    const notes = problemOf(name);
    return (
      <div>
        <label htmlFor={fieldId(name)} className="mb-1 block font-medium">
          {label}
        </label>
        <input
          id={fieldId(name)}
          type={type}
          value={form[name]}
          maxLength={name === "fullName" ? 120 : 40}
          inputMode={name === "number" && form.docType === "ktp" ? "numeric" : undefined}
          autoComplete="off"
          aria-invalid={notes.length > 0}
          aria-describedby={notes.length ? `${fieldId(name)}-problem` : undefined}
          onChange={(event) => change({ [name]: event.target.value } as Partial<IdForm>)}
          className={inputClass}
        />
        {notes.length > 0 && (
          <p id={`${fieldId(name)}-problem`} className="mt-1 text-xs text-destructive">
            {notes.join(" ")}
          </p>
        )}
      </div>
    );
  };

  const visa = needsVisa(form);
  return (
    <div className="space-y-3 text-sm">
      <p className="text-muted-foreground">
        {guest ? t("guestid.form.for", { name: guest.name }) : t("guestid.form.newGuest")}
      </p>
      <fieldset className="flex flex-wrap gap-2">
        <legend className="sr-only">{t("guestid.form.title")}</legend>
        {DOC_TYPES.map((docType) => (
          <label
            key={docType}
            className={`flex min-h-11 cursor-pointer items-center gap-2 rounded-md border px-4 py-2 ${
              form.docType === docType ? "border-primary bg-primary/10" : "border-border"
            }`}
          >
            <input
              type="radio"
              name="guest-id-type"
              checked={form.docType === docType}
              onChange={() => chooseType(docType)}
            />
            {t(`guestid.docType.${docType}`)}
          </label>
        ))}
      </fieldset>
      <div className="rounded-lg border border-dashed border-border p-3">
        <label htmlFor={fieldId("photo")} className="mb-2 block font-medium">
          {t("guestid.form.photo")}
        </label>
        <input
          ref={fileRef}
          id={fieldId("photo")}
          type="file"
          accept={ACCEPT}
          capture="environment"
          disabled={busy !== null}
          onChange={(event) => void readPhoto(event.target.files?.[0])}
          className="block w-full text-sm file:mr-3 file:min-h-11 file:rounded-md file:border-0 file:bg-secondary file:px-4 file:text-secondary-foreground"
        />
        {busy === "reading" && <p className="mt-2" role="status">{t("guestid.form.reading")}</p>}
        {scan && <p className="mt-2 text-muted-foreground">{t("guestid.form.photoSaved")}</p>}
      </div>
      {scan?.simulated ? (
        <p role="alert" className="rounded-lg border-2 border-destructive bg-destructive/10 px-3 py-2 font-semibold text-destructive">
          {t("guestid.form.simulated")}
        </p>
      ) : (
        <p className="text-muted-foreground">{t("guestid.form.manual")}</p>
      )}
      {text("number", t(`guestid.field.number.${form.docType}`))}
      {text("fullName", t("guestid.field.fullName"))}
      <div className="grid gap-3 sm:grid-cols-2">
        {text("birthDate", t("guestid.field.birthDate"), "date")}
        <div>
          <label htmlFor={fieldId("gender")} className="mb-1 block font-medium">
            {t("guestid.field.gender")}
          </label>
          <select
            id={fieldId("gender")}
            value={form.gender}
            onChange={(event) => change({ gender: event.target.value as IdForm["gender"] })}
            className={inputClass}
          >
            <option value="">{t("guestid.choose")}</option>
            {GENDERS.map((gender) => (
              <option key={gender} value={gender}>
                {t(`guestid.gender.${gender}`)}
              </option>
            ))}
          </select>
          {problemOf("gender").length > 0 && (
            <p className="mt-1 text-xs text-destructive">{problemOf("gender").join(" ")}</p>
          )}
        </div>
      </div>
      {form.docType === "passport" && (
        <div className="grid gap-3 sm:grid-cols-2">
          {text("nationality", t("guestid.field.nationality"))}
          {text("expiresOn", t("guestid.field.expiresOn"), "date")}
        </div>
      )}
      {visa && (
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label htmlFor={fieldId("visa")} className="mb-1 block font-medium">
              {t("guestid.field.visaType")}
            </label>
            <select
              id={fieldId("visa")}
              value={form.visaType}
              onChange={(event) => change({ visaType: event.target.value as IdForm["visaType"] })}
              className={inputClass}
            >
              <option value="">{t("guestid.choose")}</option>
              {VISA_TYPES.map((type) => (
                <option key={type} value={type}>
                  {t(`guestid.visa.${type}`)}
                </option>
              ))}
            </select>
          </div>
          {text("entryDate", t("guestid.field.entryDate"), "date")}
        </div>
      )}
      <label className="flex min-h-11 cursor-pointer items-start gap-3 rounded-md border border-border px-3 py-2">
        <input
          type="checkbox"
          checked={checked}
          onChange={(event) => setChecked(event.target.checked)}
          className="mt-1 h-5 w-5"
        />
        <span className="font-medium">{t("guestid.form.checked")}</span>
      </label>
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
      <div className="flex flex-wrap justify-end gap-2">
        <button type="button" disabled={busy !== null} onClick={onCancel} className={secondary}>
          {t("frontdesk.back")}
        </button>
        <button type="button" disabled={busy !== null} onClick={() => void save()} className={primary}>
          {t("guestid.form.save")}
        </button>
      </div>
    </div>
  );
}
