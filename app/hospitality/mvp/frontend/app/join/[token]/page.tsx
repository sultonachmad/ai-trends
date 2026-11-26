"use client";

/**
 * Public join page — a new staff member opens `/join/<token>` from the link the owner
 * sent. It shows which property and role the link is for. Joining needs the person to
 * be signed in with the invited email; otherwise they sign in (or sign up) and come
 * back here.
 */

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { LanguageSwitch } from "@/components/LanguageSwitch";
import { ApiError } from "@/lib/api-client";
import { homeFor, staffErrorKey } from "@/lib/housekeeping-format";
import { useLocale } from "@/lib/locale-store";
import { acceptJoin, previewJoin, type JoinPreview } from "@/lib/staff-api";

const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
const UNAUTHORISED = 401;
const card = "w-full max-w-md space-y-4 rounded-xl border border-border bg-card p-6 text-card-foreground shadow-sm";

export default function JoinPage() {
  const { token } = useParams<{ token: string }>();
  const { t } = useLocale();
  const [preview, setPreview] = useState<JoinPreview | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [signInFirst, setSignInFirst] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    previewJoin(token)
      .then((found) => {
        if (!cancelled) setPreview(found);
      })
      .catch((cause) => {
        if (cancelled) return;
        const key = staffErrorKey(cause);
        setProblem(key ? t(key) : t("staff.error.invite_not_found"));
      });
    return () => {
      cancelled = true;
    };
  }, [token, t]);

  const here = `${BASE_PATH}/join/${encodeURIComponent(token)}`;
  const signInHref = `${BASE_PATH}/login?callbackUrl=${encodeURIComponent(here)}`;
  const join = async () => {
    setBusy(true);
    setProblem(null);
    try {
      const joined = await acceptJoin(token);
      window.location.href = `${BASE_PATH}${homeFor(joined.role)}`; // full load: new menus
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === UNAUTHORISED) setSignInFirst(true);
      else {
        const key = staffErrorKey(cause);
        setProblem(key ? t(key) : cause instanceof Error ? cause.message : String(cause));
      }
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-main px-4 py-8">
      <div className="flex w-full max-w-md justify-end">
        <LanguageSwitch />
      </div>
      <section className={card} aria-labelledby="join-title">
        <h1 id="join-title" className="text-xl font-bold">{t("join.title")}</h1>
        {!preview && !problem && <p className="text-sm text-muted-foreground">{t("join.loading")}</p>}
        {preview && (
          <>
            <p>
              {t("join.for", {
                workspace: preview.workspace,
                name: preview.name ?? "",
                role: t(`staff.role.${preview.role}`),
              })}
            </p>
            {preview.state === "open" ? (
              <>
                <p className="text-sm text-muted-foreground">{t("join.email", { email: preview.email_hint })}</p>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void join()}
                  className="min-h-12 w-full rounded-md bg-primary px-4 text-base font-medium text-primary-foreground disabled:opacity-50"
                >
                  {busy ? t("join.joining") : t("join.button")}
                </button>
              </>
            ) : (
              <p role="alert" className="text-sm text-destructive">{t(`join.state.${preview.state}`)}</p>
            )}
          </>
        )}
        {signInFirst && (
          <div role="status" className="space-y-2 text-sm">
            <p>{t("join.signInFirst")}</p>
            <a href={signInHref} className="inline-flex min-h-11 items-center rounded-md border border-border px-4 font-medium hover:bg-accent">
              {t("join.signIn")}
            </a>
          </div>
        )}
        {problem && <p role="alert" className="text-sm text-destructive">{problem}</p>}
      </section>
    </div>
  );
}
