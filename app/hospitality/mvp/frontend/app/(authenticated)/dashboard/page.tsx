"use client";

/**
 * Workspace home — the operator's property, plan and this month's usage.
 * Reachable at `/dashboard`. An account without a workspace is sent to
 * `/onboarding`. Auth is handled by the `(authenticated)` layout.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { BookingsCard } from "@/components/bookings/BookingsCard";
import { LanguageSwitch } from "@/components/LanguageSwitch";
import { LinkQuotaNotice } from "@/components/payments/LinkQuotaNotice";
import { RoomsCard } from "@/components/rooms/RoomsCard";
import { ApiError } from "@/lib/api-client";
import { todayIn } from "@/lib/calendar-grid";
import { useLocale } from "@/lib/locale-store";
import { fetchOnboardingStatus, fetchWorkspace, type Workspace } from "@/lib/workspace-api";

const ONBOARDING_PATH = "/onboarding";
const NO_WORKSPACE_STATUS = 403;

const cardClass = "rounded-xl border border-border bg-card p-5 text-card-foreground shadow-sm";

export default function DashboardPage() {
  const router = useRouter();
  const { t } = useLocale();
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      // Ask first, so a brand-new account is redirected without a failed request.
      const status = await fetchOnboardingStatus();
      if (!status.has_workspace) {
        router.replace(ONBOARDING_PATH);
        return;
      }
      setWorkspace(await fetchWorkspace());
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === NO_WORKSPACE_STATUS) {
        router.replace(ONBOARDING_PATH);
        return;
      }
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  }, [router]);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) {
    return (
      <div role="alert" className="mx-auto max-w-xl space-y-3 p-8">
        <p className="text-sm text-destructive">{t("common.loadFailed", { reason: error })}</p>
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90"
        >
          {t("common.retry")}
        </button>
      </div>
    );
  }

  if (!workspace) {
    return <p className="p-8 text-sm text-muted-foreground">{t("common.loading")}</p>;
  }

  const { property, plan, usage, staff, is_owner: isOwner } = workspace;
  const usageText =
    usage.payment_links_limit === null
      ? t("dashboard.linksUnlimited", { used: usage.payment_links_used })
      : t("dashboard.linksUsed", {
          used: usage.payment_links_used,
          limit: usage.payment_links_limit,
        });

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">
            {t("dashboard.welcome", { name: staff.display_name })}
          </h1>
          <p className="text-sm text-muted-foreground">
            {isOwner ? t("dashboard.owner") : t("dashboard.staff")}
          </p>
        </div>
        <LanguageSwitch />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <section className={cardClass} aria-labelledby="property-heading">
          <h2 id="property-heading" className="text-sm font-medium text-muted-foreground">
            {t("dashboard.property")}
          </h2>
          <p className="mt-1 text-lg font-semibold">{property.name}</p>
          <p className="text-sm text-muted-foreground">
            {t(`propertyType.${property.property_type}`)}
            {property.city ? ` · ${property.city}` : ""}
          </p>
        </section>

        <section className={cardClass} aria-labelledby="plan-heading">
          <h2 id="plan-heading" className="text-sm font-medium text-muted-foreground">
            {t("dashboard.plan")}
          </h2>
          <p className="mt-1 text-lg font-semibold">
            {t("dashboard.planName", { plan: plan.name })}
          </p>
          <div className="mt-2">
            <LinkQuotaNotice usage={usage} />
          </div>
        </section>

        <section className={cardClass} aria-labelledby="inbox-heading">
          <h2 id="inbox-heading" className="text-sm font-medium text-muted-foreground">
            {t("dashboard.inbox")}
          </h2>
          <p className="mt-1 text-sm">
            {workspace.unread_conversations > 0
              ? t("dashboard.unread", { count: workspace.unread_conversations })
              : t("dashboard.inboxEmpty")}
          </p>
          <Link
            href="/inbox"
            className="mt-2 inline-block text-sm font-medium text-primary hover:underline"
          >
            {t("dashboard.openInbox")}
          </Link>
        </section>

        <section className={cardClass} aria-labelledby="links-heading">
          <h2 id="links-heading" className="text-sm font-medium text-muted-foreground">
            {t("dashboard.paymentLinks")}
          </h2>
          <p className="mt-1 text-sm">
            {usage.payment_links_used > 0 ? usageText : t("dashboard.paymentLinksEmpty")}
          </p>
          <Link
            href="/payment-links"
            className="mt-2 inline-block text-sm font-medium text-primary hover:underline"
          >
            {t("dashboard.openLinks")}
          </Link>
        </section>

        <section className={cardClass} aria-labelledby="proofs-heading">
          <h2 id="proofs-heading" className="text-sm font-medium text-muted-foreground">
            {t("dashboard.proofs")}
          </h2>
          <p className="mt-1 text-sm">
            {workspace.proofs_awaiting_review > 0
              ? t("dashboard.proofsAwaiting", { count: workspace.proofs_awaiting_review })
              : t("dashboard.proofsNone")}
          </p>
          <Link
            href="/transfer-proofs"
            className="mt-2 inline-block text-sm font-medium text-primary hover:underline"
          >
            {t("dashboard.openProofs")}
          </Link>
        </section>

        <BookingsCard className={cardClass} today={todayIn(property.timezone)} />

        <RoomsCard className={cardClass} />
      </div>
    </div>
  );
}
