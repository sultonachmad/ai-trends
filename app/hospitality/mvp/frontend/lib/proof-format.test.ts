import { describe, expect, it } from "vitest";

import { LOCALES, translate } from "@/lib/i18n";
import {
  DEFAULT_MAX_PROOF_MB,
  bankFormProblem,
  maxProofMb,
  proofBadgeClass,
  proofFileProblem,
  proofStateKey,
} from "@/lib/proof-format";

const MB = 1024 * 1024;

describe("proofFileProblem", () => {
  it.each(["image/jpeg", "image/png", "image/webp"])("accepts %s", (type) => {
    expect(proofFileProblem({ type, size: 200_000 })).toBeNull();
  });

  it.each([
    [null, "proofs.file.missing"],
    [{ type: "application/pdf", size: 1000 }, "proofs.file.type"],
    [{ type: "image/svg+xml", size: 1000 }, "proofs.file.type"],
    [{ type: "image/gif", size: 1000 }, "proofs.file.type"],
    [{ type: "", size: 1000 }, "proofs.file.type"],
    [{ type: "image/jpeg", size: 0 }, "proofs.file.empty"],
    [{ type: "image/jpeg", size: 5 * MB + 1 }, "proofs.file.tooLarge"],
  ])("rejects %o with %s", (file, problem) => {
    expect(proofFileProblem(file)).toBe(problem);
  });

  it("uses the given size limit", () => {
    expect(proofFileProblem({ type: "image/png", size: 2 * MB }, 1)).toBe("proofs.file.tooLarge");
    expect(proofFileProblem({ type: "image/png", size: 5 * MB })).toBeNull();
  });
});

describe("bankFormProblem", () => {
  const full = { bank_name: "BCA", account_number: "1234567890", account_holder: "PT Villa" };

  it("accepts a complete form and an entirely empty one", () => {
    expect(bankFormProblem(full)).toBeNull();
    expect(bankFormProblem({ bank_name: " ", account_number: "", account_holder: "" })).toBeNull();
  });

  it.each([
    [{ ...full, account_holder: "" }, "settings.bank.incomplete"],
    [{ ...full, bank_name: "B" }, "settings.bank.incomplete"],
    [{ ...full, account_number: "12-34-56" }, "settings.bank.badNumber"],
    [{ ...full, account_number: "1234" }, "settings.bank.badNumber"],
    [{ ...full, account_number: "1".repeat(31) }, "settings.bank.badNumber"],
  ])("rejects %o with %s", (form, problem) => {
    expect(bankFormProblem(form)).toBe(problem);
  });
});

describe("labels", () => {
  const keys = [
    ...["awaiting", "awaiting_second", "approved", "rejected"].map(proofStateKey),
    "proofs.file.missing",
    "proofs.file.type",
    "proofs.file.empty",
    "proofs.file.tooLarge",
    "settings.bank.incomplete",
    "settings.bank.badNumber",
  ];

  it("has every label in both languages", () => {
    for (const key of keys) {
      for (const locale of LOCALES) {
        expect(translate(locale, key, { max: 5 })).not.toBe(key);
      }
    }
  });

  it("gives each kind of state a badge style", () => {
    expect(proofBadgeClass("approved")).toContain("bg-primary");
    expect(proofBadgeClass("awaiting")).toBe(proofBadgeClass("awaiting_second"));
    expect(proofBadgeClass("rejected")).toContain("bg-muted");
  });
});

describe("maxProofMb", () => {
  it("uses the property's setting", () => {
    expect(maxProofMb({ proof_max_upload_mb: 12 })).toBe(12);
  });

  it("falls back to the default when the setting is missing or unusable", () => {
    expect(maxProofMb({})).toBe(DEFAULT_MAX_PROOF_MB);
    expect(maxProofMb({ proof_max_upload_mb: "12" })).toBe(DEFAULT_MAX_PROOF_MB);
    expect(maxProofMb({ proof_max_upload_mb: 0 })).toBe(DEFAULT_MAX_PROOF_MB);
  });
});
