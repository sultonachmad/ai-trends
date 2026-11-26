"use client";

import { useState } from "react";

import { inputClass } from "@/components/rooms/RoomTypeDialog";
import { fetchRegister } from "@/lib/apoa-api";
import { apoaErrorKey, registerRange } from "@/lib/apoa-format";
import { useLocale } from "@/lib/locale-store";

const secondary =
  "min-h-11 rounded-md border border-border px-4 py-2 text-sm hover:bg-accent disabled:opacity-50";

/** Download the masked register of foreign guests for an immigration officer. */
export function ApoaRegister({ today }: { today: string }) {
  const { t } = useLocale();
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const download = async () => {
    const range = registerRange(today, from, to);
    if (!range.ok) {
      setError(t(range.key));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const url = URL.createObjectURL(await fetchRegister(range.value.from, range.value.to));
      const link = document.createElement("a");
      link.href = url;
      link.download = `apoa-register-${range.value.from}-${range.value.to}.csv`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (cause) {
      const key = apoaErrorKey(cause);
      setError(key ? t(key) : cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section aria-labelledby="apoa-register" className="space-y-2 rounded-lg border border-border bg-card p-3 text-sm">
      <h2 id="apoa-register" className="font-semibold">
        {t("apoa.register.title")}
      </h2>
      <p className="text-muted-foreground">{t("apoa.register.body")}</p>
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor="apoa-from" className="mb-1 block">
            {t("apoa.register.from")}
          </label>
          <input id="apoa-from" type="date" value={from} max={today} onChange={(e) => setFrom(e.target.value)} className={inputClass} />
        </div>
        <div>
          <label htmlFor="apoa-to" className="mb-1 block">
            {t("apoa.register.to")}
          </label>
          <input id="apoa-to" type="date" value={to} max={today} onChange={(e) => setTo(e.target.value)} className={inputClass} />
        </div>
        <button type="button" disabled={busy} onClick={() => void download()} className={secondary}>
          {t("apoa.register.download")}
        </button>
      </div>
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
    </section>
  );
}
