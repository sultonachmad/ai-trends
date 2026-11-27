"use client";

/** Repairs — report from a phone, work the ones given to you, take rooms off sale. */

import { useCallback, useRef, useState } from "react";

import { LanguageSwitch } from "@/components/LanguageSwitch";
import { NoteDialog, type NoteMode } from "@/components/maintenance/NoteDialog";
import { OffSaleDialog } from "@/components/maintenance/OffSaleDialog";
import { RepairCard, type RepairAction } from "@/components/maintenance/RepairCard";
import { ReportForm } from "@/components/maintenance/ReportForm";
import { ApiError } from "@/lib/api-client";
import { useLocale } from "@/lib/locale-store";
import {
  assignRepair,
  cancelRepair,
  fetchMaintenance,
  fixRepair,
  putOnSale,
  reportRepair,
  startRepair,
  takeOffSale,
  waitRepair,
  type MaintBoard,
  type MaintRequest,
} from "@/lib/maintenance-api";
import { mineOrFree, ordered, repairError } from "@/lib/maintenance-format";
import { useCan } from "@/lib/rbac-store";
import { usePolling } from "@/lib/use-polling";

type Tab = "mine" | "all";
const FORBIDDEN = 403;
const POLL_MS = 30_000;

export default function MaintenancePage() {
  const { t } = useLocale();
  const canEdit = useCan("maintenance:edit");
  const canManage = useCan("maintenance:manage");
  const [board, setBoard] = useState<MaintBoard | null>(null);
  const [tab, setTab] = useState<Tab>("mine");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [reporting, setReporting] = useState(false);
  const [note, setNote] = useState<{ mode: NoteMode; request: MaintRequest } | null>(null);
  const [offSale, setOffSale] = useState<MaintRequest | null>(null);
  const [noAccess, setNoAccess] = useState(false);
  const requestId = useRef(0);

  const load = useCallback(async () => {
    const id = ++requestId.current;
    try {
      const found = await fetchMaintenance();
      if (id === requestId.current) setBoard(found);
    } catch (cause) {
      if (id !== requestId.current) return;
      if (cause instanceof ApiError && cause.status === FORBIDDEN) setNoAccess(true);
      else setProblem(t("repair.loadError"));
    }
  }, [t]);
  const dialogOpen = reporting || note !== null || offSale !== null;
  usePolling(load, POLL_MS, !busy && !dialogOpen);

  const run = async (call: () => Promise<MaintBoard>, done?: string) => {
    setBusy(true);
    setNotice(null);
    requestId.current += 1;
    try {
      setBoard(await call());
      setProblem(null);
      if (done) setNotice(done);
      return true;
    } catch (cause) {
      const refusal = repairError(cause);
      setProblem(
        refusal
          ? t(refusal.key, { items: refusal.items.join(", ") })
          : cause instanceof Error
            ? cause.message
            : String(cause),
      );
      return false;
    } finally {
      setBusy(false);
    }
  };

  const onAction = (action: RepairAction, request: MaintRequest) => {
    if (action === "wait" || action === "fix" || action === "cancel") setNote({ mode: action, request });
    else if (action === "offSale") setOffSale(request);
    else if (action === "onSale") void run(() => putOnSale(request.id));
    else void run(() => startRepair(request.id));
  };
  const onNote = (text: string | null, cost: number | null) => {
    if (!note) return;
    const { mode, request } = note;
    setNote(null);
    const calls: Record<NoteMode, () => Promise<MaintBoard>> = {
      wait: () => waitRepair(request.id, text ?? ""),
      fix: () => fixRepair(request.id, text, cost),
      cancel: () => cancelRepair(request.id, text ?? ""),
    };
    void run(calls[mode]);
  };

  if (noAccess) return <p role="alert" className="p-8 text-sm">{t("frontdesk.noAccess")}</p>;
  const list = board ? (tab === "mine" ? mineOrFree(board) : ordered(board.requests)) : [];
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">{t("repair.title")}</h1>
        <div className="flex flex-wrap items-center gap-2">
          {canEdit && board && (
            <button
              type="button"
              onClick={() => setReporting(true)}
              className="min-h-12 rounded-md bg-primary px-4 text-base font-medium text-primary-foreground"
            >
              {t("repair.report")}
            </button>
          )}
          <LanguageSwitch />
        </div>
      </div>
      {problem && (
        <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{problem}</p>
      )}
      {notice && <p role="status" className="text-sm text-primary">{notice}</p>}
      <div role="tablist" aria-label={t("repair.title")} className="flex flex-wrap gap-2">
        {(["mine", "all"] as const).map((name) => (
          <button
            key={name}
            type="button"
            role="tab"
            aria-selected={tab === name}
            onClick={() => setTab(name)}
            className={`min-h-11 rounded-md border px-4 py-2 text-sm ${
              tab === name ? "border-primary bg-primary text-primary-foreground" : "border-border hover:bg-accent"
            }`}
          >
            {t(`repair.tab.${name}`)}
          </button>
        ))}
      </div>
      {!board ? (
        <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
      ) : list.length === 0 ? (
        <p className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">{t("repair.none")}</p>
      ) : (
        <ul className="space-y-3">
          {list.map((request) => (
            <RepairCard
              key={request.id}
              request={request}
              board={board}
              canWork={canEdit}
              canManage={canManage}
              busy={busy}
              onAction={onAction}
              onAssign={(r, staffId, vendor) => void run(() => assignRepair(r.id, staffId, vendor))}
            />
          ))}
        </ul>
      )}
      {board && (
        <>
          <ReportForm
            open={reporting}
            board={board}
            busy={busy}
            onClose={() => setReporting(false)}
            onSend={async (input) => {
              if (await run(() => reportRepair(input), t("repair.sent"))) setReporting(false);
            }}
          />
          <OffSaleDialog
            request={offSale}
            today={board.today}
            busy={busy}
            onClose={() => setOffSale(null)}
            onSave={async (first, last) => {
              const target = offSale;
              if (target && (await run(() => takeOffSale(target.id, first, last)))) setOffSale(null);
            }}
          />
        </>
      )}
      <NoteDialog mode={note?.mode ?? null} busy={busy} onClose={() => setNote(null)} onSend={onNote} />
    </div>
  );
}
