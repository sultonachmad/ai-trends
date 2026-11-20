"use client";

import { formatListTime } from "@/lib/inbox-format";
import { useLocale } from "@/lib/locale-store";
import { formatRupiah } from "@/lib/money";
import { stateBadgeClass, stateLabelKey, timeLeft, timeLeftKey } from "@/lib/payment-link-format";
import type { PaymentLink } from "@/lib/payment-links-api";

interface PaymentLinkTableProps {
  links: PaymentLink[];
  onCancel: (link: PaymentLink) => void;
  timeZone?: string;
}

/** Payment links as a table: amount, purpose, guest, status, created; cancel when pending. */
export function PaymentLinkTable({ links, onCancel, timeZone }: PaymentLinkTableProps) {
  const { t, locale } = useLocale();
  const now = new Date();
  const when = (iso: string | null) => formatListTime(iso, locale, now, timeZone);

  const detail = (link: PaymentLink): string => {
    if (link.state === "paid") {
      return t("links.paidVia", { when: when(link.paid_at), method: link.paid_via ?? "" });
    }
    if (link.state !== "pending") return "";
    const left = timeLeft(link.expires_at, now);
    return left ? t(timeLeftKey(left), { value: left.value }) : "";
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead className="border-b border-border text-xs text-muted-foreground">
          <tr>
            <th scope="col" className="px-4 py-2 font-medium">{t("links.col.amount")}</th>
            <th scope="col" className="px-4 py-2 font-medium">{t("links.col.description")}</th>
            <th scope="col" className="px-4 py-2 font-medium">{t("links.col.guest")}</th>
            <th scope="col" className="px-4 py-2 font-medium">{t("links.col.state")}</th>
            <th scope="col" className="px-4 py-2 font-medium">{t("links.col.created")}</th>
            <th scope="col" className="px-4 py-2">
              <span className="sr-only">{t("links.cancel")}</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {links.map((link) => (
            <tr key={link.id}>
              <td className="px-4 py-3 align-top">
                <span className="font-semibold">{formatRupiah(link.amount)}</span>
                {link.total_amount && (
                  <span className="block text-xs text-muted-foreground">
                    {t("links.dpOf", { total: formatRupiah(link.total_amount) })}
                  </span>
                )}
              </td>
              <td className="px-4 py-3 align-top">{link.description}</td>
              <td className="px-4 py-3 align-top">
                {link.guest?.name ?? "—"}
                {link.sent_to_chat && (
                  <span className="block text-xs text-muted-foreground">
                    {t("links.sentToChat")}
                  </span>
                )}
              </td>
              <td className="px-4 py-3 align-top">
                <span
                  className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${stateBadgeClass(link.state)}`}
                >
                  {t(stateLabelKey(link.state))}
                </span>
                <span className="block text-xs text-muted-foreground">{detail(link)}</span>
                {link.needs_refund_review && (
                  <span role="status" className="mt-1 block text-xs font-semibold text-destructive">
                    {t("links.refundReview")}
                  </span>
                )}
              </td>
              <td className="px-4 py-3 align-top text-muted-foreground">
                {when(link.created_at)}
              </td>
              <td className="px-4 py-3 text-right align-top">
                {link.state === "pending" && (
                  <button
                    type="button"
                    onClick={() => onCancel(link)}
                    className="rounded-md border border-border px-3 py-1 text-xs font-medium hover:bg-accent"
                  >
                    {t("links.cancel")}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
