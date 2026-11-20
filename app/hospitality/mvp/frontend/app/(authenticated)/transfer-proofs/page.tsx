"use client";

/**
 * Transfer proofs — the review queue for "bukti transfer" screenshots.
 * Reachable at `/transfer-proofs`. Re-fetches on a timer, so a guest's upload shows
 * up without a reload.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { LanguageSwitch } from "@/components/LanguageSwitch";
import { ProofList } from "@/components/proofs/ProofList";
import { ProofReviewDialog } from "@/components/proofs/ProofReviewDialog";
import { ProofUploadDialog } from "@/components/proofs/ProofUploadDialog";
import { useLocale } from "@/lib/locale-store";
import { maxProofMb } from "@/lib/proof-format";
import {
  fetchProofs,
  type Proof,
  type ProofFilter,
  type ProofPage,
} from "@/lib/transfer-proofs-api";
import { usePolling } from "@/lib/use-polling";
import { fetchOnboardingStatus, fetchWorkspace, type Workspace } from "@/lib/workspace-api";

const ONBOARDING_PATH = "/onboarding";
const DEFAULT_POLL_SECONDS = 5;
const FILTERS: ProofFilter[] = ["awaiting", "approved", "rejected"];

const errorText = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));
const numberSetting = (value: unknown, fallback: number) =>
  typeof value === "number" && value > 0 ? value : fallback;

export default function TransferProofsPage() {
  const router = useRouter();
  const { t } = useLocale();
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [filter, setFilter] = useState<ProofFilter>("awaiting");
  const [proofs, setProofs] = useState<Proof[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [pollFailed, setPollFailed] = useState(false);
  const [open, setOpen] = useState<Proof | null>(null);
  const [uploading, setUploading] = useState(false);
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

  const changeFilter = (next: ProofFilter) => {
    if (next === filter) return;
    filterRef.current = next; // results still in flight for the old tab are dropped
    pagesShown.current = 1;
    setReady(false);
    setListError(null);
    setProofs([]);
    setNextCursor(null);
    setFilter(next);
  };

  /** Re-read every page shown so far, so a row that changed state is never left stale. */
  const refresh = useCallback(async () => {
    const request = ++listRequest.current;
    const rows: Proof[] = [];
    let cursor: string | null = null;
    for (let page = 0; page < pagesShown.current; page += 1) {
      const result: ProofPage = await fetchProofs(filter, cursor);
      rows.push(...result.items);
      cursor = result.next_cursor;
      if (cursor === null) break;
    }
    if (request !== listRequest.current || filterRef.current !== filter) return;
    setProofs(rows);
    setNextCursor(cursor);
    setReady(true);
    setPollFailed(false);
  }, [filter]);

  usePolling(
    refresh,
    numberSetting(workspace?.settings.inbox_poll_seconds, DEFAULT_POLL_SECONDS) * 1000,
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

  const refreshQuietly = () => void refresh().catch(() => setPollFailed(true));

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

  const timeZone = workspace.property.timezone;
  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">{t("proofs.title")}</h1>
        <div className="flex flex-wrap items-center gap-3">
          <LanguageSwitch />
          <button
            type="button"
            onClick={() => setUploading(true)}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            {t("proofs.record")}
          </button>
        </div>
      </div>

      <div role="tablist" className="flex flex-wrap gap-1">
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
            {t(`proofs.filter.${option}`)}
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
        {ready && proofs.length === 0 && (
          <p className="p-4 text-sm text-muted-foreground">{t(`proofs.empty.${filter}`)}</p>
        )}
        {ready && proofs.length > 0 && (
          <ProofList proofs={proofs} onOpen={setOpen} timeZone={timeZone} />
        )}
        {nextCursor && (
          <button
            type="button"
            onClick={() => void loadOlder()}
            className="w-full border-t border-border px-4 py-3 text-sm font-medium hover:bg-accent"
          >
            {t("proofs.loadMore")}
          </button>
        )}
      </section>

      <ProofReviewDialog
        proof={open}
        isOwner={workspace.is_owner}
        timeZone={timeZone}
        onClose={() => setOpen(null)}
        onDecided={(updated) => {
          // A first approval keeps the proof open for the second person; anything else is final.
          setOpen(updated.state === "awaiting_second" ? updated : null);
          refreshQuietly();
        }}
      />
      <ProofUploadDialog
        open={uploading}
        maxMb={maxProofMb(workspace.settings)}
        onClose={() => setUploading(false)}
        onUploaded={() => {
          setUploading(false);
          refreshQuietly();
        }}
      />
    </div>
  );
}
