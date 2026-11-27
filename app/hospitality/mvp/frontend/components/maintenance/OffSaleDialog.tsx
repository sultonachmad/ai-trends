"use client";

import { useEffect, useState } from "react";

import { Dialog } from "@/components/Dialog";
import { useLocale } from "@/lib/locale-store";
import type { MaintRequest } from "@/lib/maintenance-api";
import { addDays, nightsProblem } from "@/lib/maintenance-format";

const field = "min-h-12 w-full rounded-md border border-border bg-background px-3 py-2 text-base";

/** Choose the nights the request's room cannot be sold (today and tomorrow by default). */
export function OffSaleDialog({
  request,
  today,
  busy,
  onClose,
  onSave,
}: {
  request: MaintRequest | null;
  today: string;
  busy: boolean;
  onClose: () => void;
  onSave: (first: string, last: string) => void;
}) {
  const { t } = useLocale();
  const [first, setFirst] = useState(today);
  const [last, setLast] = useState(addDays(today, 1));
  useEffect(() => {
    setFirst(request?.off_sale?.first_night && request.off_sale.first_night >= today ? request.off_sale.first_night : today);
    setLast(request?.off_sale?.last_night ?? addDays(today, 1));
  }, [request, today]);
  if (!request) return null;
  const problem = nightsProblem(first, last, today);
  return (
    <Dialog open onClose={onClose} title={t("repair.offSale.title", { room: request.room_name ?? "" })}>
      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          if (!problem) onSave(first, last);
        }}
      >
        <p className="text-sm text-muted-foreground">{t("repair.offSale.help")}</p>
        <div className="grid grid-cols-2 gap-3">
          <label className="space-y-1 text-sm">
            <span>{t("repair.offSale.first")}</span>
            <input type="date" min={today} value={first} onChange={(e) => setFirst(e.target.value)} className={field} />
          </label>
          <label className="space-y-1 text-sm">
            <span>{t("repair.offSale.last")}</span>
            <input type="date" min={first} value={last} onChange={(e) => setLast(e.target.value)} className={field} />
          </label>
        </div>
        {problem && <p className="text-sm text-destructive">{t(problem)}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="min-h-12 rounded-md border border-border px-4">
            {t("hk.cancel")}
          </button>
          <button
            type="submit"
            disabled={Boolean(problem) || busy}
            className="min-h-12 rounded-md bg-destructive px-4 font-medium text-white disabled:opacity-50"
          >
            {t("repair.offSale.save")}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
