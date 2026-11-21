"use client";

import { useState } from "react";

import { Dialog } from "@/components/Dialog";
import { inputClass } from "@/components/rooms/RoomTypeDialog";
import { syncConnection, type ConnectionDetail } from "@/lib/channels-api";
import { formatListTime } from "@/lib/inbox-format";
import { useLocale } from "@/lib/locale-store";

const errorText = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));

interface PushStatusProps {
  connection: ConnectionDetail;
  onSynced: (connection: ConnectionDetail) => void;
}

/** Sender status of one connection, and the "sync now" action. */
export function PushStatus({ connection, onSynced }: PushStatusProps) {
  const { t, locale } = useLocale();
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dialog, setDialog] = useState(false);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const health = connection.push_health;
  const when = (iso: string | null) => formatListTime(iso, locale, new Date());

  const sync = async (range?: { from: string; to: string }) => {
    setSyncing(true);
    setError(null);
    try {
      onSynced(await syncConnection(connection.id, range));
      setDialog(false);
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="space-y-2 p-4 text-sm">
      <p className={health.at_risk ? "font-medium text-destructive" : "text-muted-foreground"}>
        {health.at_risk ? t("channels.push.atRisk") : null}
        {health.last_success_at
          ? t("channels.push.lastSuccess", { when: when(health.last_success_at) })
          : t("channels.push.never")}
      </p>
      {health.pending_updates > 0 && (
        <p className="text-muted-foreground">
          {t("channels.push.pending", { count: health.pending_updates })}
          {health.next_push_at ? ` · ${t("channels.push.nextAttempt", { when: when(health.next_push_at) })}` : ""}
        </p>
      )}
      {health.failing_since && (
        <p className="text-destructive">
          {t("channels.push.failing", { when: when(health.failing_since) })}
        </p>
      )}
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
      <button
        type="button"
        disabled={syncing}
        onClick={() => setDialog(true)}
        className="rounded-md border border-border px-4 py-2 text-sm hover:bg-accent disabled:opacity-50"
      >
        {t("channels.push.syncNow")}
      </button>

      {dialog && (
        <Dialog open={dialog} onClose={() => (syncing ? null : setDialog(false))} title={t("channels.push.syncTitle")}>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">{t("channels.push.syncHint")}</p>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="sync-from" className="mb-1 block text-sm font-medium">
                  {t("channels.push.syncRange")}
                </label>
                <input
                  id="sync-from"
                  type="date"
                  value={from}
                  onChange={(event) => setFrom(event.target.value)}
                  className={inputClass}
                />
              </div>
              <div>
                <label htmlFor="sync-to" className="mb-1 block text-sm font-medium">
                  –
                </label>
                <input
                  id="sync-to"
                  type="date"
                  value={to}
                  min={from || undefined}
                  onChange={(event) => setTo(event.target.value)}
                  className={inputClass}
                />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                disabled={syncing}
                onClick={() => setDialog(false)}
                className="rounded-md bg-secondary px-4 py-2 text-sm text-secondary-foreground disabled:opacity-50"
              >
                {t("rooms.form.cancel")}
              </button>
              <button
                type="button"
                disabled={syncing || !from || !to}
                onClick={() => void sync({ from, to })}
                className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {from && to ? t("channels.push.syncNow") : t("channels.push.syncAll")}
              </button>
              {(!from || !to) && (
                <button
                  type="button"
                  disabled={syncing}
                  onClick={() => void sync()}
                  className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  {t("channels.push.syncAll")}
                </button>
              )}
            </div>
          </div>
        </Dialog>
      )}
    </div>
  );
}
