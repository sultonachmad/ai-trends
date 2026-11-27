"use client";

import { useEffect, useState } from "react";

import { shortDate } from "@/lib/booking-format";
import { useLocale } from "@/lib/locale-store";
import { fetchRepairPhoto, type MaintBoard, type MaintRequest } from "@/lib/maintenance-api";
import { isLive, nextSteps } from "@/lib/maintenance-format";
import { formatRupiah } from "@/lib/money";

export type RepairAction = "start" | "wait" | "fix" | "cancel" | "offSale" | "onSale";

const button = "min-h-11 rounded-md border border-border px-3 py-1 text-sm hover:bg-accent disabled:opacity-50";
const badge = "inline-block rounded-full px-2 py-0.5 text-xs font-medium";

function statusClass(status: string): string {
  if (status === "completed") return "bg-primary/15 text-primary";
  if (status === "cancelled") return "bg-muted";
  if (status === "waiting_parts") return "bg-accent text-accent-foreground";
  return "bg-destructive/15 text-destructive";
}

/** One repair: where, what, who has it, off sale, and what can be done next. */
export function RepairCard({
  request,
  board,
  canWork,
  canManage,
  busy,
  onAction,
  onAssign,
}: {
  request: MaintRequest;
  board: MaintBoard;
  canWork: boolean;
  canManage: boolean;
  busy: boolean;
  onAction: (action: RepairAction, request: MaintRequest) => void;
  onAssign: (request: MaintRequest, staffId: string | null, vendor: string | null) => void;
}) {
  const { t, locale } = useLocale();
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [vendor, setVendor] = useState(request.vendor_name ?? "");
  useEffect(() => () => (photoUrl ? URL.revokeObjectURL(photoUrl) : undefined), [photoUrl]);

  const free = request.assigned_staff_id === null && request.vendor_name === null;
  const mayWork = canWork && isLive(request) && (request.mine || free || canManage);
  const togglePhoto = async () => {
    if (photoUrl) {
      setPhotoUrl(null);
      return;
    }
    setPhotoUrl(URL.createObjectURL(await fetchRepairPhoto(request.id)));
  };
  return (
    <li className="space-y-2 rounded-lg border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-lg font-bold">{request.room_name ?? request.place}</p>
          <p className="text-sm text-muted-foreground">
            {request.number} · {t(`repair.category.${request.category}`)}
          </p>
        </div>
        <span className="flex flex-col items-end gap-1">
          {request.urgent && isLive(request) && (
            <span className={`${badge} bg-destructive text-white`}>{t("repair.urgent")}</span>
          )}
          <span className={`${badge} ${statusClass(request.status)}`}>{t(`repair.status.${request.status}`)}</span>
        </span>
      </div>
      <p className="text-sm">{request.description}</p>
      <p className="text-xs text-muted-foreground">
        {request.reported_by_name && t("repair.reportedBy", { name: request.reported_by_name })}
        {request.from_housekeeping && ` · ${t("repair.fromCleaning")}`}
        {" · "}
        {request.assigned_name
          ? t("repair.givenTo", { name: request.assigned_name })
          : request.vendor_name
            ? t("repair.givenTo", { name: request.vendor_name })
            : t("repair.nobody")}
      </p>
      {request.status_note && <p className="text-sm">{t("repair.note", { text: request.status_note })}</p>}
      {request.cost && <p className="text-sm">{t("repair.costShown", { amount: formatRupiah(request.cost) })}</p>}
      {request.off_sale && (
        <p className="text-sm font-medium text-destructive">
          {t("repair.offSale.shown", {
            from: shortDate(request.off_sale.first_night, locale),
            to: shortDate(request.off_sale.last_night, locale),
          })}
        </p>
      )}
      {photoUrl && (
        // eslint-disable-next-line @next/next/no-img-element -- a private image fetched with the session
        <img src={photoUrl} alt={request.description} className="max-h-64 rounded-md" />
      )}
      <div className="flex flex-wrap gap-2">
        {request.has_photo && (
          <button type="button" onClick={() => void togglePhoto()} className={button}>
            {t(photoUrl ? "repair.hidePhoto" : "repair.showPhoto")}
          </button>
        )}
        {mayWork &&
          nextSteps(request).map((step) => (
            <button
              key={step}
              type="button"
              disabled={busy}
              onClick={() => onAction(step, request)}
              className={step === "fix" ? `${button} border-primary bg-primary text-primary-foreground` : button}
            >
              {t(`repair.step.${step}`)}
            </button>
          ))}
        {canManage && isLive(request) && request.unit_id && (
          <button type="button" disabled={busy} onClick={() => onAction("offSale", request)} className={button}>
            {t(request.off_sale ? "repair.offSale.change" : "repair.offSale.button")}
          </button>
        )}
        {canManage && request.off_sale && (
          <button type="button" disabled={busy} onClick={() => onAction("onSale", request)} className={button}>
            {t("repair.onSale")}
          </button>
        )}
        {canManage && isLive(request) && (
          <button type="button" disabled={busy} onClick={() => onAction("cancel", request)} className={`${button} text-destructive`}>
            {t("repair.cancel")}
          </button>
        )}
      </div>
      {canManage && isLive(request) && (
        <div className="flex flex-wrap items-end gap-2 border-t border-border pt-2 text-sm">
          <label className="space-y-1">
            <span className="block">{t("repair.giveTo")}</span>
            <select
              value={request.assigned_staff_id ?? ""}
              disabled={busy}
              onChange={(e) => onAssign(request, e.target.value || null, null)}
              className="min-h-11 rounded-md border border-border bg-background px-2"
            >
              <option value="">{t("repair.nobody")}</option>
              {board.staff.map((member) => (
                <option key={member.id} value={member.id}>{member.name}</option>
              ))}
            </select>
          </label>
          <label className="space-y-1">
            <span className="block">{t("repair.vendor")}</span>
            <input
              value={vendor}
              maxLength={80}
              onChange={(e) => setVendor(e.target.value)}
              className="min-h-11 rounded-md border border-border bg-background px-2"
            />
          </label>
          <button
            type="button"
            disabled={busy || !vendor.trim()}
            onClick={() => onAssign(request, null, vendor.trim())}
            className={button}
          >
            {t("repair.save")}
          </button>
        </div>
      )}
    </li>
  );
}
