"use client";

import { useState } from "react";

import type { PayInstructions } from "@/lib/checkout-api";
import { useLocale } from "@/lib/locale-store";

interface PaymentInstructionsProps {
  instructions: PayInstructions;
}

/** What the guest needs to pay: a (simulated) QRIS box or a virtual account number. */
export function PaymentInstructions({ instructions }: PaymentInstructionsProps) {
  const { t } = useLocale();
  const [copied, setCopied] = useState(false);

  const copyNumber = async () => {
    if (!instructions.va_number) return;
    try {
      await navigator.clipboard.writeText(instructions.va_number);
      setCopied(true);
    } catch {
      setCopied(false); // clipboard blocked: the number is on screen to copy by hand
    }
  };

  if (instructions.method === "qris") {
    return (
      <section aria-labelledby="qris-heading" className="space-y-3">
        <h2 id="qris-heading" className="text-base font-semibold">
          {t("pay.qrisTitle")}
        </h2>
        <div className="rounded-lg border border-dashed border-border bg-muted p-4 text-center">
          <p className="break-all font-mono text-xs">{instructions.qris_payload}</p>
        </div>
        <p className="text-xs text-muted-foreground">{t("pay.qrisSimulated")}</p>
      </section>
    );
  }

  return (
    <section aria-labelledby="va-heading" className="space-y-3">
      <h2 id="va-heading" className="text-base font-semibold">
        {t("pay.vaTitle")}
      </h2>
      <dl className="space-y-2 rounded-lg border border-border bg-muted p-4 text-sm">
        <div className="flex justify-between gap-3">
          <dt className="text-muted-foreground">{t("pay.bank")}</dt>
          <dd className="font-medium">{instructions.va_bank}</dd>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <dt className="text-muted-foreground">{t("pay.vaNumber")}</dt>
          <dd className="font-mono text-base font-semibold tracking-wider">
            {instructions.va_number}
          </dd>
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
  );
}
