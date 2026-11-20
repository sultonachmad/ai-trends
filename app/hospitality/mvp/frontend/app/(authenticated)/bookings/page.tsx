"use client";

/**
 * Bookings — every booking of the property, whatever its source.
 * Reachable at `/bookings`. `?from=<conversation id>` (from the inbox) opens a new
 * booking for that chat's guest.
 */

import { Suspense, useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { BookingDetailDialog } from "@/components/bookings/BookingDetailDialog";
import { BookingDialog, type BookingPrefill } from "@/components/bookings/BookingDialog";
import { BookingTable } from "@/components/bookings/BookingTable";
import { LanguageSwitch } from "@/components/LanguageSwitch";
import {
  fetchBookings,
  type Booking,
  type BookingDetail,
  type BookingTab,
} from "@/lib/bookings-api";
import { todayIn } from "@/lib/calendar-grid";
import { fetchConversation } from "@/lib/inbox-api";
import { useLocale } from "@/lib/locale-store";
import { fetchRatePlans, type RatePlan } from "@/lib/rate-plans-api";
import { fetchRoomTypes, type RoomType } from "@/lib/rooms-api";
import { fetchOnboardingStatus, fetchWorkspace, type Workspace } from "@/lib/workspace-api";

const ONBOARDING_PATH = "/onboarding";
const BOOKINGS_PATH = "/bookings";
const TABS: readonly BookingTab[] = ["upcoming", "staying", "past", "cancelled"];
const SEARCH_MAX = 80;
const errorText = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));

/** `undefined` = closed, `null` = a new booking, a booking = changing it. */
type Editing = Booking | null | undefined;

