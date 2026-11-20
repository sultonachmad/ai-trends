"use client";

import { useEffect, useState, type FormEvent } from "react";

import { inputClass } from "@/components/rooms/RoomTypeDialog";
import { parsePercent } from "@/lib/channel-format";
import {
  saveConnectionSettings,
  type CollectModel,
  type ConnectionDetail,
} from "@/lib/channels-api";
import { useLocale } from "@/lib/locale-store";

const MAX_COMMISSION = 50;
const MIN_ADJUSTMENT = -50;
const MAX_ADJUSTMENT = 100;
const COLLECTORS: readonly CollectModel[] = ["property", "channel"];
const tidy = (value: string) => String(Number(value));

interface ConnectionSettingsFormProps {
  connection: ConnectionDetail;
  onSaved: (connection: ConnectionDetail) => void;
}

/** Commission, price adjustment and who collects payment for one connection. */
export function ConnectionSettingsForm({ connection, onSaved }: ConnectionSettingsFormProps) {
  const { t } = useLocale();
  const [commission, setCommission] = useState("");
  const [adjustment, setAdjustment] = useState("");
  const [collect, setCollect] = useState<CollectModel>("property");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const readOnly = connection.status === "disconnected";

  useEffect(() => {
    setCommission(tidy(connection.commission_percent));
    setAdjustment(tidy(connection.price_adjustment_percent));
    setCollect(connection.payment_collect === "channel" ? "channel" : "property");
  }, [connection.commission_percent, connection.price_adjustment_percent, connection.payment_collect]);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSaved(false);
    const commissionValue = parsePercent(commission, 0, MAX_COMMISSION);
    if (commissionValue === null) return setError(t("channels.settings.badCommission"));
    const adjustmentValue = parsePercent(adjustment, MIN_ADJUSTMENT, MAX_ADJUSTMENT);
    if (adjustmentValue === null) return setError(t("channels.settings.badAdjustment"));
    setBusy(true);
    setError(null);
    try {
      onSaved(
        await saveConnectionSettings(connection.id, {
          commission_percent: commissionValue,
          price_adjustment_percent: adjustmentValue,
          payment_collect: collect,
        }),
      );
      setSaved(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={onSubmit} className="space-y-4 p-4" noValidate>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="channel-commission" className="mb-1 block text-sm font-medium">
            {t("channels.settings.commission")}
          </label>
          <input
            id="channel-commission"
            inputMode="decimal"
            value={commission}
            disabled={readOnly || busy}
            onChange={(event) => setCommission(event.target.value)}
            aria-describedby="channel-commission-hint"
            className={`${inputClass} max-w-28`}
          />
          <p id="channel-commission-hint" className="mt-1 text-xs text-muted-foreground">
            {t("channels.settings.commissionHint")}
          </p>
        </div>
        <div>
          <label htmlFor="channel-adjustment" className="mb-1 block text-sm font-medium">
            {t("channels.settings.adjustment")}
          </label>
          <input
            id="channel-adjustment"
            inputMode="decimal"
            value={adjustment}
            disabled={readOnly || busy}
            onChange={(event) => setAdjustment(event.target.value)}
            aria-describedby="channel-adjustment-hint"
            className={`${inputClass} max-w-28`}
          />
          <p id="channel-adjustment-hint" className="mt-1 text-xs text-muted-foreground">
            {t("channels.settings.adjustmentHint")}
          </p>
        </div>
      </div>
      <fieldset disabled={readOnly || busy}>
        <legend className="mb-1 text-sm font-medium">{t("channels.settings.collect")}</legend>
        <div className="space-y-1 text-sm">
          {COLLECTORS.map((option) => (
            <label key={option} className="flex items-center gap-2">
              <input
                type="radio"
                name="channel-collect"
                checked={collect === option}
                onChange={() => setCollect(option)}
              />
              {t(`channels.settings.collect.${option}`)}
            </label>
          ))}
        </div>
      </fieldset>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      {saved && (
        <p role="status" className="text-sm font-medium">
          {t("channels.settings.saved")}
        </p>
      )}
      {!readOnly && (
        <button
          type="submit"
          disabled={busy}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {t("channels.settings.save")}
        </button>
      )}
    </form>
  );
}
