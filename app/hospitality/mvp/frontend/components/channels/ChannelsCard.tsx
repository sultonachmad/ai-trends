"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { fetchConnections } from "@/lib/channels-api";
import { useLocale } from "@/lib/locale-store";

/** Dashboard card: how many channels are live, and the way to the Channels page. */
export function ChannelsCard({ className }: { className: string }) {
  const { t } = useLocale();
  const [counts, setCounts] = useState<{ live: number; other: number } | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchConnections()
      .then((connections) => {
        if (cancelled) return;
        const inUse = connections.filter((connection) => connection.status !== "disconnected");
        const live = inUse.filter((connection) => connection.status === "live").length;
        setCounts({ live, other: inUse.length - live });
      })
      .catch(() => {
        if (!cancelled) setCounts({ live: 0, other: 0 }); // the link below still works
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const connected = counts !== null && counts.live + counts.other > 0;
  return (
    <section className={className} aria-labelledby="channels-heading">
      <h2 id="channels-heading" className="text-sm font-medium text-muted-foreground">
        {t("dashboard.channels")}
      </h2>
      <p className="mt-1 text-sm">
        {connected
          ? t("dashboard.channelsLive", { live: counts.live, other: counts.other })
          : t("dashboard.channelsNone")}
      </p>
      <Link
        href="/channels"
        className="mt-2 inline-block text-sm font-medium text-primary hover:underline"
      >
        {t("dashboard.openChannels")}
      </Link>
    </section>
  );
}
