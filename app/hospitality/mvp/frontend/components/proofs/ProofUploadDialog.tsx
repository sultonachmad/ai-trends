"use client";

import { useEffect, useState, type FormEvent } from "react";

import { Dialog } from "@/components/Dialog";
import { useLocale } from "@/lib/locale-store";
import { formatRupiah, parseRupiah } from "@/lib/money";
import { fetchPaymentLinks, type PaymentLink } from "@/lib/payment-links-api";
import { DEFAULT_MAX_PROOF_MB, PROOF_ACCEPT_ATTRIBUTE, proofFileProblem } from "@/lib/proof-format";
import { uploadStaffProof, type Proof, type ProofTarget } from "@/lib/transfer-proofs-api";

const NO_LINK = "";
const inputClass =
  "w-full rounded-md border border-border bg-card px-3 py-2 text-sm text-card-foreground focus:outline-none focus:ring-2 focus:ring-primary";

interface ProofUploadDialogProps {
  open: boolean;
  onClose: () => void;
  onUploaded: (proof: Proof) => void;
  /** Fixed pay link (from the payment links page). */
  link?: PaymentLink;
  /** Conversation the screenshot arrived in; offers that guest's pending links too. */
  conversationId?: string;
  maxMb?: number;
}

/** Staff record a transfer proof: for a pay link, or for a transfer that had no link. */
export function ProofUploadDialog({
  open,
  onClose,
  onUploaded,
  link,
  conversationId,
  maxMb = DEFAULT_MAX_PROOF_MB,
}: ProofUploadDialogProps) {
  const { t } = useLocale();
  const [file, setFile] = useState<File | null>(null);
  const [choices, setChoices] = useState<PaymentLink[]>([]);
  const [linkId, setLinkId] = useState(NO_LINK);
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // In a conversation, offer the pending links that were sent in it.
  useEffect(() => {
    if (!open || link || !conversationId) {
      setChoices([]);
      return;
    }
    let cancelled = false;
    fetchPaymentLinks("pending")
      .then((page) => {
        if (cancelled) return;
        const mine = page.items.filter((item) => item.conversation_id === conversationId);
        setChoices(mine);
        setLinkId(mine.length > 0 ? mine[0].id : NO_LINK);
      })
      .catch(() => {
        if (!cancelled) setChoices([]); // staff can still record it without a link
      });
    return () => {
      cancelled = true;
    };
  }, [open, link, conversationId]);

  const reset = () => {
    setFile(null);
    setLinkId(NO_LINK);
    setAmount("");
    setDescription("");
    setError(null);
  };

  const close = () => {
    if (busy) return;
    reset();
    onClose();
  };

  const chosenLinkId = link?.id ?? linkId;

  const target = (): ProofTarget | string => {
    if (chosenLinkId !== NO_LINK) return { payment_link_id: chosenLinkId };
    const value = parseRupiah(amount);
    if (value === null) return t("links.form.badAmount");
    const purpose = description.trim();
    if (purpose === "") return t("links.form.needDescription");
    return {
      amount: value,
      description: purpose,
      ...(conversationId ? { conversation_id: conversationId } : {}),
    };
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const fileProblem = proofFileProblem(file, maxMb);
    if (fileProblem) return setError(t(fileProblem, { max: maxMb }));
    const chosen = target();
    if (typeof chosen === "string") return setError(chosen);
    setBusy(true);
    setError(null);
    try {
      const proof = await uploadStaffProof(file!, chosen);
      reset();
      onUploaded(proof);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={close} title={t("proofs.record")}>
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {link && (
          <p className="rounded-lg bg-muted p-3 text-sm">
            <span className="font-semibold">{formatRupiah(link.amount)}</span> · {link.description}
          </p>
        )}
        {!link && choices.length > 0 && (
          <div>
            <label htmlFor="proof-link" className="mb-1 block text-sm font-medium">
              {t("proofs.form.whichLink")}
            </label>
            <select
              id="proof-link"
              value={linkId}
              onChange={(event) => setLinkId(event.target.value)}
              className={inputClass}
            >
              {choices.map((item) => (
                <option key={item.id} value={item.id}>
                  {formatRupiah(item.amount)} · {item.description}
                </option>
              ))}
              <option value={NO_LINK}>{t("proofs.form.noLink")}</option>
            </select>
          </div>
        )}
        {chosenLinkId === NO_LINK && (
          <>
            <div>
              <label htmlFor="proof-amount" className="mb-1 block text-sm font-medium">
                {t("proofs.form.amount")}
              </label>
              <input
                id="proof-amount"
                inputMode="numeric"
                autoComplete="off"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
                className={inputClass}
              />
            </div>
            <div>
              <label htmlFor="proof-description" className="mb-1 block text-sm font-medium">
                {t("proofs.form.description")}
              </label>
              <input
                id="proof-description"
                maxLength={200}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                className={inputClass}
              />
            </div>
          </>
        )}
        <div>
          <label htmlFor="proof-file" className="mb-1 block text-sm font-medium">
            {t("proofs.file")}
          </label>
          <input
            id="proof-file"
            type="file"
            accept={PROOF_ACCEPT_ATTRIBUTE}
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            aria-describedby="proof-file-hint"
            className="block w-full text-sm"
          />
          <p id="proof-file-hint" className="mt-1 text-xs text-muted-foreground">
            {t("proofs.file.hint", { max: maxMb })}
          </p>
        </div>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={close}
            disabled={busy}
            className="rounded-md bg-secondary px-4 py-2 text-sm text-secondary-foreground disabled:opacity-50"
          >
            {t("proofs.close")}
          </button>
          <button
            type="submit"
            disabled={busy}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {t("proofs.form.upload")}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
