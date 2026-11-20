"use client";

/**
 * Rooms & rates — the room types a property sells and its rate plans.
 * Reachable at `/rooms`. Single dates are changed on the calendar (`/calendar`).
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { LanguageSwitch } from "@/components/LanguageSwitch";
import { RatePlanDialog } from "@/components/rooms/RatePlanDialog";
import { RatePlanList, RoomTypeList } from "@/components/rooms/RoomLists";
import { RoomTypeDialog } from "@/components/rooms/RoomTypeDialog";
import { useCan } from "@/lib/rbac-store";
import { useLocale } from "@/lib/locale-store";
import { fetchRatePlans, updateRatePlan, type RatePlan } from "@/lib/rate-plans-api";
import { numberSetting } from "@/lib/room-forms";
import { fetchRoomTypes, updateRoomType, type RoomType } from "@/lib/rooms-api";
import { fetchOnboardingStatus, fetchWorkspace, type Workspace } from "@/lib/workspace-api";

const ONBOARDING_PATH = "/onboarding";
const cardClass = "rounded-xl border border-border bg-card text-card-foreground shadow-sm";
const primaryButton =
  "rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50";
const errorText = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));

/** `undefined` = closed, `null` = creating, a record = editing it. */
type Editing<T> = T | null | undefined;

export default function RoomsPage() {
  const router = useRouter();
  const { t } = useLocale();
  const canEdit = useCan("rooms:edit");
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [rooms, setRooms] = useState<RoomType[]>([]);
  const [plans, setPlans] = useState<RatePlan[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [editingRoom, setEditingRoom] = useState<Editing<RoomType>>(undefined);
  const [editingPlan, setEditingPlan] = useState<Editing<RatePlan>>(undefined);

  const reload = useCallback(async () => {
    const [loadedRooms, loadedPlans] = await Promise.all([fetchRoomTypes(), fetchRatePlans()]);
    setRooms(loadedRooms);
    setPlans(loadedPlans);
  }, []);

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
        const loaded = await fetchWorkspace();
        await reload();
        if (!cancelled) setWorkspace(loaded);
      } catch (cause) {
        if (!cancelled) setLoadError(errorText(cause));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router, reload]);

  // Switching on or off, then showing what the server now has.
  const act = async (change: () => Promise<unknown>) => {
    setActionError(null);
    try {
      await change();
      await reload();
    } catch (cause) {
      setActionError(errorText(cause));
    }
  };

  if (loadError) {
    return (
      <p role="alert" className="p-8 text-sm text-destructive">
        {t("common.loadFailed", { reason: loadError })}
      </p>
    );
  }
  if (!workspace) {
    return <p className="p-8 text-sm text-muted-foreground">{t("common.loading")}</p>;
  }

  const settings = workspace.settings;
  const activeRooms = rooms.filter((room) => room.is_active);
  const ready = activeRooms.length > 0 && plans.some((plan) => plan.is_active);
  const saved = async () => {
    setEditingRoom(undefined);
    setEditingPlan(undefined);
    await reload().catch((cause) => setActionError(errorText(cause)));
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">{t("rooms.title")}</h1>
        <LanguageSwitch />
      </div>
      {actionError && (
        <p role="alert" className="text-sm text-destructive">
          {t("inbox.actionFailed", { reason: actionError })}
        </p>
      )}
      {ready && (
        <p className="flex flex-wrap items-center gap-3 rounded-lg bg-muted px-4 py-3 text-sm">
          <span>{t("rooms.nextHint")}</span>
          <Link href="/calendar" className="font-medium text-primary hover:underline">
            {t("rooms.openCalendar")}
          </Link>
        </p>
      )}

      <section className={cardClass} aria-labelledby="room-types-heading">
        <div className="flex flex-wrap items-start justify-between gap-3 p-4">
          <div>
            <h2 id="room-types-heading" className="text-lg font-semibold">
              {t("rooms.types")}
            </h2>
            <p className="text-sm text-muted-foreground">{t("rooms.types.intro")}</p>
          </div>
          <button
            type="button"
            onClick={() => setEditingRoom(null)}
            disabled={!canEdit}
            className={primaryButton}
          >
            {t("rooms.addType")}
          </button>
        </div>
        {rooms.length === 0 ? (
          <p className="border-t border-border p-4 text-sm text-muted-foreground">
            {t("rooms.empty")}
          </p>
        ) : (
          <div className="border-t border-border">
            <RoomTypeList
              rooms={rooms}
              onEdit={setEditingRoom}
              onToggle={(room) =>
                void act(() => updateRoomType(room.id, { is_active: !room.is_active }))
              }
            />
          </div>
        )}
      </section>

      <section className={cardClass} aria-labelledby="rate-plans-heading">
        <div className="flex flex-wrap items-start justify-between gap-3 p-4">
          <div>
            <h2 id="rate-plans-heading" className="text-lg font-semibold">
              {t("rates.title")}
            </h2>
            <p className="max-w-xl text-sm text-muted-foreground">{t("rates.intro")}</p>
          </div>
          <button
            type="button"
            onClick={() => setEditingPlan(null)}
            disabled={activeRooms.length === 0 || !canEdit}
            className={primaryButton}
          >
            {t("rates.add")}
          </button>
        </div>
        {plans.length === 0 ? (
          <p className="border-t border-border p-4 text-sm text-muted-foreground">
            {activeRooms.length === 0 ? t("rates.needRoomFirst") : t("rates.empty")}
          </p>
        ) : (
          <div className="border-t border-border">
            <RatePlanList
              plans={plans}
              rooms={rooms}
              onEdit={setEditingPlan}
              onToggle={(plan) =>
                void act(() => updateRatePlan(plan.id, { is_active: !plan.is_active }))
              }
            />
          </div>
        )}
      </section>

      <RoomTypeDialog
        open={editingRoom !== undefined}
        room={editingRoom ?? undefined}
        maxUnits={numberSetting(settings, "max_units_per_room_type", 100)}
        onClose={() => setEditingRoom(undefined)}
        onSaved={() => void saved()}
      />
      <RatePlanDialog
        open={editingPlan !== undefined}
        plan={editingPlan ?? undefined}
        rooms={activeRooms}
        bounds={{
          min: numberSetting(settings, "room_rate_min_amount_idr", 10_000),
          max: numberSetting(settings, "room_rate_max_amount_idr", 500_000_000),
        }}
        defaultFreeDays={numberSetting(settings, "free_cancellation_days", 7)}
        onClose={() => setEditingPlan(undefined)}
        onSaved={() => void saved()}
      />
    </div>
  );
}
