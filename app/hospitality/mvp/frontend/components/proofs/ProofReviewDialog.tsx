"use client";

import { useState } from "react";

import { Dialog } from "@/components/Dialog";
import { ProofImage } from "@/components/proofs/ProofImage";
import { formatListTime } from "@/lib/inbox-format";
import { useLocale } from "@/lib/locale-store";
import { formatRupiah } from "@/lib/money";
import { MIN_REASON_LENGTH, proofStateKey } from "@/lib/proof-format";
import { approveProof, rejectProof, type Proof } from "@/lib/transfer-proofs-api";

interface ProofReviewDialogProps {
  proof: Proof | null;
  isOwner: boolean;
  onClose: () => void;
  onDecided: (updated: Proof) => void;
  timeZone?: string;
  /** Whether the viewer may decide on proofs (proofs:edit). */
  canEdit?: boolean;
}

/** The screenshot beside what staff expect, with approve / reject (reason required). */
export function ProofReviewDialog({
  proof,
  isOwner,
  onClose,
  onDecided,
  timeZone,
canEdit = true,
}: ProofReviewDialogProps) {
  const { t, locale } = useLocale();
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const close = () => {
    if (busy) return;
    setRejecting(false);
    setReason("");
    setError(null);
    onClose();
  };

  const decide = async (action: () => Promise<Proof>) => {
    setBusy(true);
    setError(null);
    try {
      const updated = await action();
      setRejecting(false);
      setReason("");
      onDecided(updated);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  };

  const submitRejection = () => {
    const text = reason.trim();
    if (text.length < MIN_REASON_LENGTH) {
      setError(t("proofs.reasonTooShort"));
      return;
    }
    void decide(() => rejectProof(proof!.id, text));
  };

  const when = (iso: string | null) => formatListTime(iso, locale, new Date(), timeZone);
  const undecided =
    proof?.state === "awaiting" || proof?.state === "awaiting_second";
  const decidable = undecided && canEdit;
  const firstOfTwo =
    proof !== null && proof.needs_second_approval && !isOwner && proof.state === "awaiting";

  return (
    <Dialog open={proof !== null} onClose={close} title={t("proofs.title")}>
      {proof && (
        <div className="space-y-4">
          <div className="max-h-[45vh] overflow-auto rounded-lg border border-border bg-muted">
            <ProofImage
              proofId={proof.id}
              available={proof.image_available}
              className="mx-auto max-w-full"
            />
          </div>

          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
            <dt className="text-muted-foreground">{t("proofs.expected")}</dt>
            <dd className="text-lg font-bold">
              {proof.amount ? formatRupiah(proof.amount) : "—"}
            </dd>
            <dt className="text-muted-foreground">{t("proofs.for")}</dt>
            <dd>{proof.description ?? "—"}</dd>
            <dt className="text-muted-foreground">{t("proofs.guest")}</dt>
            <dd>{proof.guest?.name ?? "—"}</dd>
            <dt className="text-muted-foreground">{t("proofs.received")}</dt>
            <dd>
              {when(proof.created_at)} ·{" "}
              {proof.submitted_by_guest
                ? t("proofs.fromGuest")
                : t("proofs.fromStaff", { name: proof.uploaded_by_name ?? "—" })}
            </dd>
          </dl>

          {proof.duplicate_of && (
            <p role="alert" className="rounded-lg border border-destructive p-3 text-sm text-destructive">
              {t("proofs.duplicate", {
                when: when(proof.duplicate_of.created_at),
                what: proof.duplicate_of.description ?? "—",
              })}
            </p>
          )}
          {undecided && proof.needs_second_approval && (
            <p className="rounded-lg bg-muted p-3 text-sm">
              {proof.first_approved_by_name
                ? t("proofs.firstApproved", { name: proof.first_approved_by_name })
                : t("proofs.needsSecond")}
            </p>
          )}
          {!undecided && (
            <p className="rounded-lg bg-muted p-3 text-sm">
              {t("proofs.decidedBy", {
                state: t(proofStateKey(proof.state)),
                name: proof.reviewed_by_name ?? "—",
                when: when(proof.reviewed_at),
              })}
              {proof.rejection_reason && (
                <span className="mt-1 block">
                  {t("proofs.rejectedBecause", { reason: proof.rejection_reason })}
                </span>
              )}
            </p>
          )}

          {rejecting && (
            <div>
              <label htmlFor="reject-reason" className="mb-1 block text-sm font-medium">
                {t("proofs.reason")}
              </label>
              <input
                id="reject-reason"
                maxLength={200}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                placeholder={t("proofs.reasonPlaceholder")}
                className="w-full rounded-md border border-border bg-card px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
          )}
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}

          <div className="flex flex-wrap justify-end gap-2">
            {!undecided && (
              <button type="button" onClick={close} className={secondaryButton}>
                {t("proofs.close")}
              </button>
            )}
            {decidable && rejecting && (
              <>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    setRejecting(false);
                    setError(null);
                  }}
                  className={secondaryButton}
                >
                  {t("proofs.back")}
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={submitRejection}
                  className="rounded-md bg-destructive px-4 py-2 text-sm font-medium text-destructive-foreground disabled:opacity-50"
                >
                  {t("proofs.confirmReject")}
                </button>
              </>
            )}
            {decidable && !rejecting && (
              <>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => setRejecting(true)}
                  className={secondaryButton}
                >
                  {t("proofs.reject")}
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void decide(() => approveProof(proof.id))}
                  className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  {firstOfTwo ? t("proofs.approveFirst") : t("proofs.approve")}
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </Dialog>
  );
}

const secondaryButton =
  "rounded-md bg-secondary px-4 py-2 text-sm text-secondary-foreground disabled:opacity-50";
