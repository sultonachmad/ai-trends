"use client";

import { useState, type FormEvent } from "react";

import { simulateInbound } from "@/lib/inbox-api";
import { useLocale } from "@/lib/locale-store";

const DEFAULT_PHONE = "+6281234567890";
const inputClass =
  "w-full rounded-md border border-border bg-card px-3 py-2 text-sm text-card-foreground focus:outline-none focus:ring-2 focus:ring-primary";

interface SimulatorPanelProps {
  onSent: (conversationId: string) => void;
}

/** Development-only: send a WhatsApp message in as a guest. Shown when the backend enables it. */
export function SimulatorPanel({ onSent }: SimulatorPanelProps) {
  const { t } = useLocale();
  const [phone, setPhone] = useState(DEFAULT_PHONE);
  const [name, setName] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy || body.trim().length === 0) return;
    setBusy(true);
    setError(null);
    try {
      const guestName = name.trim();
      const result = await simulateInbound({
        from_phone: phone.trim(),
        body: body.trim(),
        ...(guestName ? { guest_name: guestName } : {}),
      });
      setBody("");
      onSent(result.conversation_id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  };

  return (
    <details className="rounded-xl border border-dashed border-border bg-card p-4 text-card-foreground">
      <summary className="cursor-pointer text-sm font-medium">{t("simulator.title")}</summary>
      <p className="mt-2 text-xs text-muted-foreground">{t("simulator.note")}</p>
      <form onSubmit={onSubmit} className="mt-3 grid gap-3 md:grid-cols-2">
        <div>
          <label htmlFor="sim-phone" className="mb-1 block text-xs font-medium">
            {t("simulator.phone")}
          </label>
          <input
            id="sim-phone"
            required
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            className={inputClass}
          />
        </div>
        <div>
          <label htmlFor="sim-name" className="mb-1 block text-xs font-medium">
            {t("simulator.name")}
          </label>
          <input
            id="sim-name"
            value={name}
            maxLength={120}
            onChange={(event) => setName(event.target.value)}
            className={inputClass}
          />
        </div>
        <div className="md:col-span-2">
          <label htmlFor="sim-body" className="mb-1 block text-xs font-medium">
            {t("simulator.text")}
          </label>
          <textarea
            id="sim-body"
            required
            rows={2}
            maxLength={4096}
            value={body}
            onChange={(event) => setBody(event.target.value)}
            className={inputClass}
          />
        </div>
        <div className="md:col-span-2">
          <button
            type="submit"
            disabled={busy || body.trim().length === 0}
            className="rounded-md bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t("simulator.send")}
          </button>
          {error && (
            <p role="alert" className="mt-2 text-sm text-destructive">
              {t("inbox.actionFailed", { reason: error })}
            </p>
          )}
        </div>
      </form>
    </details>
  );
}
