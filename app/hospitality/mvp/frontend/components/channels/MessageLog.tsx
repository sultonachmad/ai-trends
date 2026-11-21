"use client";

import { messageBadgeClass, messageStatusKey } from "@/lib/channel-format";
import type { MessageLogEntry } from "@/lib/channels-api";
import { useLocale } from "@/lib/locale-store";

const badge = "inline-block rounded-full px-2 py-0.5 text-xs font-medium";

/** The newest pushes to a channel: what was sent, whether it worked, what went wrong. */
export function MessageLog({ messages }: { messages: MessageLogEntry[] }) {
  const { t } = useLocale();
  if (messages.length === 0) {
    return <p className="p-4 text-sm text-muted-foreground">{t("channels.push.logEmpty")}</p>;
  }
  return (
    <ol className="divide-y divide-border text-sm">
      {messages.map((entry, index) => (
        <li key={`${entry.created_at}-${index}`} className="flex flex-wrap items-center gap-2 px-4 py-2">
          <span className={`rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground ring-1 ring-border`}>
            {t(`channels.push.kind.${entry.message_type}`)}
          </span>
          <span className={`${badge} ${messageBadgeClass(entry.status)}`}>
            {t(messageStatusKey(entry.status))}
          </span>
          {entry.attempts > 1 && (
            <span className="text-xs text-muted-foreground">
              {t("channels.push.attempts", { count: entry.attempts })}
            </span>
          )}
          {entry.date_from && (
            <span className="text-xs text-muted-foreground">
              {entry.date_from}
              {entry.date_to && entry.date_to !== entry.date_from ? ` – ${entry.date_to}` : ""}
            </span>
          )}
          {entry.error && <span className="text-xs text-destructive">{entry.error}</span>}
        </li>
      ))}
    </ol>
  );
}
