"use client";

import type { Conversation } from "@/lib/inbox-api";
import { formatListTime } from "@/lib/inbox-format";
import { useLocale } from "@/lib/locale-store";

interface ConversationListProps {
  conversations: Conversation[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  emptyText: string;
  timeZone?: string;
}

/** The inbox list: guest, last message preview, time and unread badge. */
export function ConversationList({
  conversations,
  selectedId,
  onSelect,
  emptyText,
  timeZone,
}: ConversationListProps) {
  const { t, locale } = useLocale();

  if (conversations.length === 0) {
    return <p className="p-4 text-sm text-muted-foreground">{emptyText}</p>;
  }

  return (
    <ul className="divide-y divide-border">
      {conversations.map((conversation) => {
        const selected = conversation.id === selectedId;
        const unread = conversation.unread_count > 0;
        const last = conversation.last_message;
        return (
          <li key={conversation.id}>
            <button
              type="button"
              onClick={() => onSelect(conversation.id)}
              aria-current={selected ? "true" : undefined}
              className={`flex w-full flex-col gap-1 px-4 py-3 text-left hover:bg-accent ${
                selected ? "bg-accent" : ""
              }`}
            >
              <span className="flex items-baseline justify-between gap-2">
                <span className={`truncate text-sm ${unread ? "font-bold" : "font-medium"}`}>
                  {conversation.guest.name}
                </span>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {formatListTime(conversation.last_message_at, locale, new Date(), timeZone)}
                </span>
              </span>
              <span className="flex items-center justify-between gap-2">
                <span className="truncate text-sm text-muted-foreground">
                  {last?.direction === "outbound" ? t("inbox.you") : ""}
                  {last?.preview ?? ""}
                </span>
                {unread && (
                  <span
                    className="shrink-0 rounded-full bg-primary px-2 py-0.5 text-xs font-semibold text-primary-foreground"
                    aria-label={t("inbox.unreadBadge", { count: conversation.unread_count })}
                  >
                    {conversation.unread_count}
                  </span>
                )}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
