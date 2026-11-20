"use client";

/**
 * Inbox — the property's guest conversations (WhatsApp, simulated for now).
 * Reachable at `/inbox`; the open conversation is kept in the URL as `?c=<id>`.
 * The list and the open thread re-fetch on a timer while the tab is visible.
 */

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { ConversationList } from "@/components/inbox/ConversationList";
import { MessageThread } from "@/components/inbox/MessageThread";
import { ReplyBox } from "@/components/inbox/ReplyBox";
import { SimulatorPanel } from "@/components/inbox/SimulatorPanel";
import { LanguageSwitch } from "@/components/LanguageSwitch";
import { amountLimits, CreateLinkDialog } from "@/components/payments/CreateLinkDialog";
import { LinkCreatedNotice } from "@/components/payments/LinkCreatedNotice";
import { ProofUploadDialog } from "@/components/proofs/ProofUploadDialog";
import { ApiError } from "@/lib/api-client";
import {
  fetchConversation,
  fetchConversations,
  fetchMessages,
  markRead,
  reopenConversation,
  resolveConversation,
  sendReply,
  type Conversation,
  type ConversationFilter,
  type Message,
} from "@/lib/inbox-api";
import {
  applyFirstPage,
  mergeConversations,
  mergeMessages,
  sameConversation,
} from "@/lib/inbox-format";
import { useLocale } from "@/lib/locale-store";
import type { CreatedLink } from "@/lib/payment-links-api";
import { usePolling } from "@/lib/use-polling";
import { maxProofMb } from "@/lib/proof-format";
import { fetchOnboardingStatus, fetchWorkspace, type Workspace } from "@/lib/workspace-api";

const ONBOARDING_PATH = "/onboarding";
const INBOX_PATH = "/inbox";
const DEFAULT_LIST_POLL_SECONDS = 5;
const DEFAULT_THREAD_POLL_SECONDS = 3;
const CONFLICT_STATUS = 409;
const FILTERS: ConversationFilter[] = ["open", "resolved"];

const errorText = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));
const seconds = (value: unknown, fallback: number) =>
  (typeof value === "number" && value > 0 ? value : fallback) * 1000;

