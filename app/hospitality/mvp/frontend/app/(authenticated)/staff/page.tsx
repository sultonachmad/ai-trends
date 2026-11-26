"use client";

/** Staff — who can sign in to this property, join links, roles and removal. */

import { useCallback, useEffect, useState } from "react";

import { InviteForm } from "@/components/staff/InviteForm";
import { TeamList } from "@/components/staff/TeamList";
import { LanguageSwitch } from "@/components/LanguageSwitch";
import { ApiError } from "@/lib/api-client";
import { staffErrorKey } from "@/lib/housekeeping-format";
import { useLocale } from "@/lib/locale-store";
import { useCan } from "@/lib/rbac-store";
import { changeRole, fetchTeam, removeMember, revokeInvite, type Team } from "@/lib/staff-api";

const FORBIDDEN = 403;

export default function StaffPage() {
  const { t } = useLocale();
  const canEdit = useCan("staff:edit");
  const [team, setTeam] = useState<Team | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [noAccess, setNoAccess] = useState(false);

  const load = useCallback(async () => {
    try {
      setTeam(await fetchTeam());
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === FORBIDDEN) setNoAccess(true);
      else setError(t("staff.loadError"));
    }
  }, [t]);
  useEffect(() => {
    void load();
  }, [load]);

  const run = async (call: () => Promise<Team>) => {
    setBusy(true);
    setError(null);
    try {
      setTeam(await call());
    } catch (cause) {
      const key = staffErrorKey(cause);
      setError(key ? t(key) : cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  };

  if (noAccess) return <p role="alert" className="p-8 text-sm">{t("frontdesk.noAccess")}</p>;
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{t("staff.title")}</h1>
          <p className="text-sm text-muted-foreground">{t("staff.subtitle")}</p>
        </div>
        <LanguageSwitch />
      </div>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {canEdit && <InviteForm onMade={() => void load()} />}
      {!team ? (
        <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
      ) : (
        <TeamList
          team={team}
          canEdit={canEdit}
          busy={busy}
          onRole={(member, role) => void run(() => changeRole(member.staff_id, role))}
          onRemove={(member) => void run(() => removeMember(member.staff_id))}
          onRevoke={(id) => void run(() => revokeInvite(id))}
        />
      )}
    </div>
  );
}
