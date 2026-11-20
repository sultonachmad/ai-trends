"use client";

/**
 * One channel connection: where it is in its setup, the matching of rooms and rates,
 * its settings, status changes and history. Reachable at `/channels/<id>`.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { ConnectionSettingsForm } from "@/components/channels/ConnectionSettingsForm";
import { MappingEditor } from "@/components/channels/MappingEditor";
import { LanguageSwitch } from "@/components/LanguageSwitch";
import {
  actionsFor,
  canMatch,
  eventKey,
  nextStep,
  problemKey,
  SETUP_STEPS,
  statusBadgeClass,
  statusKey,
} from "@/lib/channel-format";
import {
  actOnConnection,
  fetchConnection,
  type ConnectionAction,
  type ConnectionDetail,
} from "@/lib/channels-api";
import { formatListTime } from "@/lib/inbox-format";
import { useLocale } from "@/lib/locale-store";
import { fetchRatePlans, type RatePlan } from "@/lib/rate-plans-api";
import { fetchRoomTypes, type RoomType } from "@/lib/rooms-api";
import { fetchOnboardingStatus } from "@/lib/workspace-api";

const ONBOARDING_PATH = "/onboarding";
const SIMULATOR = "simulator";
const cardClass = "rounded-xl border border-border bg-card text-card-foreground shadow-sm";
const secondary = "rounded-md border border-border px-4 py-2 text-sm hover:bg-accent disabled:opacity-50";
const primary =
  "rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50";
const errorText = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));

export default function ChannelConnectionPage() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const { t, locale } = useLocale();
  const [connection, setConnection] = useState<ConnectionDetail | null>(null);
  const [rooms, setRooms] = useState<RoomType[]>([]);
  const [plans, setPlans] = useState<RatePlan[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const reload = useCallback(async () => {
    setConnection(await fetchConnection(id));
  }, [id]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const status = await fetchOnboardingStatus();
        if (cancelled) return;
        if (!status.has_workspace) {
          router.replace(ONBOARDING_PATH);
          return;
        }
        const [found, loadedRooms, loadedPlans] = await Promise.all([
          fetchConnection(id),
          fetchRoomTypes(),
          fetchRatePlans(),
        ]);
        if (cancelled) return;
        setRooms(loadedRooms);
        setPlans(loadedPlans);
        setConnection(found);
      } catch (cause) {
        if (!cancelled) setLoadError(errorText(cause));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, router]);

  const act = async (action: ConnectionAction) => {
    setBusy(true);
    setActionError(null);
    try {
      setConnection(await actOnConnection(id, action));
      setConfirming(false);
    } catch (cause) {
      setActionError(errorText(cause));
    } finally {
      setBusy(false);
    }
  };

  if (loadError) {
    return (
      <p role="alert" className="p-8 text-sm text-destructive">
        {t("common.loadFailed", { reason: loadError })}
      </p>
    );
  }
  if (!connection) {
    return <p className="p-8 text-sm text-muted-foreground">{t("common.loading")}</p>;
  }

  const step = nextStep(connection);
  const actions = actionsFor(connection);
  const when = (iso: string) => formatListTime(iso, locale, new Date());

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link href="/channels" className="text-sm font-medium text-primary hover:underline">
            ← {t("channels.back")}
          </Link>
          <h1 className="mt-1 flex flex-wrap items-center gap-2 text-2xl font-bold">
            {connection.channel_name}
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusBadgeClass(connection.status)}`}
            >
              {t(statusKey(connection.status))}
            </span>
          </h1>
          <p className="text-sm text-muted-foreground">
            {t("channels.propertyId", { id: connection.external_property_id })}
            {connection.channel_property_name ? ` · ${connection.channel_property_name}` : ""}
          </p>
        </div>
        <LanguageSwitch />
      </div>

      <section className={`${cardClass} space-y-3 p-4`} aria-labelledby="status-heading">
        <h2 id="status-heading" className="sr-only">
          {t("channels.steps")}
        </h2>
        {step !== null && (
          <ol className="flex flex-wrap gap-2 text-sm">
            {SETUP_STEPS.map((name, index) => (
              <li
                key={name}
                aria-current={name === step ? "step" : undefined}
                className={`rounded-full px-3 py-1 ${
                  name === step
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground"
                }`}
              >
                {index + 1}. {t(`channels.step.${name}`)}
              </li>
            ))}
          </ol>
        )}
        {step !== null && <p className="text-sm">{t(`channels.hint.${step}`)}</p>}
        {connection.problem && (
          <p role="alert" className="text-sm text-destructive">
            {t(problemKey(connection.problem))}
          </p>
        )}
        {connection.channel_code === SIMULATOR && connection.status !== "disconnected" && (
          <p className="text-xs text-muted-foreground">{t("channels.hint.simulated")}</p>
        )}
        {connection.last_tested_at && (
          <p className="text-xs text-muted-foreground">
            {t("channels.lastTested", { when: when(connection.last_tested_at) })}
          </p>
        )}
        {actionError && (
          <p role="alert" className="text-sm text-destructive">
            {actionError}
          </p>
        )}
        {confirming ? (
          <div className="space-y-2 rounded-lg border border-destructive/40 p-3 text-sm">
            <p>{t("channels.disconnect.confirm")}</p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={() => void act("disconnect")}
                className="rounded-md bg-destructive/15 px-3 py-1.5 text-sm font-medium text-destructive hover:bg-destructive/25 disabled:opacity-50"
              >
                {t("channels.disconnect.yes")}
              </button>
              <button type="button" disabled={busy} onClick={() => setConfirming(false)} className={secondary}>
                {t("channels.disconnect.no")}
              </button>
            </div>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {actions.map((action, index) => (
              <button
                key={action}
                type="button"
                disabled={busy}
                onClick={() => (action === "disconnect" ? setConfirming(true) : void act(action))}
                className={index === 0 && action !== "disconnect" ? primary : secondary}
              >
                {t(`channels.action.${action}`)}
              </button>
            ))}
          </div>
        )}
      </section>

      {canMatch(connection.status) && (
        <section className={cardClass} aria-labelledby="matching-heading">
          <h2 id="matching-heading" className="border-b border-border p-4 text-lg font-semibold">
            {t("channels.matching")}
          </h2>
          <MappingEditor
            connection={connection}
            rooms={rooms}
            plans={plans}
            onSaved={setConnection}
            onRefreshed={() => void reload().catch((cause) => setActionError(errorText(cause)))}
          />
        </section>
      )}

      <section className={cardClass} aria-labelledby="settings-heading">
        <h2 id="settings-heading" className="border-b border-border p-4 text-lg font-semibold">
          {t("channels.settings")}
        </h2>
        <ConnectionSettingsForm connection={connection} onSaved={setConnection} />
      </section>

      <section className={cardClass} aria-labelledby="history-heading">
        <h2 id="history-heading" className="border-b border-border p-4 text-lg font-semibold">
          {t("channels.history")}
        </h2>
        <ol className="divide-y divide-border text-sm">
          {connection.history.map((entry) => (
            <li key={`${entry.at}-${entry.event}`} className="px-4 py-2">
              {t("channels.history.by", { event: t(eventKey(entry.event)), when: when(entry.at) })}
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
