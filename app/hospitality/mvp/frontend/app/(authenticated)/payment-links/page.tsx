"use client";

/**
 * Payment links — the property's links with their state; create and cancel.
 * Reachable at `/payment-links`. The list re-fetches on a timer, so a guest's
 * payment shows up without a reload.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { Dialog } from "@/components/Dialog";
import { LanguageSwitch } from "@/components/LanguageSwitch";
import { amountLimits, CreateLinkDialog } from "@/components/payments/CreateLinkDialog";
import { LinkCreatedNotice } from "@/components/payments/LinkCreatedNotice";
import { PaymentLinkTable } from "@/components/payments/PaymentLinkTable";
import { ProofUploadDialog } from "@/components/proofs/ProofUploadDialog";
import { useLocale } from "@/lib/locale-store";
import { formatRupiah } from "@/lib/money";
import { LINK_STATES } from "@/lib/payment-link-format";
import {
  cancelPaymentLink,
  fetchPaymentLinks,
  type CreatedLink,
  type LinkFilter,
  type PaymentLink,
  type PaymentLinkPage,
} from "@/lib/payment-links-api";
import { usePolling } from "@/lib/use-polling";
import { maxProofMb } from "@/lib/proof-format";
import { fetchOnboardingStatus, fetchWorkspace, type Workspace } from "@/lib/workspace-api";

const ONBOARDING_PATH = "/onboarding";
const DEFAULT_POLL_SECONDS = 5;
const FILTERS: LinkFilter[] = ["all", ...LINK_STATES];

const errorText = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));

export default function PaymentLinksPage() {
  const router = useRouter();
  const { t } = useLocale();
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [filter, setFilter] = useState<LinkFilter>("all");
  const [links, setLinks] = useState<PaymentLink[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [pollFailed, setPollFailed] = useState(false);
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<CreatedLink | null>(null);
  const [toCancel, setToCancel] = useState<PaymentLink | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [proofFor, setProofFor] = useState<PaymentLink | null>(null);
  const filterRef = useRef(filter);
  const listRequest = useRef(0);
  const pagesShown = useRef(1);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const status = await fetchOnboardingStatus();
        if (cancelled) return;
        if (!status.has_workspace) {
          router.replace(ONBOARDING_PATH);
          return;
        }
        const loaded = await fetchWorkspace();
        if (!cancelled) setWorkspace(loaded);
      } catch (cause) {
        if (!cancelled) setLoadError(errorText(cause));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  const changeFilter = (next: LinkFilter) => {
    if (next === filter) return;
    filterRef.current = next; // results still in flight for the old filter are dropped
    pagesShown.current = 1;
    setReady(false);
    setListError(null);
    setLinks([]);
    setNextCursor(null);
    setFilter(next);
  };

  /** Re-read every page shown so far, so a row that changed state is never left stale. */
  const refresh = useCallback(async () => {
    const request = ++listRequest.current;
    const rows: PaymentLink[] = [];
    let cursor: string | null = null;
    for (let page = 0; page < pagesShown.current; page += 1) {
      const result: PaymentLinkPage = await fetchPaymentLinks(filter, cursor);
      rows.push(...result.items);
      cursor = result.next_cursor;
      if (cursor === null) break;
    }
    if (request !== listRequest.current || filterRef.current !== filter) return;
    setLinks(rows);
    setNextCursor(cursor);
    setReady(true);
    setPollFailed(false);
  }, [filter]);

  const pollSeconds = workspace?.settings.inbox_poll_seconds;
  usePolling(
    refresh,
    (typeof pollSeconds === "number" && pollSeconds > 0 ? pollSeconds : DEFAULT_POLL_SECONDS) * 1000,
    workspace !== null,
    () => setPollFailed(true),
    filter,
  );

  const loadOlder = async () => {
    if (!nextCursor) return;
    const requested = filter;
    setListError(null);
    pagesShown.current += 1;
    try {
      await refresh();
    } catch (cause) {
      pagesShown.current -= 1;
      if (filterRef.current === requested) setListError(errorText(cause));
    }
  };

  const confirmCancel = async () => {
    if (!toCancel) return;
    setCancelling(true);
    setListError(null);
    try {
      await cancelPaymentLink(toCancel.id);
    } catch (cause) {
      setListError(errorText(cause));
    } finally {
      setCancelling(false);
      setToCancel(null);
    }
    void refresh().catch(() => setPollFailed(true));
  };

  const onCreated = (result: CreatedLink) => {
    setCreating(false);
    setCreated(result);
    void refresh().catch(() => setPollFailed(true));
  };

  if (loadError) {
    return (
      <p role="alert" className="p-8 text-sm text-destructive">
        {t("common.loadFailed", { reason: loadError })}
      </p>
    );
  }
  if (!workspace) {
    return <p className="p-8 text-sm text-muted-foreground">{t("common.loading")}</p>;
  }

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">{t("links.title")}</h1>
        <div className="flex flex-wrap items-center gap-3">
          <LanguageSwitch />
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            {t("links.new")}
          </button>
        </div>
      </div>

      <div role="tablist" aria-label={t("links.filter")} className="flex flex-wrap gap-1">
        {FILTERS.map((option) => (
          <button
            key={option}
            type="button"
            role="tab"
            aria-selected={filter === option}
            onClick={() => changeFilter(option)}
            className={`rounded-md px-3 py-1 text-sm font-medium ${
              filter === option
                ? "bg-primary text-primary-foreground"
                : "border border-border bg-card hover:bg-accent"
            }`}
          >
            {option === "all" ? t("links.filter.all") : t(`links.state.${option}`)}
          </button>
        ))}
      </div>

      {pollFailed && (
        <p role="status" className="text-sm text-muted-foreground">
          {t("inbox.updateFailed")}
        </p>
      )}
      {listError && (
        <p role="alert" className="text-sm text-destructive">
          {t("inbox.actionFailed", { reason: listError })}
        </p>
      )}

      <section className="rounded-xl border border-border bg-card text-card-foreground">
        {!ready && <p className="p-4 text-sm text-muted-foreground">{t("common.loading")}</p>}
        {ready && links.length === 0 && (
          <p className="p-4 text-sm text-muted-foreground">{t("links.empty")}</p>
        )}
        {ready && links.length > 0 && (
          <PaymentLinkTable
            links={links}
            onCancel={setToCancel}
            onAddProof={setProofFor}
            timeZone={workspace.property.timezone}
          />
        )}
        {nextCursor && (
          <button
            type="button"
            onClick={() => void loadOlder()}
            className="w-full border-t border-border px-4 py-3 text-sm font-medium hover:bg-accent"
          >
            {t("links.loadMore")}
          </button>
        )}
      </section>

      <CreateLinkDialog
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={onCreated}
        limits={amountLimits(workspace.settings)}
      />
      <LinkCreatedNotice created={created} onClose={() => setCreated(null)} />
      <ProofUploadDialog
        open={proofFor !== null}
        link={proofFor ?? undefined}
        maxMb={maxProofMb(workspace.settings)}
        onClose={() => setProofFor(null)}
        onUploaded={() => {
          setProofFor(null);
          router.push("/transfer-proofs");
        }}
      />
      <Dialog
        open={toCancel !== null}
        onClose={() => !cancelling && setToCancel(null)}
        title={t("links.cancelTitle")}
      >
        <p className="text-sm">
          {t("links.cancelBody", { amount: toCancel ? formatRupiah(toCancel.amount) : "" })}
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={() => setToCancel(null)}
            disabled={cancelling}
            className="rounded-md bg-secondary px-4 py-2 text-sm text-secondary-foreground disabled:opacity-50"
          >
            {t("links.keep")}
          </button>
          <button
            type="button"
            onClick={() => void confirmCancel()}
            disabled={cancelling}
            className="rounded-md bg-destructive px-4 py-2 text-sm font-medium text-destructive-foreground disabled:opacity-50"
          >
            {t("links.cancelConfirm")}
          </button>
        </div>
      </Dialog>
    </div>
  );
}
