/**
 * Inbox calls (backend: app/routers/inbox.py, app/routers/simulator.py).
 */

import { request } from "@/lib/api-client";

export type ConversationFilter = "open" | "resolved";
export type ReplyBlockedReason = "resolved" | "window_closed";

export interface Conversation {
  id: string;
  status: string;
  guest: { id: string | null; name: string; phone: string | null };
  unread_count: number;
  last_message_at: string | null;
  last_message: { preview: string; direction: string; created_at: string } | null;
  can_reply: boolean;
  reply_blocked_reason: ReplyBlockedReason | null;
  service_window_expires_at: string | null;
}

export interface ConversationPage {
  items: Conversation[];
  next_cursor: string | null;
}

export interface Message {
  id: string;
  conversation_id: string;
  direction: "inbound" | "outbound" | "internal_note";
  sender_kind: string;
  sender_name: string | null;
  body: string | null;
  status: string;
  error: string | null;
  created_at: string;
}

export interface SimulatedInbound {
  from_phone: string;
  guest_name?: string;
  body: string;
}

const base = "/api/conversations";
const post = <T,>(path: string, body?: unknown): Promise<T> =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export function fetchConversations(
  filter: ConversationFilter,
  cursor?: string | null,
): Promise<ConversationPage> {
  const params = new URLSearchParams({ status: filter });
  if (cursor) params.set("cursor", cursor);
  return request(`${base}?${params.toString()}`);
}

export function fetchConversation(id: string): Promise<Conversation> {
  return request(`${base}/${id}`);
}

export function fetchMessages(id: string, afterId?: string | null): Promise<Message[]> {
  const query = afterId ? `?after=${encodeURIComponent(afterId)}` : "";
  return request(`${base}/${id}/messages${query}`);
}

export const sendReply = (id: string, body: string) =>
  post<Message>(`${base}/${id}/messages`, { body });
export const markRead = (id: string) => post<Conversation>(`${base}/${id}/read`);
export const resolveConversation = (id: string) => post<Conversation>(`${base}/${id}/resolve`);
export const reopenConversation = (id: string) => post<Conversation>(`${base}/${id}/reopen`);
export const simulateInbound = (input: SimulatedInbound) =>
  post<{ conversation_id: string; message_id: string }>("/api/simulator/whatsapp/inbound", input);
