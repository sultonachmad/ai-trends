"use client";

import type { ChannelUsage } from "@/lib/channels-api";
import { useLocale } from "@/lib/locale-store";

/** One line on connected channels against the plan limit. */
export function ChannelQuotaNotice({ usage }: { usage: ChannelUsage }) {
  const { t } = useLocale();
  const values = { used: usage.used, limit: usage.limit ?? 0 };
  let text = t("channels.usage", values);
  if (usage.limit === null) text = t("channels.usageUnlimited", values);
  else if (usage.limit === 0) text = t("channels.notInPlan");
  else if (usage.limit_reached) text = t("channels.usageReached", values);
  return (
    <p
      role="status"
      className={`text-sm ${usage.limit_reached ? "font-medium text-foreground" : "text-muted-foreground"}`}
    >
      {text}
    </p>
  );
}
