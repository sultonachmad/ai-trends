"use client";

import { useState, type FormEvent } from "react";

import type { PublicLink } from "@/lib/checkout-api";
import { useLocale } from "@/lib/locale-store";
import { formatRupiah } from "@/lib/money";
import { DEFAULT_MAX_PROOF_MB, PROOF_ACCEPT_ATTRIBUTE, proofFileProblem } from "@/lib/proof-format";

interface ManualTransferPanelProps {
  link: PublicLink;
  /** Uploads the file; the guest's agreement to the notice is given by submitting. */
  onUpload: (file: File) => Promise<void>;
}

/**
 * Manual bank transfer for the guest: where to send the money, then the upload of the
 * transfer proof with the storage notice beside the button. Shows "being checked" or
 * "not accepted — reason" for a proof already sent.
 */
export function ManualTransferPanel({ link, onUpload }: ManualTransferPanelProps) {
  const { t } = useLocale();
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const account = link.manual_transfer;
  if (!account) return null;

  const copyNumber = async () => {
    try {
      await navigator.clipboard.writeText(account.account_number);
      setCopied(true);
    } catch {
      setCopied(false); // clipboard blocked: the number is on screen to copy by hand
    }
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const maxMb = account?.max_upload_mb ?? DEFAULT_MAX_PROOF_MB;
    const problem = proofFileProblem(file, maxMb);
    if (problem) return setError(t(problem, { max: maxMb }));
    setBusy(true);
    setError(null);
    try {
      await onUpload(file!);
      setFile(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  };

  const checking = link.proof?.state === "checking";
  return (
    <div className="space-y-4">
      <section aria-labelledby="manual-heading" className="space-y-3">
        <h2 id="manual-heading" className="text-base font-semibold">
          {t("pay.manualTitle")}
        </h2>
        <dl className="space-y-2 rounded-lg border border-border bg-muted p-4 text-sm">
          <div className="flex justify-between gap-3">
            <dt className="text-muted-foreground">{t("pay.bank")}</dt>
            <dd className="font-medium">{account.bank_name}</dd>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <dt className="text-muted-foreground">{t("pay.accountNumber")}</dt>
            <dd className="font-mono text-base font-semibold tracking-wider">
              {account.account_number}
            </dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-muted-foreground">{t("pay.accountHolder")}</dt>
            <dd className="font-medium">{account.account_holder}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-muted-foreground">{t("pay.manualAmount")}</dt>
            <dd className="font-semibold">{formatRupiah(link.amount)}</dd>
          </div>
        </dl>
        <button
          type="button"
          onClick={() => void copyNumber()}
          className="rounded-md border border-border px-3 py-1.5 text-sm font-medium hover:bg-accent"
        >
          {copied ? t("links.created.copied") : t("pay.copyNumber")}
        </button>
      </section>

      {checking ? (
        <p role="status" className="rounded-lg bg-muted p-4 text-sm">
          {t("pay.proofChecking", { property: link.property_name })}
        </p>
      ) : (
        <form onSubmit={onSubmit} className="space-y-3" noValidate>
          <h2 className="text-base font-semibold">{t("pay.proofTitle")}</h2>
          {link.proof?.state === "rejected" && (
            <p role="alert" className="rounded-lg border border-destructive p-3 text-sm text-destructive">
              {t("pay.proofRejected", { reason: link.proof.reason ?? "" })}
              <span className="mt-1 block">{t("pay.proofAgain")}</span>
            </p>
          )}
          <div>
            <label htmlFor="guest-proof" className="mb-1 block text-sm font-medium">
              {t("pay.proofChoose")}
            </label>
            <input
              id="guest-proof"
              type="file"
              accept={PROOF_ACCEPT_ATTRIBUTE}
              onChange={(event) => {
                setFile(event.target.files?.[0] ?? null);
                setError(null);
              }}
              className="block w-full text-sm"
            />
          </div>
          <p className="text-xs text-muted-foreground">
            {t("pay.proofConsent", { property: link.property_name })}
          </p>
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-md bg-primary px-4 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {busy ? t("pay.proofUploading") : t("pay.proofUpload")}
          </button>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
        </form>
      )}
    </div>
  );
}
