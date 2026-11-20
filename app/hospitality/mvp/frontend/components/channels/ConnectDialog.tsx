"use client";

import { useEffect, useState, type FormEvent } from "react";

import { Dialog } from "@/components/Dialog";
import { inputClass } from "@/components/rooms/RoomTypeDialog";
import {
  createConnection,
  createTestListing,
  fetchTestListings,
  type CatalogChannel,
  type ConnectionDetail,
  type TestListing,
} from "@/lib/channels-api";
import { useLocale } from "@/lib/locale-store";

const SIMULATOR = "simulator";
const ID_PATTERN = /^[A-Za-z0-9._-]{1,64}$/;
const errorText = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));

interface ConnectDialogProps {
  /** The channel to connect; null closes the dialog. */
  channel: CatalogChannel | null;
  onClose: () => void;
  onStarted: (connection: ConnectionDetail) => void;
}

/** First step of connecting: the property's ID on the channel. The rest happens on its page. */
export function ConnectDialog({ channel, onClose, onStarted }: ConnectDialogProps) {
  const { t } = useLocale();
  const [propertyId, setPropertyId] = useState("");
  const [listings, setListings] = useState<TestListing[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const simulated = channel?.code === SIMULATOR;

  useEffect(() => {
    setPropertyId("");
    setError(null);
    setListings([]);
    if (!simulated) return;
    let cancelled = false;
    fetchTestListings()
      .then((found) => {
        if (!cancelled) setListings(found);
      })
      .catch(() => {
        if (!cancelled) setListings([]); // the ID can still be typed by hand
      });
    return () => {
      cancelled = true;
    };
  }, [channel?.code, simulated]);

  const run = async (work: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await work();
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy(false);
    }
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!channel) return;
    const id = propertyId.trim();
    if (!ID_PATTERN.test(id)) return setError(t("channels.connectDialog.badId"));
    void run(async () => onStarted(await createConnection(channel.code, id)));
  };

  const addListing = () =>
    run(async () => {
      const listing = await createTestListing();
      setListings((current) => [listing, ...current]);
      setPropertyId(listing.hotel_id);
    });

  const close = () => {
    if (!busy) onClose();
  };

  return (
    <Dialog
      open={channel !== null}
      onClose={close}
      title={t("channels.connectDialog.title", { channel: channel?.name ?? "" })}
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {simulated && (
          <section className="space-y-2 rounded-lg bg-muted p-3 text-sm">
            <h3 className="font-semibold">{t("channels.testPanel.title")}</h3>
            <p>{t("channels.testPanel.intro")}</p>
            <button
              type="button"
              disabled={busy}
              onClick={() => void addListing()}
              className="rounded-md border border-border bg-card px-3 py-1.5 text-sm hover:bg-accent disabled:opacity-50"
            >
              {t("channels.testPanel.create")}
            </button>
            {listings.length > 0 && (
              <ul className="max-h-32 space-y-1 overflow-y-auto">
                {listings.map((listing) => (
                  <li key={listing.hotel_id} className="flex flex-wrap items-center justify-between gap-2">
                    <span>
                      <span className="font-mono font-medium">{listing.hotel_id}</span> ·{" "}
                      {t("channels.testPanel.rooms", { count: listing.rooms.length })}
                    </span>
                    <button
                      type="button"
                      onClick={() => setPropertyId(listing.hotel_id)}
                      className="text-sm font-medium text-primary hover:underline"
                    >
                      {t("channels.testPanel.use")}
                      <span className="sr-only">: {listing.hotel_id}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}
        <div>
          <label htmlFor="connect-id" className="mb-1 block text-sm font-medium">
            {t("channels.connectDialog.id")}
          </label>
          <input
            id="connect-id"
            value={propertyId}
            maxLength={64}
            autoComplete="off"
            onChange={(event) => setPropertyId(event.target.value)}
            aria-describedby="connect-id-hint"
            className={`${inputClass} font-mono`}
          />
          <p id="connect-id-hint" className="mt-1 text-xs text-muted-foreground">
            {t("channels.connectDialog.idHint")}
          </p>
        </div>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={close}
            disabled={busy}
            className="rounded-md bg-secondary px-4 py-2 text-sm text-secondary-foreground disabled:opacity-50"
          >
            {t("rooms.form.cancel")}
          </button>
          <button
            type="submit"
            disabled={busy}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {t("channels.connectDialog.start")}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
