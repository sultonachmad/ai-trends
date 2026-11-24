"use client";

/** Front desk — today's arrivals, in-house guests, departures and rooms. */

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { AssignRoomDialog } from "@/components/front-desk/AssignRoomDialog";
import { DeskActionDialog } from "@/components/front-desk/DeskActionDialog";
import {
  DeskEntryCard,
  type DeskActionKind,
} from "@/components/front-desk/DeskEntryCard";
import { RoomsToday } from "@/components/front-desk/RoomsToday";
import { StayChangeDialog } from "@/components/front-desk/StayChangeDialog";
import { LanguageSwitch } from "@/components/LanguageSwitch";
import { ApiError } from "@/lib/api-client";
import { shortDate } from "@/lib/booking-format";
import {
  fetchDeskToday,
  type DeskEntry,
  type DeskRoom,
  type DeskToday,
} from "@/lib/front-desk-api";
import { DESK_TABS, type DeskTab } from "@/lib/front-desk-format";
import { useLocale } from "@/lib/locale-store";
import { useCan } from "@/lib/rbac-store";
import { fetchOnboardingStatus } from "@/lib/workspace-api";

const FORBIDDEN = 403;
const TAB_ACTIONS: Record<Exclude<DeskTab, "rooms">, readonly DeskActionKind[]> = {
  arrivals: ["checkin", "noshow"],
  in_house: ["checkout", "stay", "undo"],
  departures: ["checkout", "stay"],
};
const errorText = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));

type ConfirmAction = { kind: Exclude<DeskActionKind, "stay">; entry: DeskEntry };

export default function FrontDeskPage() {
  const router = useRouter();
  const { t, locale } = useLocale();
  const canEdit = useCan("frontdesk:edit");
  const [desk, setDesk] = useState<DeskToday | null>(null);
  const [tab, setTab] = useState<DeskTab>("arrivals");
  const [noAccess, setNoAccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [roomTarget, setRoomTarget] = useState<{ entry: DeskEntry; room: DeskRoom } | null>(null);
  const [action, setAction] = useState<ConfirmAction | null>(null);
  const [changing, setChanging] = useState<DeskEntry | null>(null);
  const requestId = useRef(0);

  const load = useCallback(async () => {
    const id = ++requestId.current;
    try {
      const found = await fetchDeskToday();
      if (id !== requestId.current) return;
      setDesk(found);
      setError(null);
    } catch (cause) {
      if (id !== requestId.current) return;
      if (cause instanceof ApiError && cause.status === FORBIDDEN) setNoAccess(true);
      else setError(errorText(cause));
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchOnboardingStatus()
      .then((status) => {
        if (cancelled) return;
        if (!status.has_workspace) router.replace("/onboarding");
        else void load();
      })
      .catch((cause) => {
        if (!cancelled) setError(errorText(cause));
      });
    return () => {
      cancelled = true;
    };
  }, [router, load]);

  const finished = () => {
    setRoomTarget(null);
    setAction(null);
    setChanging(null);
    void load();
  };
  const onAction = (kind: DeskActionKind, entry: DeskEntry) => {
    if (kind === "stay") setChanging(entry);
    else setAction({ kind, entry });
  };
  const card = (entry: DeskEntry, actions: readonly DeskActionKind[]) => (
    <DeskEntryCard
      key={entry.id}
      entry={entry}
      actions={actions}
      canEdit={canEdit}
      onAction={onAction}
      onRoom={(owner, room) => setRoomTarget({ entry: owner, room })}
    />
  );

  if (noAccess) {
    return <p role="alert" className="p-8 text-sm">{t("frontdesk.noAccess")}</p>;
  }
  const list = desk && tab !== "rooms" ? desk[tab] : [];
  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{t("frontdesk.title")}</h1>
          {desk && (
            <p className="text-sm text-muted-foreground">{shortDate(desk.date, locale)}</p>
          )}
        </div>
        <LanguageSwitch />
      </div>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {t("common.loadFailed", { reason: error })}
        </p>
      )}
      <div role="tablist" aria-label={t("frontdesk.title")} className="flex flex-wrap gap-2">
        {DESK_TABS.map((name) => (
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
            {t(`frontdesk.tab.${name}`)}
            {desk && name !== "rooms" && ` (${desk[name].length})`}
          </button>
        ))}
      </div>
      {!desk ? (
        <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
      ) : tab === "rooms" ? (
        <RoomsToday rooms={desk.rooms} />
      ) : list.length === 0 ? (
        <p className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">
          {t(`frontdesk.empty.${tab}`)}
        </p>
      ) : (
        <ul className="space-y-3">
          {list.map((entry) =>
            card(
              entry,
              TAB_ACTIONS[tab].filter((kind) => kind !== "undo" || entry.can_undo),
            ),
          )}
        </ul>
      )}
      {desk && desk.done_today.length > 0 && (
        <section aria-labelledby="desk-done" className="space-y-2">
          <h2 id="desk-done" className="text-sm font-semibold">
            {t("frontdesk.doneToday")}
          </h2>
          <ul className="space-y-3">{desk.done_today.map((entry) => card(entry, ["undo"]))}</ul>
        </section>
      )}
      <AssignRoomDialog
        target={roomTarget}
        onClose={() => setRoomTarget(null)}
        onDone={finished}
      />
      {desk && (
        <>
          <DeskActionDialog
            action={action}
            today={desk.date}
            onClose={() => setAction(null)}
            onDone={finished}
          />
          <StayChangeDialog
            entry={changing}
            today={desk.date}
            onClose={() => setChanging(null)}
            onDone={finished}
          />
        </>
      )}
    </div>
  );
}
