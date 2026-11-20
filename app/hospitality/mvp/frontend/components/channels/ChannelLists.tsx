"use client";

import Link from "next/link";

import { statusBadgeClass, statusKey } from "@/lib/channel-format";
import type { CatalogChannel, Connection } from "@/lib/channels-api";
import { useLocale } from "@/lib/locale-store";

const badge = "inline-block rounded-full px-2 py-0.5 text-xs font-medium";

/** The property's connections, each opening its own page. */
export function ConnectionList({ connections }: { connections: Connection[] }) {
  const { t } = useLocale();
  return (
    <ul className="divide-y divide-border">
      {connections.map((connection) => (
        <li key={connection.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="min-w-0">
            <p className="flex flex-wrap items-center gap-2 font-medium">
              <span className="truncate">{connection.channel_name}</span>
              <span className={`${badge} ${statusBadgeClass(connection.status)}`}>
                {t(statusKey(connection.status))}
              </span>
            </p>
            <p className="text-sm text-muted-foreground">
              {t("channels.propertyId", { id: connection.external_property_id })} ·{" "}
              {t("channels.matched", { count: connection.mapped_pairs })}
            </p>
          </div>
          <Link
            href={`/channels/${connection.id}`}
            className="rounded-md border border-border px-3 py-1 text-sm hover:bg-accent"
          >
            {t("channels.open")}
            <span className="sr-only">: {connection.channel_name}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

interface ChannelCatalogProps {
  channels: CatalogChannel[];
  /** False when the plan allows no further connection. */
  canConnect: boolean;
  onConnect: (channel: CatalogChannel) => void;
}

/** What can be connected now and what is still to come, with what each will support. */
export function ChannelCatalog({ channels, canConnect, onConnect }: ChannelCatalogProps) {
  const { t } = useLocale();
  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {channels.map((channel) => (
        <li
          key={channel.code}
          className={`rounded-lg border border-border p-4 ${
            channel.state === "connectable" ? "bg-card" : "bg-muted/40"
          }`}
        >
          <div className="flex items-start justify-between gap-2">
            <p className="font-medium">{channel.name}</p>
            {channel.state === "coming_soon" && (
              <span className={`${badge} bg-muted text-muted-foreground ring-1 ring-border`}>
                {t("channels.comingSoon")}
              </span>
            )}
            {channel.state === "connectable" && channel.connected && (
              <span className={`${badge} bg-accent text-accent-foreground`}>
                {t("channels.connected")}
              </span>
            )}
          </div>
          {channel.features.length > 0 && (
            <p className="mt-1 text-xs text-muted-foreground">
              {channel.features.map((feature) => t(`channels.feature.${feature}`)).join(" · ")}
            </p>
          )}
          {channel.state === "connectable" && !channel.connected && (
            <button
              type="button"
              disabled={!canConnect}
              onClick={() => onConnect(channel)}
              className="mt-3 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {t("channels.connect")}
              <span className="sr-only">: {channel.name}</span>
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}
