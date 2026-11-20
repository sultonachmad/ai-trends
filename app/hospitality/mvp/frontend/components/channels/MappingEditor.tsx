"use client";

import { useEffect, useState } from "react";

import { inputClass } from "@/components/rooms/RoomTypeDialog";
import {
  channelPairs,
  isUnchanged,
  mappingsOf,
  ownPairs,
  selectionOf,
  tighterRooms,
  usedTwice,
  type Selection,
} from "@/lib/channel-mapping";
import {
  refreshChannelProducts,
  saveMappings,
  type ConnectionDetail,
} from "@/lib/channels-api";
import { useLocale } from "@/lib/locale-store";
import type { RatePlan } from "@/lib/rate-plans-api";
import type { RoomType } from "@/lib/rooms-api";

interface MappingEditorProps {
  connection: ConnectionDetail;
  rooms: RoomType[];
  plans: RatePlan[];
  onSaved: (connection: ConnectionDetail) => void;
  /** The channel's rooms were fetched again: the page should re-read the connection. */
  onRefreshed: () => void;
}

const errorText = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));

/** Each of our room and rate pairs with a choice of the channel's room and rate. */
export function MappingEditor({ connection, rooms, plans, onSaved, onRefreshed }: MappingEditorProps) {
  const { t } = useLocale();
  const [selection, setSelection] = useState<Selection>(() => selectionOf(connection.mappings));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // What the server holds replaces the edits whenever it changes (after a save or refresh).
  useEffect(() => {
    setSelection(selectionOf(connection.mappings));
  }, [connection.mappings]);

  const ours = ownPairs(rooms, plans);
  const theirs = channelPairs(connection.products);
  const twice = usedTwice(selection);
  const tighter = tighterRooms(ours, theirs, selection);
  const unchanged = isUnchanged(selection, selectionOf(connection.mappings), ours);

  const run = async (work: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      await work();
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy(false);
    }
  };

  const save = () => {
    if (twice.length > 0) return setError(t("channels.matching.twice"));
    void run(async () => {
      onSaved(await saveMappings(connection.id, mappingsOf(ours, selection)));
      setSaved(true);
    });
  };

  const refresh = () =>
    run(async () => {
      await refreshChannelProducts(connection.id);
      onRefreshed();
    });

  if (ours.length === 0) {
    return <p className="p-4 text-sm text-muted-foreground">{t("channels.matching.noOwn")}</p>;
  }
  if (theirs.length === 0) {
    return <p className="p-4 text-sm text-muted-foreground">{t("channels.matching.needTest")}</p>;
  }

  const health = connection.health;
  const warnings = [
    health.unmatched_pairs > 0 && t("channels.warn.unmatchedOurs", { count: health.unmatched_pairs }),
    health.unmatched_channel_rates > 0 &&
      t("channels.warn.unmatchedTheirs", { count: health.unmatched_channel_rates }),
    tighter.length > 0 &&
      t("channels.warn.smaller", {
        rooms: [...new Set(tighter.map((pair) => pair.roomName))].join(", "),
      }),
    health.switched_off.length > 0 &&
      t("channels.warn.switchedOff", { count: health.switched_off.length }),
    health.missing_on_channel.length > 0 &&
      t("channels.warn.missing", { count: health.missing_on_channel.length }),
  ].filter((warning): warning is string => Boolean(warning));

  return (
    <div className="space-y-3 p-4">
      <p className="text-sm text-muted-foreground">{t("channels.matching.intro")}</p>
      <ul className="space-y-2">
        {ours.map((pair) => {
          const chosen = selection[pair.key] ?? "";
          const clash = chosen !== "" && twice.includes(chosen);
          const id = `match-${pair.key}`;
          return (
            <li key={pair.key} className="grid gap-1 sm:grid-cols-2 sm:items-center sm:gap-3">
              <label htmlFor={id} className="text-sm">
                <span className="font-medium">{pair.roomName}</span>
                <span className="text-muted-foreground"> · {pair.planName}</span>
              </label>
              <select
                id={id}
                value={chosen}
                aria-invalid={clash}
                onChange={(event) => {
                  setSaved(false);
                  setSelection((current) => ({ ...current, [pair.key]: event.target.value }));
                }}
                className={`${inputClass} ${clash ? "border-destructive ring-1 ring-destructive" : ""}`}
              >
                <option value="">{t("channels.matching.notSold")}</option>
                {theirs.map((option) => (
                  <option key={option.key} value={option.key}>
                    {option.label}
                  </option>
                ))}
              </select>
            </li>
          );
        })}
      </ul>
      {warnings.length > 0 && (
        <ul className="list-disc space-y-1 rounded-lg bg-muted py-2 pl-7 pr-3 text-sm">
          {warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      {saved && (
        <p role="status" className="text-sm font-medium">
          {t("channels.matching.saved")}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy || unchanged}
          onClick={save}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {t("channels.matching.save")}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void refresh()}
          className="rounded-md border border-border px-4 py-2 text-sm hover:bg-accent disabled:opacity-50"
        >
          {t("channels.matching.refresh")}
        </button>
      </div>
    </div>
  );
}
