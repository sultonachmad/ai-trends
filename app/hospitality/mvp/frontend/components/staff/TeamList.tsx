"use client";

import { useState } from "react";

import { Dialog } from "@/components/Dialog";
import { shortDate } from "@/lib/booking-format";
import { STAFF_ROLES } from "@/lib/housekeeping-format";
import { useLocale } from "@/lib/locale-store";
import type { Member, StaffRole, Team } from "@/lib/staff-api";

const small = "min-h-11 rounded-md border border-border px-3 py-1 text-sm hover:bg-accent disabled:opacity-50";

/** The team and the join links not used yet. */
export function TeamList({
  team,
  canEdit,
  busy,
  onRole,
  onRemove,
  onRevoke,
}: {
  team: Team;
  canEdit: boolean;
  busy: boolean;
  onRole: (member: Member, role: StaffRole) => void;
  onRemove: (member: Member) => void;
  onRevoke: (inviteId: string) => void;
}) {
  const { t, locale } = useLocale();
  const [removing, setRemoving] = useState<Member | null>(null);
  const others = team.members.filter((member) => !member.is_owner && !member.is_me);
  return (
    <div className="space-y-4">
      <section aria-labelledby="staff-members" className="space-y-2">
        <h2 id="staff-members" className="font-semibold">{t("staff.members")}</h2>
        <ul className="divide-y divide-border rounded-lg border border-border bg-card">
          {team.members.map((member) => {
            const editable = canEdit && !member.is_owner && !member.is_me;
            return (
              <li key={member.staff_id} className="flex flex-wrap items-center justify-between gap-2 p-3">
                <span>
                  <span className="font-medium">{member.name}</span>
                  {member.is_owner && <span className="ml-2 text-xs text-muted-foreground">{t("staff.owner")}</span>}
                  {member.is_me && <span className="ml-2 text-xs text-muted-foreground">{t("staff.you")}</span>}
                  <span className="block text-xs text-muted-foreground">{member.email}</span>
                </span>
                {editable && member.role !== "custom" ? (
                  <span className="flex flex-wrap items-center gap-2">
                    <select
                      aria-label={t("staff.invite.role")}
                      value={member.role}
                      disabled={busy}
                      onChange={(e) => onRole(member, e.target.value as StaffRole)}
                      className="min-h-11 rounded-md border border-border bg-background px-2 text-sm"
                    >
                      {STAFF_ROLES.map((role) => (
                        <option key={role} value={role}>{t(`staff.role.${role}`)}</option>
                      ))}
                    </select>
                    <button type="button" disabled={busy} onClick={() => setRemoving(member)} className={`${small} text-destructive`}>
                      {t("staff.remove")}
                    </button>
                  </span>
                ) : (
                  <span className="text-sm">{t(`staff.role.${member.role}`)}</span>
                )}
              </li>
            );
          })}
        </ul>
        {others.length === 0 && <p className="text-sm text-muted-foreground">{t("staff.none")}</p>}
      </section>
      {team.invites.length > 0 && (
        <section aria-labelledby="staff-pending" className="space-y-2">
          <h2 id="staff-pending" className="font-semibold">{t("staff.pending")}</h2>
          <ul className="divide-y divide-border rounded-lg border border-border bg-card">
            {team.invites.map((invite) => (
              <li key={invite.id} className="flex flex-wrap items-center justify-between gap-2 p-3">
                <span>
                  <span className="font-medium">{invite.name ?? invite.email}</span> · {t(`staff.role.${invite.role}`)}
                  <span className="block text-xs text-muted-foreground">
                    {invite.email} · {t("staff.expires", { date: shortDate(invite.expires_at.slice(0, 10), locale) })}
                  </span>
                </span>
                {canEdit && (
                  <button type="button" disabled={busy} onClick={() => onRevoke(invite.id)} className={small}>
                    {t("staff.revoke")}
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
      <Dialog open={removing !== null} onClose={() => setRemoving(null)} title={t("staff.remove")}>
        <p className="text-sm">{removing && t("staff.removeConfirm", { name: removing.name })}</p>
        <div className="mt-4 flex justify-end gap-2">
          <button type="button" onClick={() => setRemoving(null)} className={small}>{t("hk.cancel")}</button>
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              if (removing) onRemove(removing);
              setRemoving(null);
            }}
            className="min-h-11 rounded-md bg-destructive px-3 py-1 text-sm font-medium text-white"
          >
            {t("staff.remove")}
          </button>
        </div>
      </Dialog>
    </div>
  );
}
