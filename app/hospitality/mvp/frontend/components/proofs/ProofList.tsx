"use client";

import { formatListTime } from "@/lib/inbox-format";
import { useLocale } from "@/lib/locale-store";
import { formatRupiah } from "@/lib/money";
import { proofBadgeClass, proofStateKey } from "@/lib/proof-format";
import type { Proof } from "@/lib/transfer-proofs-api";

interface ProofListProps {
  proofs: Proof[];
  onOpen: (proof: Proof) => void;
  timeZone?: string;
}

/** Transfer proofs as rows: amount, purpose, guest, source, state; open to review. */
export function ProofList({ proofs, onOpen, timeZone }: ProofListProps) {
  const { t, locale } = useLocale();
  const now = new Date();

  return (
    <ul className="divide-y divide-border">
      {proofs.map((proof) => {
        const undecided = proof.state === "awaiting" || proof.state === "awaiting_second";
        return (
          <li key={proof.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
            <div className="min-w-0 space-y-0.5">
              <p className="font-semibold">
                {proof.amount ? formatRupiah(proof.amount) : "—"}
                <span className="ml-2 font-normal">{proof.description}</span>
              </p>
              <p className="text-xs text-muted-foreground">
                {proof.guest?.name ? `${proof.guest.name} · ` : ""}
                {proof.submitted_by_guest
                  ? t("proofs.fromGuest")
                  : t("proofs.fromStaff", { name: proof.uploaded_by_name ?? "—" })}
                {" · "}
                {formatListTime(proof.created_at, locale, now, timeZone)}
                {proof.payment_link_id ? "" : ` · ${t("proofs.noLink")}`}
              </p>
              {proof.duplicate_of && (
                <p className="text-xs font-semibold text-destructive">
                  {t("proofs.duplicate", {
                    when: formatListTime(proof.duplicate_of.created_at, locale, now, timeZone),
                    what: proof.duplicate_of.description ?? "—",
                  })}
                </p>
              )}
            </div>
            <div className="flex items-center gap-3">
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-medium ${proofBadgeClass(proof.state)}`}
              >
                {t(proofStateKey(proof.state))}
              </span>
              <button
                type="button"
                onClick={() => onOpen(proof)}
                className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                  undecided
                    ? "bg-primary text-primary-foreground hover:bg-primary/90"
                    : "border border-border hover:bg-accent"
                }`}
              >
                {undecided ? t("proofs.review") : t("proofs.view")}
              </button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
