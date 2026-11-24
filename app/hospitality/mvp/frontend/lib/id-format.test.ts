import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api-client";
import {
  GUEST_ID_ERROR_CODES,
  ID_PROBLEM_CODES,
  checkIdForm,
  emptyIdForm,
  formFromRead,
  guestIdErrorKey,
  idProblems,
  needsVisa,
} from "@/lib/id-format";
import { LOCALES, translate } from "@/lib/i18n";

const ktp = {
  ...emptyIdForm("ktp"),
  number: " 3171 2305 0190 0001 ",
  fullName: " Budi Santoso ",
  birthDate: "1990-01-05",
  gender: "male" as const,
};

describe("the ID form", () => {
  it("starts empty with Indonesia for a KTP", () => {
    expect(emptyIdForm("ktp").nationality).toBe("ID");
    expect(emptyIdForm("passport").nationality).toBe("");
  });

  it("turns a checked KTP into what the server takes", () => {
    expect(checkIdForm(ktp, { guestId: "g1", scanId: null, checked: true })).toEqual({
      ok: true,
      value: {
        guest_id: "g1",
        doc_type: "ktp",
        number: "3171 2305 0190 0001",
        full_name: "Budi Santoso",
        birth_date: "1990-01-05",
        gender: "male",
        nationality: "ID",
        expires_on: null,
        visa_type: null,
        entry_date: null,
        scan_id: null,
        checked: true,
      },
    });
  });

  it("needs the checked tick, a number and a name", () => {
    expect(checkIdForm(ktp, { guestId: null, scanId: null, checked: false })).toEqual({
      ok: false,
      key: "guestid.needChecked",
    });
    expect(checkIdForm({ ...ktp, number: " " }, { guestId: null, scanId: null, checked: true })).toEqual({
      ok: false,
      key: "guestid.needNumber",
    });
    expect(checkIdForm({ ...ktp, fullName: "" }, { guestId: null, scanId: null, checked: true })).toEqual({
      ok: false,
      key: "guestid.needName",
    });
  });

  it("asks a foreign passport for expiry, visa and entry", () => {
    const passport = { ...emptyIdForm("passport"), number: "PA1234567", fullName: "Anna", nationality: "de" };
    expect(needsVisa(passport)).toBe(true);
    expect(needsVisa({ ...passport, nationality: "ID" })).toBe(false);
    expect(checkIdForm(passport, { guestId: null, scanId: "s", checked: true })).toEqual({
      ok: false,
      key: "guestid.needExpiry",
    });
    expect(
      checkIdForm({ ...passport, nationality: " " }, { guestId: null, scanId: "s", checked: true }),
    ).toEqual({ ok: false, key: "guestid.needNationality" });
    const full = { ...passport, expiresOn: "2030-01-01", visaType: "voa" as const, entryDate: "2026-11-20" };
    const checked = checkIdForm(full, { guestId: null, scanId: "s", checked: true });
    expect(checked.ok && checked.value.nationality).toBe("DE");
    expect(checked.ok && checked.value.visa_type).toBe("voa");
  });

  it("drops visa fields for a KTP even when they were typed", () => {
    const checked = checkIdForm({ ...ktp, visaType: "voa", entryDate: "2026-01-01" }, {
      guestId: null,
      scanId: null,
      checked: true,
    });
    expect(checked.ok && [checked.value.visa_type, checked.value.entry_date]).toEqual([null, null]);
  });

  it("fills the form from what a reader suggested, keeping what it did not know", () => {
    const filled = formFromRead(emptyIdForm("ktp"), {
      number: "3171",
      full_name: "CONTOH",
      birth_date: null,
      gender: "female",
      nationality: null,
      expires_on: null,
      visa_type: "nonsense",
      entry_date: null,
    });
    expect([filled.number, filled.fullName, filled.gender, filled.nationality, filled.visaType]).toEqual([
      "3171",
      "CONTOH",
      "female",
      "ID",
      "",
    ]);
  });
});

describe("refusals", () => {
  it("translates known codes and leaves the rest", () => {
    const missing = new ApiError(409, "x", { code: "id_missing" });
    expect(guestIdErrorKey(missing)).toBe("guestid.error.id_missing");
    expect(guestIdErrorKey(new ApiError(409, "x", { code: "room_occupied" }))).toBe(
      "frontdesk.error.room_occupied",
    );
    expect(guestIdErrorKey(new ApiError(500, "boom"))).toBeNull();
  });

  it("lists field problems by field", () => {
    const invalid = new ApiError(422, "x", {
      code: "id_invalid",
      problems: [
        { code: "nik_gender", field: "gender" },
        { code: "made_up", field: "number" },
      ],
    });
    expect(idProblems(invalid)).toEqual([
      { field: "gender", key: "guestid.problem.nik_gender" },
      { field: "number", key: "guestid.problem.unknown" },
    ]);
    expect(idProblems(new Error("x"))).toEqual([]);
  });

  it("has text for every code in both languages", () => {
    const keys = [
      ...GUEST_ID_ERROR_CODES.map((code) => `guestid.error.${code}`),
      ...ID_PROBLEM_CODES.map((code) => `guestid.problem.${code}`),
      "guestid.problem.unknown",
    ];
    for (const locale of LOCALES) {
      for (const key of keys) expect(translate(locale, key), `${locale} ${key}`).not.toBe(key);
    }
  });
});