function BookingsScreen() {
  const router = useRouter();
  const fromConversation = useSearchParams().get("from");
  const { t } = useLocale();
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [rooms, setRooms] = useState<RoomType[]>([]);
  const [plans, setPlans] = useState<RatePlan[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [tab, setTab] = useState<BookingTab>("upcoming");
  const [typed, setTyped] = useState("");
  const [query, setQuery] = useState("");
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Editing>(undefined);
  const [prefill, setPrefill] = useState<BookingPrefill | undefined>(undefined);
  const [openId, setOpenId] = useState<string | null>(null);
  const listRequest = useRef(0);

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
        const [loaded, loadedRooms, loadedPlans] = await Promise.all([
          fetchWorkspace(),
          fetchRoomTypes(),
          fetchRatePlans(),
        ]);
        if (cancelled) return;
        setRooms(loadedRooms.filter((room) => room.is_active));
        setPlans(loadedPlans.filter((plan) => plan.is_active));
        setWorkspace(loaded);
      } catch (cause) {
        if (!cancelled) setLoadError(errorText(cause));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  // Coming from a chat: open a new booking for that guest, then drop the parameter.
  useEffect(() => {
    if (!workspace || !fromConversation) return;
    let cancelled = false;
    fetchConversation(fromConversation)
      .then((conversation) => {
        if (cancelled) return;
        setPrefill({
          guestName: conversation.guest.name,
          guestPhone: conversation.guest.phone ?? "",
          conversationId: conversation.id,
        });
        setEditing(null);
      })
      .catch((cause) => {
        if (!cancelled) setListError(errorText(cause));
      })
      .finally(() => {
        if (!cancelled) router.replace(BOOKINGS_PATH, { scroll: false });
      });
    return () => {
      cancelled = true;
    };
  }, [workspace, fromConversation, router]);

  const load = useCallback(
    async (cursor: string | null) => {
      const request = ++listRequest.current;
      try {
        const page = await fetchBookings(tab, query || undefined, cursor);
        if (request !== listRequest.current) return; // a newer tab or search was asked for
        setBookings((current) => (cursor ? [...current, ...page.items] : page.items));
        setNextCursor(page.next_cursor);
        setListError(null);
      } catch (cause) {
        if (request === listRequest.current) setListError(errorText(cause));
      } finally {
        if (request === listRequest.current) setReady(true);
      }
    },
    [tab, query],
  );

  useEffect(() => {
    if (!workspace) return;
    setReady(false);
    setNextCursor(null); // it belonged to the previous tab or search
    void load(null);
  }, [workspace, load]);

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

  const today = todayIn(workspace.property.timezone);
  const onSearch = (event: FormEvent) => {
    event.preventDefault();
    setQuery(typed.trim());
  };
  const onSaved = (saved: BookingDetail) => {
    setEditing(undefined);
    setPrefill(undefined);
    setOpenId(saved.id);
    void load(null);
  };

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">{t("bookings.title")}</h1>
        <div className="flex flex-wrap items-center gap-3">
          <LanguageSwitch />
          <button
            type="button"
            onClick={() => setEditing(null)}
            disabled={rooms.length === 0 || plans.length === 0}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {t("bookings.new")}
          </button>
        </div>
      </div>
      {(rooms.length === 0 || plans.length === 0) && (
        <p className="rounded-lg bg-muted px-4 py-3 text-sm">{t("calendar.needSetup")}</p>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="tablist" aria-label={t("bookings.tablist")} className="flex flex-wrap gap-1">
          {TABS.map((option) => (
            <button
              key={option}
              type="button"
              role="tab"
              aria-selected={tab === option}
              onClick={() => setTab(option)}
              className={`rounded-md px-3 py-1 text-sm font-medium ${
                tab === option
                  ? "bg-primary text-primary-foreground"
                  : "border border-border bg-card hover:bg-accent"
              }`}
            >
              {t(`bookings.tab.${option}`)}
            </button>
          ))}
        </div>
        <form onSubmit={onSearch} role="search" className="flex gap-2">
          <input
            type="search"
            value={typed}
            maxLength={SEARCH_MAX}
            aria-label={t("bookings.search")}
            placeholder={t("bookings.search")}
            onChange={(event) => setTyped(event.target.value)}
            className="w-56 max-w-full rounded-md border border-border bg-card px-3 py-1.5 text-sm text-card-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <button type="submit" className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-accent">
            {t("bookings.searchButton")}
          </button>
          {query && (
            <button
              type="button"
              onClick={() => {
                setTyped("");
                setQuery("");
              }}
              className="text-sm font-medium text-primary hover:underline"
            >
              {t("bookings.clearSearch")}
            </button>
          )}
        </form>
      </div>

      {listError && (
        <p role="alert" className="text-sm text-destructive">
          {t("inbox.actionFailed", { reason: listError })}
        </p>
      )}

      <section className="rounded-xl border border-border bg-card text-card-foreground">
        {!ready && <p className="p-4 text-sm text-muted-foreground">{t("common.loading")}</p>}
        {ready && bookings.length === 0 && (
          <p className="p-4 text-sm text-muted-foreground">
            {query ? t("bookings.empty.search") : t(`bookings.empty.${tab}`)}
          </p>
        )}
        {ready && bookings.length > 0 && (
          <BookingTable bookings={bookings} today={today} onOpen={(booking) => setOpenId(booking.id)} />
        )}
        {nextCursor && (
          <button
            type="button"
            onClick={() => void load(nextCursor)}
            className="w-full border-t border-border px-4 py-3 text-sm font-medium hover:bg-accent"
          >
            {t("bookings.loadMore")}
          </button>
        )}
      </section>

      <BookingDetailDialog
        bookingId={editing === undefined ? openId : null}
        today={today}
        onClose={() => setOpenId(null)}
        onChanged={() => void load(null)}
        onEdit={(booking) => setEditing(booking)}
      />
      <BookingDialog
        open={editing !== undefined}
        booking={editing ?? undefined}
        rooms={rooms}
        plans={plans}
        today={today}
        prefill={prefill}
        onClose={() => {
          setEditing(undefined);
          setPrefill(undefined);
        }}
        onSaved={onSaved}
      />
    </div>
  );
}

export default function BookingsPage() {
  // useSearchParams needs a Suspense boundary to build.
  return (
    <Suspense fallback={null}>
      <BookingsScreen />
    </Suspense>
  );
}
