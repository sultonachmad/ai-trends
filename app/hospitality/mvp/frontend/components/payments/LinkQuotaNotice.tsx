"use client";

import { useLocale } from "@/lib/locale-store";
import {
  quotaPercent,
  quotaState,
  quotaTextKey,
  resetDateLabel,
  type LinkUsage,
  type QuotaState,
} from "@/lib/link-quota";

interface LinkQuotaNoticeProps {
  usage: LinkUsage;
  /** Without the bar: for tight places such as a dialog. */
  compact?: boolean;
}

const TEXT_CLASS: Record<QuotaState, string> = {
  unlimited: "text-muted-foreground",
  ok: "text-muted-foreground",
  warning: "font-medium text-foreground",
  reached: "font-medium text-destructive",
  notInPlan: "font-medium text-destructive",
};

const BAR_CLASS: Record<QuotaState, string> = {
  unlimited: "bg-primary",
  ok: "bg-primary",
  warning: "bg-accent-foreground",
  reached: "bg-destructive",
  notInPlan: "bg-destructive",
};

/** One line on this month's payment links against the plan limit, with a small bar. */
export function LinkQuotaNotice({ usage, compact = false }: LinkQuotaNoticeProps) {
  const { t, locale } = useLocale();
  const state = quotaState(usage);
  const percent = quotaPercent(usage);
  const text = t(quotaTextKey(state), {
    used: usage.payment_links_used,
    limit: usage.payment_links_limit ?? 0,
    date: resetDateLabel(usage.payment_links_resets_on, locale),
  });

  return (
    <div className="space-y-1.5">
      <p role="status" className={`text-sm ${TEXT_CLASS[state]}`}>
        {text}
      </p>
      {!compact && percent !== null && (
        <div
          role="progressbar"
          aria-label={t("quota.meter")}
          aria-valuemin={0}
          aria-valuemax={usage.payment_links_limit ?? 0}
          aria-valuenow={Math.min(usage.payment_links_used, usage.payment_links_limit ?? 0)}
          className="h-1.5 w-full max-w-xs overflow-hidden rounded-full bg-muted"
        >
          <div className={`h-full rounded-full ${BAR_CLASS[state]}`} style={{ width: `${percent}%` }} />
        </div>
      )}
    </div>
  );
}
