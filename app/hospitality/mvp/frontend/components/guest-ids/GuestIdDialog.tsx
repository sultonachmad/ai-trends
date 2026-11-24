"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Dialog } from "@/components/Dialog";
import { GuestIdCard } from "@/components/guest-ids/GuestIdCard";
import { IdCaptureForm } from "@/components/guest-ids/IdCaptureForm";
import {
  fetchGuests,
  fetchIdHistory,
  removeGuest,
  type BookingGuests,
  type GuestOnBooking,
  type IdView,
} from "@/lib/guest-ids-api";
import { guestIdErrorKey } from "@/lib/id-format";
import { formatClock, formatShortDate } from "@/lib/inbox-format";
import { useLocale } from "@/lib/locale-store";
import { useCan } from "@/lib/rbac-store";

interface GuestIdDialogProps {
  /** The booking whose guests to show; null closes the dialog. */
  bookingId: string | null;
  onClose: () => void;
  /** An ID was confirmed or a guest removed: lists behind may refresh. */
  onChanged: () => void;
}

const secondary =
  "min-h-11 rounded-md border border-border px-4 py-2 text-sm hover:bg-accent disabled:opacity-50";

type Capture = { guest: { id: string; name: string } | null } | null;

function History({ entries }: { entries: IdView[] }) {
  const { t, locale } = useLocale();
  return (
    <section aria-labelledby="guest-id-history" className="space-y-1 text-sm">
      <h3 id="guest-id-history" className="font-semibold">
        {t("guestid.history")}
      </h3>
      {entries.length === 0 ? (
        <p className="text-muted-foreground">{t("guestid.historyEmpty")}</p>
      ) : (
        <ul className="space-y-1">
          {entries.map((entry, index) => (
            <li key={`${entry.at}-${index}`} className="flex flex-wrap justify-between gap-2">
              <span>{t(`guestid.event.${entry.event}`, { by: entry.by })}</span>
              <span className="text-muted-foreground tabular-nums">
                {formatShortDate(entry.at, locale)} {formatClock(entry.at, locale)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** Who is staying, their masked IDs, capture and confirm, and who looked at what. */
export function GuestIdDialog({ bookingId, onClose, onChanged }: GuestIdDialogProps) {
  const { t } = useLocale();
  const canEdit = useCan("guestid:edit");
  const [guests, setGuests] = useState<BookingGuests | null>(null);
  const [history, setHistory] = useState<IdView[]>([]);
  const [capture, setCapture] = useState<Capture>(null);
  const [error, setError] = useState<string | null>(null);
  const request = useRef(0);

  const fail = useCallback(
    (cause: unknown) => {
      const key = guestIdErrorKey(cause);
      setError(key ? t(key) : cause instanceof Error ? cause.message : String(cause));
    },
    [t],
  );
  const loadHistory = useCallback(async (id: string, ticket: number) => {
    try {
      const found = await fetchIdHistory(id);
      if (ticket === request.current) setHistory(found);
    } catch {
      // the history is secondary; the guest list still works without it
    }
  }, []);

  useEffect(() => {
    setGuests(null);
    setHistory([]);
    setCapture(null);
    setError(null);
    if (!bookingId) return;
    const ticket = ++request.current;
    fetchGuests(bookingId)
      .then((found) => {
        if (ticket === request.current) setGuests(found);
      })
      .catch((cause) => {
        if (ticket === request.current) fail(cause);
      });
    void loadHistory(bookingId, ticket);
  }, [bookingId, fail, loadHistory]);

  if (!bookingId) return <Dialog open={false} onClose={onClose}>{null}</Dialog>;
  const editable = canEdit && (guests?.can_change ?? false);
  const refreshHistory = () => void loadHistory(bookingId, request.current);

  const saved = (changed: BookingGuests) => {
    setGuests(changed);
    setCapture(null);
    refreshHistory();
    onChanged();
  };
  const remove = async (guest: GuestOnBooking) => {
    if (!window.confirm(t("guestid.removeConfirm", { name: guest.full_name }))) return;
    setError(null);
    try {
      await removeGuest(bookingId, guest.guest_id);
      saved(await fetchGuests(bookingId));
    } catch (cause) {
      fail(cause);
    }
  };

  return (
    <Dialog open onClose={onClose} title={t(capture ? "guestid.form.title" : "guestid.title")}>
      {capture ? (
        <IdCaptureForm
          bookingId={bookingId}
          guest={capture.guest}
          onSaved={saved}
          onCancel={() => setCapture(null)}
        />
      ) : (
        <div className="space-y-4 text-sm">
          {!guests && !error && <p className="text-muted-foreground">{t("guestid.loading")}</p>}
          {guests && (
            <p
              role="status"
              className={`rounded-lg px-3 py-2 ${guests.main_guest_ready ? "bg-accent text-accent-foreground" : "bg-destructive/10 text-destructive"}`}
            >
              {t(guests.main_guest_ready ? "guestid.ready" : "guestid.notReady")}
            </p>
          )}
          {guests && !guests.can_change && <p className="text-muted-foreground">{t("guestid.closed")}</p>}
          {guests && guests.can_change && !canEdit && (
            <p className="text-muted-foreground">{t("guestid.readOnly")}</p>
          )}
          {guests && (
            <ul className="space-y-3">
              {guests.guests.map((guest) => (
                <GuestIdCard
                  key={guest.guest_id}
                  bookingId={bookingId}
                  guest={guest}
                  canEdit={editable}
                  canReveal={canEdit}
                  onCapture={(chosen) =>
                    setCapture({ guest: { id: chosen.guest_id, name: chosen.full_name } })
                  }
                  onRemove={(chosen) => void remove(chosen)}
                  onViewed={refreshHistory}
                />
              ))}
            </ul>
          )}
          {error && (
            <p role="alert" className="text-destructive">
              {error}
            </p>
          )}
          <div className="flex flex-wrap justify-between gap-2">
            {editable ? (
              <button type="button" className={secondary} onClick={() => setCapture({ guest: null })}>
                {t("guestid.addGuest")}
              </button>
            ) : (
              <span />
            )}
            <button type="button" className={secondary} onClick={onClose}>
              {t("frontdesk.back")}
            </button>
          </div>
          <History entries={history} />
        </div>
      )}
    </Dialog>
  );
}
