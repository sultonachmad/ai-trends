"use client";

import { useEffect, useRef } from "react";

import type { Message } from "@/lib/inbox-api";
import { dayLabel, formatClock, startsNewDay } from "@/lib/inbox-format";
import { useLocale } from "@/lib/locale-store";

const STATUS_LABEL: Record<string, string> = {
  queued: "inbox.sending",
  failed: "inbox.failed",
};

interface MessageThreadProps {
  messages: Message[];
  timeZone?: string;
}

/** Messages oldest to newest with day separators; keeps the newest in view. */
export function MessageThread({ messages, timeZone }: MessageThreadProps) {
  const { t, locale } = useLocale();
  const endRef = useRef<HTMLDivElement>(null);
  const lastId = messages.length > 0 ? messages[messages.length - 1].id : null;

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [lastId]);

  const labelFor = (iso: string): string => {
    const label = dayLabel(iso, locale, new Date(), timeZone);
    if (label.kind === "today") return t("inbox.today");
    if (label.kind === "yesterday") return t("inbox.yesterday");
    return label.text;
  };

  return (
    <ol className="flex flex-col gap-2 p-4" aria-live="polite">
      {messages.map((message, index) => {
        const outbound = message.direction === "outbound";
        const previous = index > 0 ? messages[index - 1].created_at : null;
        return (
          <li key={message.id} className="flex flex-col gap-2">
            {startsNewDay(previous, message.created_at, timeZone) && (
              <span className="self-center rounded-full bg-muted px-3 py-0.5 text-xs text-muted-foreground">
                {labelFor(message.created_at)}
              </span>
            )}
            <div
              className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                outbound
                  ? "self-end bg-primary text-primary-foreground"
                  : "self-start border border-border bg-card text-card-foreground"
              }`}
            >
              <p className="whitespace-pre-wrap break-words">{message.body}</p>
              <p className={`mt-1 text-xs ${outbound ? "opacity-80" : "text-muted-foreground"}`}>
                {formatClock(message.created_at, locale, timeZone)}
                {outbound && message.sender_name ? ` · ${message.sender_name}` : ""}
                {outbound ? ` · ${t(STATUS_LABEL[message.status] ?? "inbox.sent")}` : ""}
              </p>
              {message.status === "failed" && message.error && (
                <p role="alert" className="mt-1 text-xs font-medium">
                  {message.error}
                </p>
              )}
            </div>
          </li>
        );
      })}
      <div ref={endRef} />
    </ol>
  );
}
