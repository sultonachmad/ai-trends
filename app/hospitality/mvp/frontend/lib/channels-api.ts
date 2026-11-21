/**
 * Sales channel calls (backend: app/routers/channels.py, channel_simulator.py).
 */

import { request } from "@/lib/api-client";

export type ConnectionStatus = "draft" | "testing" | "live" | "paused" | "error" | "disconnected";
export type ConnectionAction = "test" | "go-live" | "pause" | "resume" | "disconnect";
export type CollectModel = "property" | "channel";

export interface ChannelUsage {
  used: number;
  /** null = unlimited */
  limit: number | null;
  limit_reached: boolean;
}

export interface CatalogChannel {
  code: string;
  name: string;
  kind: string;
  features: string[];
  state: "connectable" | "coming_soon";
  /** This property already has a connection to it. */
  connected: boolean;
}

export interface ChannelsOverview {
  usage: ChannelUsage;
  channels: CatalogChannel[];
}

export interface MappingPair {
  room_type_id: string;
  rate_plan_id: string;
  external_room_id: string;
  external_rate_id: string;
}

export interface ChannelRoom {
  id: string;
  name: string;
  max_guests: number;
  rates: { id: string; name: string }[];
}

export interface ChannelProducts {
  property_name: string;
  rooms: ChannelRoom[];
}

export interface Connection {
  id: string;
  channel_code: string;
  channel_name: string;
  external_property_id: string;
  channel_property_name: string | null;
  status: ConnectionStatus;
  /** Why the last test failed, as a short code. */
  problem: string | null;
  commission_percent: string;
  price_adjustment_percent: string;
  payment_collect: string;
  mapped_pairs: number;
  last_tested_at: string | null;
  created_at: string;
}

export interface MappingHealth {
  unmatched_pairs: number;
  unmatched_channel_rates: number;
  smaller_capacity: MappingPair[];
  switched_off: MappingPair[];
  missing_on_channel: MappingPair[];
}

export interface PushHealth {
  pending_updates: number;
  oldest_pending_at: string | null;
  failing_since: string | null;
  next_push_at: string | null;
  at_risk: boolean;
  last_success_at: string | null;
}

export interface MessageLogEntry {
  message_type: string;
  status: string;
  attempts: number;
  date_from: string | null;
  date_to: string | null;
  error: string | null;
  next_attempt_at: string | null;
  sent_at: string | null;
  created_at: string;
}

export interface ConnectionDetail extends Connection {
  mappings: MappingPair[];
  /** The channel's rooms and rates as last fetched. */
  products: ChannelProducts | null;
  health: MappingHealth;
  push_health: PushHealth;
  messages: MessageLogEntry[];
  history: { event: string; actor: string | null; at: string; details: Record<string, unknown> }[];
}

export interface DriftEntry {
  room: string;
  date: string;
  kind: "missing_on_channel" | "differs";
  channel: Record<string, unknown> | null;
  ours: Record<string, unknown> | null;
}

export interface ConnectionSettings {
  commission_percent?: number;
  price_adjustment_percent?: number;
  payment_collect?: CollectModel;
}

export interface TestListing {
  hotel_id: string;
  name: string;
  rooms: ChannelRoom[];
  created_at: string;
}

const base = "/api/channel-connections";
const json = (method: string, body: unknown) => ({ method, body: JSON.stringify(body) });

export const fetchChannels = () => request<ChannelsOverview>("/api/channels");
export const fetchConnections = () => request<Connection[]>(base);
export const fetchConnection = (id: string) => request<ConnectionDetail>(`${base}/${id}`);
export const createConnection = (channelCode: string, externalPropertyId: string) =>
  request<ConnectionDetail>(
    base,
    json("POST", { channel_code: channelCode, external_property_id: externalPropertyId }),
  );
export const actOnConnection = (id: string, action: ConnectionAction) =>
  request<ConnectionDetail>(`${base}/${id}/${action}`, { method: "POST" });
export const saveConnectionSettings = (id: string, settings: ConnectionSettings) =>
  request<ConnectionDetail>(`${base}/${id}`, json("PATCH", settings));
export const refreshChannelProducts = (id: string) =>
  request<ChannelProducts>(`${base}/${id}/products`);
export const saveMappings = (id: string, mappings: MappingPair[]) =>
  request<ConnectionDetail>(`${base}/${id}/mappings`, json("PUT", { mappings }));
export const syncConnection = (id: string, range?: { from: string; to: string }) =>
  request<ConnectionDetail>(
    `${base}/${id}/sync`,
    json("POST", range ? { date_from: range.from, date_to: range.to } : {}),
  );
export const fetchDrift = (id: string) =>
  request<{ differences: DriftEntry[] }>(`${base}/${id}/drift`);

const listings = "/api/simulator/channels/listings";
export const fetchTestListings = () => request<TestListing[]>(listings);
export const createTestListing = () => request<TestListing>(listings, { method: "POST" });
