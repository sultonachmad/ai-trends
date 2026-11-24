"use client";

import { staySecondaryButton, staySectionTitle } from "@/components/booking-page/stay-classes";
import type { PublicPage } from "@/lib/booking-page-api";
import { whatsappUrl } from "@/lib/booking-page-format";
import { useLocale } from "@/lib/locale-store";

const ICONS = {
  clock: "M12 7v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z",
  wallet: "M3 7h16a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7zm0 0 13-3v3M16 13h2",
  timer: "M9 3h6M12 3v3M19 13a7 7 0 1 1-14 0 7 7 0 0 1 14 0zM12 13V9",
  moon: "M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z",
};

/** The property's real terms as amenity-style rows, with a WhatsApp contact card. */
export function ThingsToKnow({ page }: { page: PublicPage }) {
  const { t } = useLocale();
  const contact = whatsappUrl(page.whatsapp_phone);
  const rows = [
    {
      icon: ICONS.clock,
      text: t("book.times", {
        in: page.check_in_time.slice(0, 5),
        out: page.check_out_time.slice(0, 5),
      }),
    },
    { icon: ICONS.wallet, text: t("book.knowDeposit", { percent: page.deposit_percent }) },
    { icon: ICONS.timer, text: t("book.holdNote", { minutes: page.hold_minutes }) },
    { icon: ICONS.moon, text: t("book.knowMaxNights", { nights: page.max_nights }) },
  ];
  return (
    <section className="border-t border-stay-hairline py-8">
      <h2 className={staySectionTitle}>{t("book.thingsToKnow")}</h2>
      <ul className="mt-4">
        {rows.map((row) => (
          <li key={row.icon} className="flex items-start gap-4 py-3 text-stay-body">
            <svg
              viewBox="0 0 24 24"
              aria-hidden="true"
              className="mt-0.5 h-6 w-6 shrink-0 fill-none stroke-stay-ink"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d={row.icon} />
            </svg>
            <span>{row.text}</span>
          </li>
        ))}
      </ul>
      {contact && (
        <div className="mt-6 flex flex-wrap items-center justify-between gap-4 rounded-stay-md border border-stay-hairline p-6">
          <div>
            <p className="text-type-title">{t("book.contactTitle")}</p>
            <p className="mt-1 text-type-body-sm text-stay-muted">{page.property_name}</p>
          </div>
          <a
            href={contact}
            target="_blank"
            rel="noopener noreferrer"
            className={`inline-flex items-center ${staySecondaryButton}`}
          >
            {t("book.contactAction")}
          </a>
        </div>
      )}
    </section>
  );
}
