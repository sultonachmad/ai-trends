"use client";

/**
 * Channels — what is connected and what can be.
 * Reachable at `/channels`; one connection lives at `/channels/<id>`.
 */

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ChannelCatalog, ConnectionList } from "@/components/channels/ChannelLists";
import { ChannelQuotaNotice } from "@/components/channels/ChannelQuotaNotice";
import { ConnectDialog } from "@/components/channels/ConnectDialog";
import { LanguageSwitch } from "@/components/LanguageSwitch";
import {
  fetchChannels,
  fetchConnections,
  type CatalogChannel,
  type ChannelsOverview,
  type Connection,
} from "@/lib/channels-api";
import { useLocale } from "@/lib/locale-store";
import { fetchOnboardingStatus } from "@/lib/workspace-api";

const ONBOARDING_PATH = "/onboarding";
const cardClass = "rounded-xl border border-border bg-card text-card-foreground shadow-sm";
const errorText = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));

export default function ChannelsPage() {
  const router = useRouter();
  const { t } = useLocale();
  const [overview, setOverview] = useState<ChannelsOverview | null>(null);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [connecting, setConnecting] = useState<CatalogChannel | null>(null);

  const reload = useCallback(async () => {
    const [channels, mine] = await Promise.all([fetchChannels(), fetchConnections()]);
    setOverview(channels);
    setConnections(mine);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const status = await fetchOnboardingStatus();
        if (cancelled) return;
        if (!status.has_workspace) {
          router.replace(ONBOARDING_PATH);
          return;
        }
        await reload();
      } catch (cause) {
        if (!cancelled) setLoadError(errorText(cause));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router, reload]);

  if (loadError) {
    return (
      <p role="alert" className="p-8 text-sm text-destructive">
        {t("common.loadFailed", { reason: loadError })}
      </p>
    );
  }
  if (!overview) {
    return <p className="p-8 text-sm text-muted-foreground">{t("common.loading")}</p>;
  }

  const inUse = connections.filter((connection) => connection.status !== "disconnected");
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">{t("channels.title")}</h1>
        <LanguageSwitch />
      </div>
      <div className="space-y-1">
        <p className="max-w-2xl text-sm text-muted-foreground">{t("channels.intro")}</p>
        <ChannelQuotaNotice usage={overview.usage} />
      </div>

      <section className={cardClass} aria-labelledby="connections-heading">
        <h2 id="connections-heading" className="p-4 text-lg font-semibold">
          {t("channels.mine")}
        </h2>
        <div className="border-t border-border">
          {connections.length === 0 ? (
            <p className="p-4 text-sm text-muted-foreground">{t("channels.none")}</p>
          ) : (
            <ConnectionList connections={[...inUse, ...connections.filter((c) => !inUse.includes(c))]} />
          )}
        </div>
      </section>

      <section aria-labelledby="catalog-heading" className="space-y-3">
        <h2 id="catalog-heading" className="text-lg font-semibold">
          {t("channels.catalog")}
        </h2>
        <ChannelCatalog
          channels={overview.channels}
          canConnect={!overview.usage.limit_reached}
          onConnect={setConnecting}
        />
      </section>

      <ConnectDialog
        channel={connecting}
        onClose={() => setConnecting(null)}
        onStarted={(connection) => router.push(`/channels/${connection.id}`)}
      />
    </div>
  );
}
