"use client";

import { importErrorKey, linkBadgeClass, linkState } from "@/lib/calendar-link-format";
import type { CalendarLink } from "@/lib/calendar-links-api";
import { formatListTime } from "@/lib/inbox-format";
import { useLocale } from "@/lib/locale-store";

const badge = "inline-block rounded-full px-2 py-0.5 text-xs font-medium";
const action = "rounded-md border border-border px-3 py-1 text-sm hover:bg-accent disabled:opacity-50";

interface CalendarLinkRowProps {
  link: CalendarLink;
  canEdit: boolean;
  busy: boolean;
  onSync: () => void;
  onStopImport: () => void;
  onEdit: () => void;
  onReplace: () => void;
  onRemove: () => void;
}

/** One calendar link: its state and what can be done with it. */
export function CalendarLinkRow({
  link,
  canEdit,
  busy,
  onSync,
  onStopImport,
  onEdit,
  onReplace,
  onRemove,
}: CalendarLinkRowProps) {
  const { t, locale } = useLocale();
  const state = linkState(link);
  const imported = link.imports;
  const named = <span className="sr-only">: {link.label}</span>;
  return (
    <li className="space-y-2 px-4 py-3 text-sm">
      <p className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{link.label}</span>
        <span className="text-muted-foreground">{link.room_type_name}</span>
        <span className={`${badge} ${linkBadgeClass(state)}`}>
          {t(`calendarLinks.state.${state}`)}
        </span>
      </p>
      {imported && (
        <p className="break-all text-muted-foreground">
          {imported.url_hint} · {t("calendarLinks.busyDates", { count: imported.busy_dates })}
          {imported.last_synced_at
            ? ` · ${t("calendarLinks.lastSync", {
                when: formatListTime(imported.last_synced_at, locale, new Date()),
              })}`
            : ""}
        </p>
      )}
      {imported?.last_error && (
        <p role="status" className="text-destructive">
          {t(importErrorKey(imported.last_error))} {t("calendarLinks.blocksKept")}
        </p>
      )}
      {link.conflict_dates.length > 0 && (
        <p role="status" className="text-destructive">
          {t("calendarLinks.conflict", { dates: link.conflict_dates.join(", ") })}
        </p>
      )}
      {canEdit && (
        <div className="flex flex-wrap gap-2">
          {imported && (
            <button type="button" disabled={busy} onClick={onSync} className={action}>
              {t("calendarLinks.syncNow")}
              {named}
            </button>
          )}
          {imported && (
            <button type="button" disabled={busy} onClick={onStopImport} className={action}>
              {t("calendarLinks.stopImport")}
              {named}
            </button>
          )}
          <button type="button" disabled={busy} onClick={onEdit} className={action}>
            {t("calendarLinks.edit")}
            {named}
          </button>
          <button type="button" disabled={busy} onClick={onReplace} className={action}>
            {t("calendarLinks.replace")}
            {named}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={onRemove}
            className={`${action} text-destructive`}
          >
            {t("calendarLinks.remove")}
            {named}
          </button>
        </div>
      )}
    </li>
  );
}
