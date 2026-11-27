"use client";

import Link from "next/link";

import { shortDate } from "@/lib/booking-format";
import { useLocale } from "@/lib/locale-store";
import type { MaintNotice } from "@/lib/maintenance-api";

/** Urgent repairs and rooms off sale, until they are fixed. */
export function RepairNotices({ notices, canOpen }: { notices: MaintNotice[]; canOpen: boolean }) {
  const { t, locale } = useLocale();
  if (notices.length === 0) return null;
  return (
    <section
      aria-labelledby="desk-repairs"
      className="flex flex-wrap items-start justify-between gap-2 rounded-lg bg-accent px-3 py-2 text-sm text-accent-foreground"
    >
      <div>
        <h2 id="desk-repairs" className="font-semibold">{t("frontdesk.repairs.title")}</h2>
        <ul>
          {notices.map((notice) => {
            const where = notice.room_name ?? notice.place ?? notice.number;
            return (
              <li key={notice.id}>
                {notice.off_sale_until
                  ? t("frontdesk.repairs.offSale", { where, date: shortDate(notice.off_sale_until, locale) })
                  : t("frontdesk.repairs.urgent", { where, category: t(`repair.category.${notice.category}`) })}
              </li>
            );
          })}
        </ul>
      </div>
      {canOpen && (
        <Link href="/maintenance" className="min-h-11 rounded-md border border-current px-3 py-2 font-medium">
          {t("frontdesk.repairs.open")}
        </Link>
      )}
    </section>
  );
}
