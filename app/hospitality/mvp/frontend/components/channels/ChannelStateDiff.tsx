"use client";

import { useState } from "react";

import { fetchDrift, type DriftEntry } from "@/lib/channels-api";
import { driftKindKey } from "@/lib/channel-format";
import { formatRupiah } from "@/lib/money";
import { useLocale } from "@/lib/locale-store";

const errorText = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));

const describe = (side: Record<string, unknown> | null) => {
  if (side === null) return "–";
  const prices = side.prices as Record<string, number> | undefined;
  const first = prices ? Object.values(prices)[0] : undefined;
  return `${side.closed ? "closed" : "open"} · ${side.available} · ${first ? formatRupiah(first) : "–"}`;
};

/** Compare what the channel holds with our truth, on demand. */
export function ChannelStateDiff({ connectionId }: { connectionId: string }) {
  const { t } = useLocale();
  const [entries, setEntries] = useState<DriftEntry[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const check = async () => {
    setBusy(true);
    setError(null);
    try {
      setEntries((await fetchDrift(connectionId)).differences);
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-2 p-4 text-sm">
      <button
        type="button"
        disabled={busy}
        onClick={() => void check()}
        className="rounded-md border border-border px-4 py-2 text-sm hover:bg-accent disabled:opacity-50"
      >
        {t("channels.drift.check")}
      </button>
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
      {entries !== null && !error && (
        <>
          <p className={entries.length > 0 ? "font-medium text-destructive" : "text-muted-foreground"}>
            {entries.length === 0
              ? t("channels.drift.none")
              : t("channels.drift.some", { count: entries.length })}
          </p>
          {entries.length > 0 && (
            <ol className="max-h-64 space-y-1 overflow-y-auto rounded-lg border border-border p-3">
              {entries.map((entry) => (
                <li key={`${entry.room}-${entry.date}`}>
                  <span className="font-medium">
                    {entry.room} · {entry.date}
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    {t(driftKindKey(entry.kind))}
                  </span>
                  {entry.kind === "differs" && (
                    <span className="block text-xs">
                      {t("channels.drift.showTheirs", { text: describe(entry.channel) })} ·{" "}
                      {t("channels.drift.showOurs", { text: describe(entry.ours) })}
                    </span>
                  )}
                </li>
              ))}
            </ol>
          )}
        </>
      )}
    </div>
  );
}
