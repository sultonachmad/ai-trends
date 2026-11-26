"use client";

import { useEffect, useRef, useState } from "react";

import { Dialog } from "@/components/Dialog";
import { inputClass } from "@/components/rooms/RoomTypeDialog";
import {
  closeDrawer,
  fetchMyDrawer,
  openDrawer,
  recordPaidOut,
  type Drawer,
} from "@/lib/end-of-day-api";
import { checkCount, needsNote, parseCash, problemOf, type Problem } from "@/lib/end-of-day-format";
import { formatClock, formatShortDate } from "@/lib/inbox-format";
import { useLocale } from "@/lib/locale-store";
import { formatRupiah, parseRupiah } from "@/lib/money";

interface CashDrawerDialogProps {
  open: boolean;
  onClose: () => void;
}

const secondary =
  "min-h-11 rounded-md border border-border px-4 py-2 text-sm hover:bg-accent disabled:opacity-50";
const primary =
  "min-h-11 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50";
const REASON_MIN = 3;

function Row({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className={`flex justify-between gap-3 py-1 ${strong ? "font-semibold" : ""}`}>
      <span>{label}</span>
      <span className="tabular-nums">{value}</span>
    </div>
  );
}

function Totals({ drawer }: { drawer: Drawer }) {
  const { t, locale } = useLocale();
  return (
    <div className="text-sm">
      <p className="text-muted-foreground">
        {t("drawer.opened", {
          when: `${formatShortDate(drawer.opened_at, locale)} ${formatClock(drawer.opened_at, locale)}`,
        })}
      </p>
      <Row label={t("drawer.float")} value={formatRupiah(drawer.opening_float)} />
      <Row label={t("drawer.cashIn")} value={formatRupiah(drawer.cash_in)} />
      <Row label={t("drawer.cashOut")} value={`− ${formatRupiah(drawer.cash_out)}`} />
      <Row label={t("drawer.paidOuts")} value={`− ${formatRupiah(drawer.paid_outs)}`} />
      <Row label={t("drawer.expected")} value={formatRupiah(drawer.expected_cash)} strong />
      {drawer.by_method.length > 0 && (
        <div className="mt-2 border-t border-border pt-2">
          <p className="font-medium">{t("drawer.byMethod")}</p>
          {drawer.by_method.map((row) => (
            <p key={row.method} className="flex justify-between gap-3 text-xs">
              <span>{t(`drawer.method.${row.method}`)}</span>
              <span className="tabular-nums">
                {t("drawer.received", { amount: formatRupiah(row.received) })}
                {Number(row.paid_out) > 0 && ` · ${t("drawer.out", { amount: formatRupiah(row.paid_out) })}`}
              </span>
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

/** The signed-in person's cash drawer: open, paid-outs, count and close. */
export function CashDrawerDialog({ open, onClose }: CashDrawerDialogProps) {
  const { t } = useLocale();
  const [drawer, setDrawer] = useState<Drawer | null | undefined>(undefined);
  const [float, setFloat] = useState("");
  const [outAmount, setOutAmount] = useState("");
  const [outReason, setOutReason] = useState("");
  const [counted, setCounted] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const request = useRef(0);

  useEffect(() => {
    if (!open) return;
    setDrawer(undefined);
    setMessage(null);
    setProblem(null);
    setFloat("");
    setOutAmount("");
    setOutReason("");
    setCounted("");
    setNote("");
    const ticket = ++request.current;
    fetchMyDrawer()
      .then((found) => {
        if (ticket === request.current) setDrawer(found.drawer);
      })
      .catch((cause) => {
        if (ticket === request.current) setProblem(problemOf(cause));
      });
  }, [open]);

  const act = async (call: () => Promise<Drawer>, after?: (d: Drawer) => void) => {
    setBusy(true);
    setProblem(null);
    try {
      const changed = await call();
      setDrawer(changed.status === "open" ? changed : null);
      after?.(changed);
    } catch (cause) {
      setProblem(problemOf(cause));
    } finally {
      setBusy(false);
    }
  };

  const startDrawer = () => {
    const amount = parseCash(float || "0");
    if (amount === null) return setProblem({ key: "drawer.badAmount" });
    void act(() => openDrawer(amount), () => setFloat(""));
  };
  const paidOut = () => {
    const amount = parseRupiah(outAmount);
    if (amount === null) return setProblem({ key: "drawer.badAmount" });
    if (outReason.trim().length < REASON_MIN) return setProblem({ key: "drawer.needReason" });
    void act(() => recordPaidOut(amount, outReason.trim()), () => {
      setOutAmount("");
      setOutReason("");
    });
  };
  const count = drawer ? checkCount(counted, drawer.expected_cash) : null;
  const finish = () => {
    if (!count || !count.ok) return setProblem({ key: "drawer.badAmount" });
    if (needsNote(count.difference, note)) return setProblem({ key: "drawer.needNote" });
    void act(() => closeDrawer(count.value, note.trim() || null), (closed) => {
      setMessage(t("drawer.closed", { amount: formatRupiah(closed.variance ?? "0") }));
      setCounted("");
      setNote("");
    });
  };

  return (
    <Dialog open={open} onClose={() => !busy && onClose()} title={t("drawer.title")}>
      <div className="space-y-4 text-sm">
        {message && <p role="status" className="rounded-lg bg-accent px-3 py-2 text-accent-foreground">{message}</p>}
        {drawer === undefined && !problem && <p className="text-muted-foreground">{t("common.loading")}</p>}
        {drawer === null && (
          <div className="space-y-2">
            <p>{t("drawer.none")}</p>
            <label htmlFor="drawer-float" className="block font-medium">{t("drawer.float")}</label>
            <input id="drawer-float" inputMode="numeric" value={float} placeholder="0" onChange={(e) => setFloat(e.target.value)} className={inputClass} />
            <button type="button" disabled={busy} onClick={startDrawer} className={primary}>{t("drawer.open")}</button>
            <p className="text-xs text-muted-foreground">{t("drawer.autoNote")}</p>
          </div>
        )}
        {drawer && (
          <>
            <Totals drawer={drawer} />
            <section aria-labelledby="drawer-paid-out" className="space-y-2 border-t border-border pt-3">
              <h3 id="drawer-paid-out" className="font-semibold">{t("drawer.paidOut.title")}</h3>
              <div className="grid gap-2 sm:grid-cols-2">
                <div>
                  <label htmlFor="drawer-out-amount" className="mb-1 block">{t("drawer.paidOut.amount")}</label>
                  <input id="drawer-out-amount" inputMode="numeric" value={outAmount} onChange={(e) => setOutAmount(e.target.value)} className={inputClass} />
                </div>
                <div>
                  <label htmlFor="drawer-out-reason" className="mb-1 block">{t("drawer.paidOut.reason")}</label>
                  <input id="drawer-out-reason" maxLength={300} value={outReason} onChange={(e) => setOutReason(e.target.value)} className={inputClass} />
                </div>
              </div>
              <button type="button" disabled={busy} onClick={paidOut} className={secondary}>{t("drawer.paidOut.save")}</button>
            </section>
            <section aria-labelledby="drawer-close" className="space-y-2 border-t border-border pt-3">
              <h3 id="drawer-close" className="font-semibold">{t("drawer.close.title")}</h3>
              <label htmlFor="drawer-counted" className="block">{t("drawer.close.counted")}</label>
              <input id="drawer-counted" inputMode="numeric" value={counted} onChange={(e) => setCounted(e.target.value)} className={inputClass} />
              {count?.ok && (
                <p className={count.difference === 0 ? "text-muted-foreground" : "font-medium text-destructive"}>
                  {t("drawer.close.difference", { amount: formatRupiah(count.difference) })}
                </p>
              )}
              {count?.ok && count.difference !== 0 && (
                <>
                  <label htmlFor="drawer-note" className="block">{t("drawer.close.note")}</label>
                  <input id="drawer-note" maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} className={inputClass} />
                </>
              )}
              <button type="button" disabled={busy} onClick={finish} className={primary}>{t("drawer.close.save")}</button>
            </section>
          </>
        )}
        {problem && (
          <p role="alert" className="text-destructive">
            {"key" in problem ? t(problem.key) : problem.text}
          </p>
        )}
        <div className="flex justify-end">
          <button type="button" disabled={busy} onClick={onClose} className={secondary}>{t("frontdesk.back")}</button>
        </div>
      </div>
    </Dialog>
  );
}
