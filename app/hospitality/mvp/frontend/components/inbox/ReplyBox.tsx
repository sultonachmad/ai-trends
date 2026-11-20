"use client";

import { useState, type FormEvent, type KeyboardEvent } from "react";

import type { ReplyBlockedReason } from "@/lib/inbox-api";
import { useLocale } from "@/lib/locale-store";

const MAX_LENGTH = 4096; // WhatsApp text limit; the backend enforces the same

interface ReplyBoxProps {
  blockedReason: ReplyBlockedReason | null;
  onSend: (body: string) => Promise<void>;
}

/** Reply input. Enter sends, Shift+Enter adds a line. Explains why when replying is blocked. */
export function ReplyBox({ blockedReason, onSend }: ReplyBoxProps) {
  const { t } = useLocale();
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (blockedReason) {
    return (
      <p className="border-t border-border bg-muted p-4 text-sm text-muted-foreground">
        {blockedReason === "resolved" ? t("inbox.blockedResolved") : t("inbox.blockedWindow")}
      </p>
    );
  }

  const submit = async () => {
    const body = text.trim();
    if (!body || sending) return;
    setSending(true);
    setError(null);
    try {
      await onSend(body);
      setText("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setSending(false);
    }
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    void submit();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void submit();
    }
  };

  return (
    <form onSubmit={onSubmit} className="space-y-2 border-t border-border p-3">
      <div className="flex items-end gap-2">
        <label htmlFor="reply-body" className="sr-only">
          {t("inbox.replyLabel")}
        </label>
        <textarea
          id="reply-body"
          rows={2}
          maxLength={MAX_LENGTH}
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder={t("inbox.replyPlaceholder")}
          className="min-h-[44px] flex-1 resize-y rounded-md border border-border bg-card px-3 py-2 text-sm text-card-foreground focus:outline-none focus:ring-2 focus:ring-primary"
        />
        <button
          type="submit"
          disabled={sending || text.trim().length === 0}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {sending ? t("inbox.sending") : t("inbox.send")}
        </button>
      </div>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {t("inbox.actionFailed", { reason: error })}
        </p>
      )}
    </form>
  );
}
