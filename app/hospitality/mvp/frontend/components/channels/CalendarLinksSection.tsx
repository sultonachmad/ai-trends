"use client";

import { useCallback, useEffect, useState } from "react";

import { CalendarLinkDialog } from "@/components/channels/CalendarLinkDialog";
import { CalendarLinkRow } from "@/components/channels/CalendarLinkRow";
import { exportUrl } from "@/lib/calendar-link-format";
import {
  fetchCalendarLinks,
  removeCalendarLink,
  replaceCalendarToken,
  syncCalendarLink,
  updateCalendarLink,
  type CalendarLink,
  type CalendarLinkCreated,
} from "@/lib/calendar-links-api";
import { useLocale } from "@/lib/locale-store";
import { useCan } from "@/lib/rbac-store";
import { fetchRoomTypes, type RoomType } from "@/lib/rooms-api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const cardClass = "rounded-xl border border-border bg-card text-card-foreground shadow-sm";
const errorText = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));

/** Calendar links for Airbnb and similar sites: availability only, in both directions. */
export function CalendarLinksSection() {
  const { t } = useLocale();
  const canEdit = useCan("channels:edit");
  const [links, setLinks] = useState<CalendarLink[] | null>(null);
  const [rooms, setRooms] = useState<RoomType[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [dialog, setDialog] = useState<{ link: CalendarLink | null } | null>(null);
  const [shown, setShown] = useState<CalendarLinkCreated | null>(null);
  const [copied, setCopied] = useState(false);

  const reload = useCallback(async () => setLinks(await fetchCalendarLinks()), []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchCalendarLinks(), fetchRoomTypes().catch(() => [] as RoomType[])])
      .then(([found, roomTypes]) => {
        if (cancelled) return;
        setLinks(found);
        setRooms(roomTypes.filter((room) => room.is_active));
      })
      .catch((cause) => {
        if (!cancelled) setError(errorText(cause));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const act = async (id: string, call: () => Promise<unknown>) => {
    setBusyId(id);
    setError(null);
    try {
      await call();
      await reload();
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusyId(null);
    }
  };

  const reveal = (created: CalendarLinkCreated) => {
    setCopied(false);
    setShown(created);
  };
  const replace = (link: CalendarLink) => {
    if (!window.confirm(t("calendarLinks.replaceConfirm", { label: link.label }))) return;
    void act(link.id, async () => reveal(await replaceCalendarToken(link.id)));
  };
  const stopImport = (link: CalendarLink) => {
    if (!window.confirm(t("calendarLinks.stopImportConfirm", { label: link.label }))) return;
    void act(link.id, () => updateCalendarLink(link.id, { import_url: null }));
  };
  const remove = (link: CalendarLink) => {
    if (!window.confirm(t("calendarLinks.removeConfirm", { label: link.label }))) return;
    void act(link.id, () => removeCalendarLink(link.id));
  };
  const saved = (result: CalendarLink | CalendarLinkCreated) => {
    setDialog(null);
    if ("export_path" in result) reveal(result);
    void reload().catch((cause) => setError(errorText(cause)));
  };
  const address = shown ? exportUrl(API_BASE, shown.export_path) : "";
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(address);
      setCopied(true);
    } catch {
      setCopied(false); // the address stays selectable on screen
    }
  };

  return (
    <section className={cardClass} aria-labelledby="calendar-links-heading">
      <div className="flex flex-wrap items-center justify-between gap-3 p-4">
        <h2 id="calendar-links-heading" className="text-lg font-semibold">
          {t("calendarLinks.title")}
        </h2>
        {canEdit && (
          <button
            type="button"
            disabled={rooms.length === 0}
            onClick={() => setDialog({ link: null })}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {t("calendarLinks.add")}
          </button>
        )}
      </div>
      <div className="space-y-1 px-4 pb-3 text-sm text-muted-foreground">
        <p>{t("calendarLinks.intro")}</p>
        <p>{t("calendarLinks.slowWarning")}</p>
      </div>
      {shown && (
        <div className="mx-4 mb-3 space-y-2 rounded-lg bg-muted p-3 text-sm">
          <p className="font-medium">{t("calendarLinks.copyTitle", { label: shown.label })}</p>
          <p className="text-muted-foreground">{t("calendarLinks.copyOnce")}</p>
          <input
            readOnly
            aria-label={t("calendarLinks.exportAddress")}
            value={address}
            onFocus={(event) => event.target.select()}
            className="w-full rounded-md border border-border bg-card px-3 py-2 font-mono text-xs"
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => void copy()}
              className="rounded-md bg-primary px-3 py-1 text-sm text-primary-foreground"
            >
              {t(copied ? "calendarLinks.copied" : "calendarLinks.copy")}
            </button>
            <button
              type="button"
              onClick={() => setShown(null)}
              className="rounded-md border border-border px-3 py-1 text-sm hover:bg-accent"
            >
              {t("calendarLinks.done")}
            </button>
          </div>
        </div>
      )}
      {error && (
        <p role="alert" className="px-4 pb-3 text-sm text-destructive">
          {error}
        </p>
      )}
      <div className="border-t border-border">
        {links === null ? (
          <p className="p-4 text-sm text-muted-foreground">{t("common.loading")}</p>
        ) : links.length === 0 ? (
          <p className="p-4 text-sm text-muted-foreground">{t("calendarLinks.none")}</p>
        ) : (
          <ul className="divide-y divide-border">
            {links.map((link) => (
              <CalendarLinkRow
                key={link.id}
                link={link}
                canEdit={canEdit}
                busy={busyId === link.id}
                onSync={() => void act(link.id, () => syncCalendarLink(link.id))}
                onStopImport={() => stopImport(link)}
                onEdit={() => setDialog({ link })}
                onReplace={() => replace(link)}
                onRemove={() => remove(link)}
              />
            ))}
          </ul>
        )}
      </div>
      <CalendarLinkDialog
        open={dialog !== null}
        link={dialog?.link ?? null}
        rooms={rooms}
        onClose={() => setDialog(null)}
        onSaved={saved}
      />
    </section>
  );
}
