/**
 * Pure helpers for showing channel connections: status labels, what can be done next,
 * and which setup step a connection is at.
 */

import type { Connection, ConnectionAction, ConnectionStatus } from "@/lib/channels-api";

/** i18n key of a status label. */
export function statusKey(status: ConnectionStatus): string {
  return `channels.status.${status}`;
}

/** Tailwind classes for a status badge (semantic theme colours only). */
export function statusBadgeClass(status: ConnectionStatus): string {
  if (status === "live") return "bg-primary text-primary-foreground";
  if (status === "error") return "bg-destructive/15 text-destructive";
  if (status === "paused" || status === "testing") return "bg-accent text-accent-foreground";
  return "bg-muted text-muted-foreground ring-1 ring-border";
}

/** i18n key for the reason a test failed; unknown codes get a general sentence. */
export function problemKey(problem: string): string {
  return problem === "unknown_property" || problem === "channel_unavailable"
    ? `channels.problem.${problem}`
    : "channels.problem.other";
}

/** i18n key for a history entry ("channel.connection.went_live" → "channels.event.went_live"). */
export function eventKey(event: string): string {
  return `channels.event.${event.split(".").pop() ?? event}`;
}

/** The setup steps, in order. */
export const SETUP_STEPS = ["test", "match", "settings", "live"] as const;
export type SetupStep = (typeof SETUP_STEPS)[number];

/** The step a connection that is still being set up should do next; null once it is in use. */
export function nextStep(connection: Pick<Connection, "status" | "mapped_pairs">): SetupStep | null {
  if (connection.status === "draft" || connection.status === "error") return "test";
  if (connection.status !== "testing") return null;
  return connection.mapped_pairs === 0 ? "match" : "live";
}

/** Whether matching can be edited (the channel's rooms are known and it is not ended). */
export function canMatch(status: ConnectionStatus): boolean {
  return status === "testing" || status === "live" || status === "paused";
}

/** The status changes offered for a connection, most useful first. */
export function actionsFor(
  connection: Pick<Connection, "status" | "mapped_pairs">,
): ConnectionAction[] {
  switch (connection.status) {
    case "draft":
    case "error":
      return ["test", "disconnect"];
    case "testing":
      return connection.mapped_pairs > 0
        ? ["go-live", "test", "disconnect"]
        : ["test", "disconnect"];
    case "live":
      return ["pause", "test", "disconnect"];
    case "paused":
      return ["resume", "test", "disconnect"];
    default:
      return [];
  }
}

/** A typed percentage within [min, max] with at most two decimals, or null. */
export function parsePercent(input: string, min: number, max: number): number | null {
  const text = input.trim().replace(",", ".");
  if (!/^-?\d{1,3}(\.\d{1,2})?$/.test(text)) return null;
  const value = Number(text);
  return value >= min && value <= max ? value : null;
}