function InboxScreen() {
  const router = useRouter();
  const selectedId = useSearchParams().get("c");
  const { t } = useLocale();

  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [filter, setFilter] = useState<ConversationFilter>("open");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [listReady, setListReady] = useState(false);
  const [selected, setSelected] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [pollFailed, setPollFailed] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [linkDialogOpen, setLinkDialogOpen] = useState(false);
  const [proofDialogOpen, setProofDialogOpen] = useState(false);
  const [createdLink, setCreatedLink] = useState<CreatedLink | null>(null);
  const lastMessageId = useRef<string | null>(null);
  const olderLoaded = useRef(false);
  // What the screen is showing *now*; async results for anything else are dropped.
  const selectedIdRef = useRef(selectedId);
  const filterRef = useRef(filter);
  const listRequest = useRef(0);

  useEffect(() => {
    selectedIdRef.current = selectedId;
  }, [selectedId]);

  useEffect(() => {
    filterRef.current = filter;
  }, [filter]);

  useEffect(() => {
    lastMessageId.current = messages.length > 0 ? messages[messages.length - 1].id : null;
  }, [messages]);

  const showConversation = useCallback((fresh: Conversation) => {
    setSelected((current) => (current && sameConversation(current, fresh) ? current : fresh));
  }, []);

  // Keep the list row of the open conversation in step with it (e.g. unread cleared).
  useEffect(() => {
    if (!selected) return;
    setConversations((current) =>
      current.some((c) => c.id === selected.id && c !== selected)
        ? current.map((c) => (c.id === selected.id ? selected : c))
        : current,
    );
  }, [selected]);

  // Workspace (timezone, polling intervals, simulator switch); no workspace -> onboarding.
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

  const select = useCallback(
    (id: string | null) => {
      router.replace(id ? `${INBOX_PATH}?c=${id}` : INBOX_PATH, { scroll: false });
    },
    [router],
  );

  const changeFilter = (next: ConversationFilter) => {
    if (next === filter) return;
    olderLoaded.current = false;
    filterRef.current = next; // results still in flight for the old tab are dropped
    setListReady(false);
    setListError(null);
    setConversations([]);
    setNextCursor(null);
    setFilter(next);
  };

  // ---- conversation list -------------------------------------------------
  const refreshList = useCallback(async () => {
    const request = ++listRequest.current;
    const page = await fetchConversations(filter);
    if (request !== listRequest.current || filterRef.current !== filter) return;
    setConversations((current) => applyFirstPage(current, page.items, page.next_cursor !== null));
    if (!olderLoaded.current) setNextCursor(page.next_cursor);
    setListReady(true);
    setPollFailed(false);
  }, [filter]);

  usePolling(
    refreshList,
    seconds(workspace?.settings.inbox_poll_seconds, DEFAULT_LIST_POLL_SECONDS),
    workspace !== null,
    () => setPollFailed(true),
    filter, // switching tab fetches at once instead of waiting for the next tick
  );

  const loadOlder = async () => {
    if (!nextCursor) return;
    const requestedFilter = filter;
    setListError(null);
    try {
      const page = await fetchConversations(requestedFilter, nextCursor);
      if (filterRef.current !== requestedFilter) return;
      olderLoaded.current = true;
      setConversations((current) => mergeConversations(current, page.items));
      setNextCursor(page.next_cursor);
    } catch (cause) {
      if (filterRef.current === requestedFilter) setListError(errorText(cause));
    }
  };

  // ---- open thread ---------------------------------------------------------
  useEffect(() => {
    setMessages([]);
    setSelected(null);
    setActionError(null);
    if (!selectedId || !workspace) return;
    let cancelled = false;
    (async () => {
      let conversation: Conversation;
      try {
        const [loaded, thread] = await Promise.all([
          fetchConversation(selectedId),
          fetchMessages(selectedId),
        ]);
        if (cancelled) return;
        conversation = loaded;
        setMessages(thread);
        setSelected(loaded);
      } catch (cause) {
        if (!cancelled) setActionError(errorText(cause));
        return;
      }
      if (conversation.unread_count === 0) return;
      try {
        const read = await markRead(selectedId);
        if (!cancelled) setSelected(read);
      } catch {
        // Best effort: the thread is on screen; the next refresh retries.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedId, workspace]);

  // The link count follows the server: re-read it after a link is made or refused.
  const refreshUsage = () => {
    void fetchWorkspace()
      .then(setWorkspace)
      .catch(() => setPollFailed(true));
  };

  const refreshThread = useCallback(async () => {
    const id = selectedId;
    if (!id) return;
    const [fresh, conversation] = await Promise.all([
      fetchMessages(id, lastMessageId.current),
      fetchConversation(id),
    ]);
    if (selectedIdRef.current !== id) return;
    if (fresh.length > 0) setMessages((current) => mergeMessages(current, fresh));
    showConversation(conversation);
    if (conversation.unread_count === 0) return;
    const read = await markRead(id);
    if (selectedIdRef.current === id) showConversation(read);
  }, [selectedId, showConversation]);

  usePolling(
    refreshThread,
    seconds(workspace?.settings.thread_poll_seconds, DEFAULT_THREAD_POLL_SECONDS),
    workspace !== null && selectedId !== null && selected !== null,
    () => setPollFailed(true),
    selectedId,
  );

  const reply = async (body: string) => {
    const id = selectedId;
    if (!id) return;
    try {
      const sent = await sendReply(id, body);
      if (selectedIdRef.current === id) setMessages((current) => mergeMessages(current, [sent]));
    } catch (cause) {
      // Refused (e.g. the reply window closed, or a colleague resolved it): show the
      // conversation as it is now, so the reply box explains why.
      if (cause instanceof ApiError && cause.status === CONFLICT_STATUS) {
        const current = await fetchConversation(id).catch(() => null);
        if (current && selectedIdRef.current === id) showConversation(current);
      }
      throw cause;
    }
    // The reply is sent and recorded. Updating the list is best effort: a failure
    // here must not look like a failed send (a retry would message the guest twice).
    void refreshList().catch(() => setPollFailed(true));
  };

  const toggleResolved = async () => {
    if (!selected) return;
    const id = selected.id;
    setActionError(null);
    try {
      const updated =
        selected.status === "resolved"
          ? await reopenConversation(id)
          : await resolveConversation(id);
      if (selectedIdRef.current === id) setSelected(updated);
    } catch (cause) {
      if (selectedIdRef.current === id) setActionError(errorText(cause));
      return;
    }
    void refreshList().catch(() => setPollFailed(true));
  };

  // ---- render ----------------------------------------------------------------
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
  const listPane = (
    <section
      aria-label={t("inbox.title")}
      className={`flex-col rounded-xl border border-border bg-card text-card-foreground md:flex md:w-80 md:shrink-0 ${
        selectedId ? "hidden" : "flex"
      }`}
    >
      <div role="tablist" className="flex gap-1 border-b border-border p-2">
        {FILTERS.map((option) => (
          <button
            key={option}
            type="button"
            role="tab"
            aria-selected={filter === option}
            onClick={() => changeFilter(option)}
            className={`rounded-md px-3 py-1 text-sm font-medium ${
              filter === option ? "bg-primary text-primary-foreground" : "hover:bg-accent"
            }`}
          >
            {t(`inbox.${option}`)}
          </button>
        ))}
      </div>
      <div className="max-h-[65vh] overflow-y-auto">
        {listReady ? (
          <ConversationList
            conversations={conversations}
            selectedId={selectedId}
            onSelect={select}
            emptyText={t(filter === "open" ? "inbox.emptyOpen" : "inbox.emptyResolved")}
            timeZone={timeZone}
          />
        ) : (
          <p className="p-4 text-sm text-muted-foreground">{t("common.loading")}</p>
        )}
        {listError && (
          <p role="alert" className="p-4 text-sm text-destructive">
            {t("inbox.actionFailed", { reason: listError })}
          </p>
        )}
        {nextCursor && (
          <button
            type="button"
            onClick={() => void loadOlder()}
            className="w-full border-t border-border px-4 py-3 text-sm font-medium hover:bg-accent"
          >
            {t("inbox.loadMore")}
          </button>
        )}
      </div>
    </section>
  );

  const threadPane = (
    <section
      className={`min-w-0 flex-1 flex-col rounded-xl border border-border bg-card text-card-foreground md:flex ${
        selectedId ? "flex" : "hidden"
      }`}
    >
      {!selectedId && (
        <p className="p-8 text-sm text-muted-foreground">{t("inbox.pickConversation")}</p>
      )}
      {selectedId && !selected && !actionError && (
        <p className="p-8 text-sm text-muted-foreground">{t("common.loading")}</p>
      )}
      {selectedId && selected && (
        <>
          <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border p-3">
            <div className="min-w-0">
              <button
                type="button"
                onClick={() => select(null)}
                className="mb-1 text-xs font-medium text-muted-foreground hover:underline md:hidden"
              >
                ← {t("inbox.back")}
              </button>
              <h2 className="truncate text-base font-semibold">{selected.guest.name}</h2>
              <p className="text-xs text-muted-foreground">{selected.guest.phone}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setLinkDialogOpen(true)}
                className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
              >
                {t("inbox.sendLink")}
              </button>
              <button
                type="button"
                onClick={() => setProofDialogOpen(true)}
                className="rounded-md border border-border px-3 py-1.5 text-sm font-medium hover:bg-accent"
              >
                {t("inbox.recordProof")}
              </button>
              <button
                type="button"
                onClick={() => router.push(`/bookings?from=${encodeURIComponent(selectedId)}`)}
                className="rounded-md border border-border px-3 py-1.5 text-sm font-medium hover:bg-accent"
              >
                {t("inbox.createBooking")}
              </button>
              <button
                type="button"
                onClick={() => void toggleResolved()}
                className="rounded-md border border-border px-3 py-1.5 text-sm font-medium hover:bg-accent"
              >
                {selected.status === "resolved" ? t("inbox.reopen") : t("inbox.resolve")}
              </button>
            </div>
          </header>
          <div className="h-[50vh] overflow-y-auto">
            <MessageThread messages={messages} timeZone={timeZone} />
          </div>
          <ReplyBox blockedReason={selected.reply_blocked_reason} onSend={reply} />
        </>
      )}
      {actionError && (
        <p role="alert" className="p-3 text-sm text-destructive">
          {t("inbox.actionFailed", { reason: actionError })}
        </p>
      )}
    </section>
  );

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">{t("inbox.title")}</h1>
        <LanguageSwitch />
      </div>
      {pollFailed && (
        <p role="status" className="text-sm text-muted-foreground">
          {t("inbox.updateFailed")}
        </p>
      )}
      <div className="flex flex-col gap-4 md:flex-row">
        {listPane}
        {threadPane}
      </div>
      <CreateLinkDialog
        open={linkDialogOpen && selectedId !== null}
        onClose={() => setLinkDialogOpen(false)}
        conversationId={selectedId ?? undefined}
        limits={amountLimits(workspace.settings)}
        quota={workspace.usage}
        onLimitReached={refreshUsage}
        onCreated={(result) => {
          setLinkDialogOpen(false);
          setCreatedLink(result);
          refreshUsage();
          // The link message shows up in the thread on the next refresh.
          void refreshThread().catch(() => setPollFailed(true));
          void refreshList().catch(() => setPollFailed(true));
        }}
      />
      <LinkCreatedNotice created={createdLink} onClose={() => setCreatedLink(null)} />
      <ProofUploadDialog
        open={proofDialogOpen && selectedId !== null}
        conversationId={selectedId ?? undefined}
        maxMb={maxProofMb(workspace.settings)}
        onClose={() => setProofDialogOpen(false)}
        onUploaded={() => {
          setProofDialogOpen(false);
          router.push("/transfer-proofs");
        }}
      />
      {workspace.simulator_enabled && (
        <SimulatorPanel
          onSent={(conversationId) => {
            void refreshList();
            if (!selectedId) select(conversationId);
          }}
        />
      )}
    </div>
  );
}

export default function InboxPage() {
  return (
    <Suspense fallback={null}>
      <InboxScreen />
    </Suspense>
  );
}
