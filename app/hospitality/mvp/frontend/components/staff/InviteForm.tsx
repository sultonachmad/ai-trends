"use client";

import { useState } from "react";

import { joinLink, STAFF_ROLES, staffErrorKey, whatsappShare } from "@/lib/housekeeping-format";
import { useLocale } from "@/lib/locale-store";
import { createInvite, type StaffRole } from "@/lib/staff-api";

const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
const field = "min-h-11 w-full rounded-md border border-border bg-background px-3 py-2 text-base";

type Made = { name: string; email: string; link: string };

/** Name, email and role in; a join link out, to copy or send by WhatsApp. */
export function InviteForm({ onMade }: { onMade: () => void }) {
  const { t } = useLocale();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<StaffRole>("housekeeper");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [made, setMade] = useState<Made | null>(null);
  const [copied, setCopied] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setCopied(false);
    try {
      const created = await createInvite(name.trim(), email.trim(), role);
      setMade({
        name: name.trim(),
        email: created.invite.email,
        link: joinLink(window.location.origin, BASE_PATH, created.token),
      });
      setName("");
      setEmail("");
      onMade();
    } catch (cause) {
      const key = staffErrorKey(cause);
      setError(key ? t(key) : cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  };
  const copy = async (link: string) => {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
    } catch {
      setCopied(false); // the link stays on screen to copy by hand
    }
  };

  return (
    <section aria-labelledby="staff-invite" className="space-y-3 rounded-lg border border-border bg-card p-4">
      <h2 id="staff-invite" className="font-semibold">{t("staff.invite.title")}</h2>
      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-3">
        <label className="space-y-1 text-sm">
          <span>{t("staff.invite.name")}</span>
          <input required maxLength={80} value={name} onChange={(e) => setName(e.target.value)} className={field} />
        </label>
        <label className="space-y-1 text-sm">
          <span>{t("staff.invite.email")}</span>
          <input type="email" required maxLength={254} value={email} onChange={(e) => setEmail(e.target.value)} className={field} />
        </label>
        <label className="space-y-1 text-sm">
          <span>{t("staff.invite.role")}</span>
          <select value={role} onChange={(e) => setRole(e.target.value as StaffRole)} className={field}>
            {STAFF_ROLES.map((option) => (
              <option key={option} value={option}>{t(`staff.role.${option}`)}</option>
            ))}
          </select>
        </label>
        <div className="sm:col-span-3">
          <button type="submit" disabled={busy} className="min-h-11 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50">
            {t("staff.invite.create")}
          </button>
        </div>
      </form>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {made && (
        <div role="status" className="space-y-2 rounded-md bg-accent p-3 text-sm text-accent-foreground">
          <p>{t("staff.invite.ready", { name: made.name, email: made.email })}</p>
          <p className="break-all font-mono text-xs">{made.link}</p>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => void copy(made.link)} className="min-h-11 rounded-md border border-current px-3 py-1 font-medium">
              {copied ? t("staff.invite.copied") : t("staff.invite.copy")}
            </button>
            <a
              href={whatsappShare(t("staff.invite.message", { name: made.name, link: made.link }))}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex min-h-11 items-center rounded-md border border-current px-3 py-1 font-medium"
            >
              {t("staff.invite.whatsapp")}
            </a>
          </div>
        </div>
      )}
    </section>
  );
}
