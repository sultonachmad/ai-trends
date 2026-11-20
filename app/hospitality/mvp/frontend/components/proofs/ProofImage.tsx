"use client";

import { useEffect, useState } from "react";

import { ApiError } from "@/lib/api-client";
import { useLocale } from "@/lib/locale-store";
import { fetchProofImage } from "@/lib/transfer-proofs-api";

const GONE_STATUS = 410;

interface ProofImageProps {
  proofId: string;
  available: boolean;
  className?: string;
}

/**
 * The transfer screenshot. It is fetched with the staff session (never by public
 * address) and shown from memory; the temporary address is released on unmount.
 */
export function ProofImage({ proofId, available, className }: ProofImageProps) {
  const { t } = useLocale();
  const [source, setSource] = useState<string | null>(null);
  const [problem, setProblem] = useState<"gone" | "failed" | null>(available ? null : "gone");

  useEffect(() => {
    if (!available) {
      setProblem("gone");
      return;
    }
    let cancelled = false;
    let objectUrl: string | null = null;
    setSource(null);
    setProblem(null);
    fetchProofImage(proofId)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setSource(objectUrl);
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setProblem(cause instanceof ApiError && cause.status === GONE_STATUS ? "gone" : "failed");
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [proofId, available]);

  if (problem) {
    return (
      <p className="rounded-lg bg-muted p-4 text-sm text-muted-foreground">
        {t(problem === "gone" ? "proofs.imageGone" : "proofs.imageFailed")}
      </p>
    );
  }
  if (!source) {
    return <p className="p-4 text-sm text-muted-foreground">{t("common.loading")}</p>;
  }
  // A blob: address from our own fetch — next/image cannot optimise it and must not try.
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={source} alt={t("proofs.imageAlt")} className={className} />;
}
