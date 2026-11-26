"use client";

/** Foreign guests to check in to and out of APOA (Imigrasi), and what was recorded. */

import { useCallback, useEffect, useRef, useState } from "react";

import { ApoaCard, type ApoaAction } from "@/components/apoa/ApoaCard";
import { ApoaRegister } from "@/components/apoa/ApoaRegister";
import { ApoaStepDialog, type StepTarget } from "@/components/apoa/ApoaStepDialog";
import { GuestIdDialog } from "@/components/guest-ids/GuestIdDialog";
import { LanguageSwitch } from "@/components/LanguageSwitch";
import { ApiError } from "@/lib/api-client";
import { fetchApoa, type ApoaItem, type ApoaList, type ApoaStep } from "@/lib/apoa-api";
import { APOA_TABS, type ApoaTab } from "@/lib/apoa-format";
import { useLocale } from "@/lib/locale-store";
import { useCan } from "@/lib/rbac-store";

const FORBIDDEN = 403;
const errorText = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));

export default function ApoaPage() {
  const { t } = useLocale();
  const canEdit = useCan("apoa:edit");
  const canSeePhoto = useCan("guestid:edit");
  const canSeeIds = useCan("guestid:view");
  const [list, setList] = useState<ApoaList | null>(null);
  const [tab, setTab] = useState<ApoaTab>("to_report");
  const [target, setTarget] = useState<StepTarget>(null);
  const [guestsOf, setGuestsOf] = useState<string | null>(null);
  const [noAccess, setNoAccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  const load = useCallback(async () => {
    const id = ++requestId.current;
    try {
      const found = await fetchApoa();
      if (id !== requestId.current) return;
      setList(found);
      setError(null);
    } catch (cause) {
      if (id !== requestId.current) return;
      if (cause instanceof ApiError && cause.status === FORBIDDEN) setNoAccess(true);
      else setError(errorText(cause));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (noAccess) return <p role="alert" className="p-8 text-sm">{t("apoa.noAccess")}</p>;
  const items = list ? list[tab] : [];
  const onAction = (item: ApoaItem, action: ApoaAction, step: ApoaStep) =>
    setTarget({ item, action, step });

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">{t("apoa.title")}</h1>
        <LanguageSwitch />
      </div>
      <p className="text-sm">{t("apoa.intro")}</p>
      {list && (
        <p className="rounded-lg bg-accent px-3 py-2 text-sm text-accent-foreground">
          {t("apoa.deadline", { hours: list.deadline_hours })}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {t("common.loadFailed", { reason: error })}
        </p>
      )}
      {list?.truncated && (
        <p role="status" className="text-sm text-muted-foreground">
          {t("apoa.truncated")}
        </p>
      )}
      {list && list.unregistered.length > 0 && (
        <section aria-labelledby="apoa-unregistered" className="space-y-2 rounded-lg border border-destructive p-3 text-sm">
          <h2 id="apoa-unregistered" className="font-semibold text-destructive">
            {t("apoa.unregistered.title")}
          </h2>
          <ul className="space-y-2">
            {list.unregistered.map((flag) => (
              <li key={flag.booking_id} className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  {t("apoa.unregistered.body", {
                    guest: flag.guest_name,
                    number: flag.booking_number,
                    listed: flag.listed,
                    expected: flag.expected,
                  })}
                </span>
                {canSeeIds && (
                  <button
                    type="button"
                    onClick={() => setGuestsOf(flag.booking_id)}
                    className="min-h-11 rounded-md border border-border px-3 py-2 hover:bg-accent"
                  >
                    {t("apoa.unregistered.open")}
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
      <div role="tablist" aria-label={t("apoa.title")} className="flex flex-wrap gap-2">
        {APOA_TABS.map((name) => (
          <button
            key={name}
            type="button"
            role="tab"
            aria-selected={tab === name}
            onClick={() => setTab(name)}
            className={`min-h-11 rounded-md border px-4 py-2 text-sm ${
              tab === name
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border hover:bg-accent"
            }`}
          >
            {t(`apoa.tab.${name}`)}
            {list && ` (${list[name].length})`}
          </button>
        ))}
      </div>
      {!list ? (
        <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
      ) : items.length === 0 ? (
        <p className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">
          {t(`apoa.empty.${tab}`)}
        </p>
      ) : (
        <ul className="space-y-3">
          {items.map((item) => (
            <ApoaCard
              key={`${item.booking_id}-${item.guest_id}`}
              item={item}
              canEdit={canEdit}
              canSeePhoto={canSeePhoto}
              onAction={onAction}
            />
          ))}
        </ul>
      )}
      {list && <ApoaRegister today={list.date} />}
      <ApoaStepDialog
        target={target}
        onClose={() => setTarget(null)}
        onDone={(changed) => {
          setTarget(null);
          setList(changed);
        }}
      />
      <GuestIdDialog
        bookingId={guestsOf}
        onClose={() => setGuestsOf(null)}
        onChanged={() => void load()}
      />
    </div>
  );
}
