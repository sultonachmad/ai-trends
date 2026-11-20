"use client";

import { useState } from "react";

import { Dialog } from "@/components/Dialog";
import { useLocale } from "@/lib/locale-store";
import { formatRupiah } from "@/lib/money";
import type { CreatedLink } from "@/lib/payment-links-api";

interface LinkCreatedNoticeProps {
  created: CreatedLink | null;
  onClose: () => void;
}

/** Shown once after creating a link: whether it reached the chat, and the address to copy. */
export function LinkCreatedNotice({ created, onClose }: LinkCreatedNoticeProps) {
  const { t } = useLocale();
  const [copied, setCopied] = useState(false);

  const close = () => {
    setCopied(false);
    onClose();
  };

  const copy = async () => {
    if (!created) return;
    try {
      await navigator.clipboard.writeText(created.url);
      setCopied(true);
    } catch {
      // Clipboard blocked: the address is selectable in the field below.
      setCopied(false);
    }
  };

  return (
    <Dialog open={created !== null} onClose={close} title={t("links.created.title")}>
      {created && (
        <div className="space-y-4">
          <p className="text-lg font-semibold">{formatRupiah(created.link.amount)}</p>
          <p className="text-sm">
            {created.sent_to_chat
              ? t("links.created.sent")
              : created.not_sent_reason
                ? t(`links.created.notSent.${created.not_sent_reason}`)
                : ""}
          </p>
          <div>
            <input
              readOnly
              value={created.url}
              aria-label={t("links.created.copy")}
              onFocus={(event) => event.target.select()}
              className="w-full rounded-md border border-border bg-muted px-3 py-2 text-xs"
            />
            <p className="mt-1 text-xs text-muted-foreground">{t("links.created.once")}</p>
          </div>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => void copy()}
              className="rounded-md border border-border px-4 py-2 text-sm font-medium hover:bg-accent"
            >
              {copied ? t("links.created.copied") : t("links.created.copy")}
            </button>
            <button
              type="button"
              onClick={close}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              {t("links.created.done")}
            </button>
          </div>
        </div>
      )}
    </Dialog>
  );
}
