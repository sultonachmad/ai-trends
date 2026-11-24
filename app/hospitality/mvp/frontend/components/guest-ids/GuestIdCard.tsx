"use client";

import { useEffect, useState } from "react";

import { shortDate } from "@/lib/booking-format";
import {
  fetchIdImage,
  revealNumber,
  type GuestOnBooking,
} from "@/lib/guest-ids-api";
import { guestIdErrorKey } from "@/lib/id-format";
import { formatClock, formatShortDate } from "@/lib/inbox-format";
import { useLocale } from "@/lib/locale-store";

interface GuestIdCardProps {
  bookingId: string;
  guest: GuestOnBooking;
  /** May capture, replace, remove and show full details (guestid:edit, stay open). */
  canEdit: boolean;
  canReveal: boolean;
  onCapture: (guest: GuestOnBooking) => void;
  onRemove: (guest: GuestOnBooking) => void;
  /** A full view was logged: the history should refresh. */
  onViewed: () => void;
}

const SHOWN_FOR_MS = 60_000; // a revealed number or photo hides itself after a minute
const secondary =
  "min-h-11 rounded-md border border-border px-3 py-2 text-sm hover:bg-accent disabled:opacity-50";

/** One guest: their masked ID, and the logged "show" buttons. */
export function GuestIdCard({
  bookingId,
  guest,
  canEdit,
  canReveal,
  onCapture,
  onRemove,
  onViewed,
}: GuestIdCardProps) {
  const { t, locale } = useLocale();
  const doc = guest.document;
  const [number, setNumber] = useState<string | null>(null);
  const [photo, setPhoto] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setNumber(null);
    setPhoto(null);
  }, [doc?.id]);
  useEffect(() => () => {
    if (photo) URL.revokeObjectURL(photo);
  }, [photo]);
  useEffect(() => {
    if (!number && !photo) return;
    const timer = setTimeout(() => {
      setNumber(null);
      setPhoto(null);
    }, SHOWN_FOR_MS);
    return () => clearTimeout(timer);
  }, [number, photo]);

  const fail = (cause: unknown) => {
    const key = guestIdErrorKey(cause);
    setError(key ? t(key) : cause instanceof Error ? cause.message : String(cause));
  };
  const show = async () => {
    if (!doc) return;
    setError(null);
    try {
      setNumber((await revealNumber(bookingId, doc.id)).number);
      onViewed();
    } catch (cause) {
      fail(cause);
    }
  };
  const showPhoto = async () => {
    if (!doc) return;
    setError(null);
    try {
      setPhoto(URL.createObjectURL(await fetchIdImage(bookingId, doc.id)));
      onViewed();
    } catch (cause) {
      fail(cause);
    }
  };

  const confirmed = doc?.confirmed_at
    ? `${formatShortDate(doc.confirmed_at, locale)} ${formatClock(doc.confirmed_at, locale)}`
    : "";
  return (
    <li className="space-y-2 rounded-lg border border-border bg-card p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-semibold">{guest.full_name}</p>
        <span className={`rounded-full px-2 py-0.5 text-xs ${guest.is_main ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground"}`}>
          {t(guest.is_main ? "guestid.main" : "guestid.companion")}
        </span>
      </div>
      {!doc ? (
        <p className="text-sm text-destructive">{t("guestid.noId")}</p>
      ) : (
        <div className="space-y-1 text-sm">
          <p>
            <span className="font-medium">{t(`guestid.docType.${doc.doc_type}`)}</span>{" "}
            <span className="font-mono tabular-nums">
              {number ?? doc.masked_number ?? t("guestid.numberCleared")}
            </span>
            {doc.issuing_country && ` · ${doc.issuing_country}`}
          </p>
          {doc.expires_on && (
            <p>{t("guestid.expires", { date: shortDate(doc.expires_on, locale) })}</p>
          )}
          {doc.visa_type && (
            <p>
              {t(`guestid.visa.${doc.visa_type}`)}
              {doc.entry_date && ` · ${t("guestid.entry", { date: shortDate(doc.entry_date, locale) })}`}
            </p>
          )}
          {!doc.usable && <p className="text-destructive">{t("guestid.notUsable")}</p>}
          <p className="text-xs text-muted-foreground">
            {t("guestid.confirmedBy", { by: doc.confirmed_by ?? "-", when: confirmed })} ·{" "}
            {t(doc.has_image ? "guestid.photoKept" : "guestid.noPhoto")}
          </p>
        </div>
      )}
      {photo && (
        // A decrypted ID photo from our own API, shown only on request; not optimisable.
        // eslint-disable-next-line @next/next/no-img-element
        <img src={photo} alt={t("guestid.form.photo")} className="max-h-80 w-full rounded-md object-contain" />
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {canReveal && doc?.masked_number && (
          <button
            type="button"
            className={secondary}
            onClick={() => (number ? setNumber(null) : void show())}
            title={t("guestid.logged")}
          >
            {t(number ? "guestid.hide" : "guestid.show")}
          </button>
        )}
        {canReveal && doc?.has_image && (
          <button
            type="button"
            className={secondary}
            onClick={() => (photo ? setPhoto(null) : void showPhoto())}
            title={t("guestid.logged")}
          >
            {t(photo ? "guestid.hide" : "guestid.showPhoto")}
          </button>
        )}
        {canEdit && (
          <button type="button" className={secondary} onClick={() => onCapture(guest)}>
            {t(doc ? "guestid.replace" : "guestid.add")}
          </button>
        )}
        {canEdit && !guest.is_main && (
          <button type="button" className={secondary} onClick={() => onRemove(guest)}>
            {t("guestid.remove")}
          </button>
        )}
      </div>
      {canReveal && (doc?.masked_number || doc?.has_image) && (
        <p className="text-xs text-muted-foreground">
          {t("guestid.logged")} {(number || photo) && t("guestid.autoHidden")}
        </p>
      )}
    </li>
  );
}
