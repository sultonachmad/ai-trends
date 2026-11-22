"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { channelAttentionKey, channelKindKey } from "@/lib/booking-format";
import {
  fetchChannelAttention,
  type ChannelAttentionEntry,
} from "@/lib/bookings-api";
import { formatListTime } from "@/lib/inbox-format";
import { useLocale } from "@/lib/locale-store";

/** Channel bookings flagged for a person, with the reason and a way to the connection. */
export function ChannelAttentionCard() {
  const { t, locale } = useLocale();
  const [entries, setEntries] = useState<ChannelAttentionEntry[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchChannelAttention()
      .then((found) => {
        if (!cancelled) setEntries(found);
      })
      .catch(() => {
        if (!cancelled) setEntries([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (entries === null || entries.length === 0) return null;
  return (
    <section
      aria-labelledby="channel-attention-heading"
      className="rounded-xl border border-destructive/40 bg-card text-card-foreground shadow-sm"
    >
      <h2 id="channel-attention-heading" className="p-4 pb-2 text-lg font-semibold">
        {t("bookings.channel.title")}
      </h2>
      <ul className="divide-y divide-border text-sm">
        {entries.map((entry) => (
          <li key={entry.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
            <div className="min-w-0">
              <p className="font-medium">
                {t(channelKindKey(entry.kind))} · {entry.external_booking_id}
              </p>
              <p className="text-xs text-muted-foreground">
                {entry.reason
                  ? t(channelAttentionKey(entry.reason))
                  : t("bookings.channel.empty")}{" "}
                · {formatListTime(entry.received_at, locale, new Date())}
              </p>
            </div>
            <Link
              href={`/channels/${entry.connection_id}`}
              className="rounded-md border border-border px-3 py-1 text-sm hover:bg-accent"
            >
              {t("bookings.channel.viewConnection")}
              <span className="sr-only">: {entry.external_booking_id}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
