/**
 * Calls for onboarding and the workspace summary (backend: app/routers/onboarding.py,
 * app/routers/workspace.py). All go through the shared `request` helper, which sends
 * the session cookie and turns non-2xx answers into `ApiError`.
 */

import { request } from "@/lib/api-client";

export interface Workspace {
  tenant: { id: string; code: string; name: string };
  property: {
    id: string;
    code: string;
    name: string;
    property_type: string;
    city: string | null;
    timezone: string;
    currency: string;
  };
  plan: { code: string; name: string };
  usage: { payment_links_used: number; payment_links_limit: number | null };
  is_owner: boolean;
  staff: { display_name: string; email: string | null };
  settings: Record<string, string | number>;
  unread_conversations: number;
  simulator_enabled: boolean;
}

export interface OnboardingInput {
  property_name: string;
  property_type: string;
  city: string;
}

export function fetchOnboardingStatus(): Promise<{ has_workspace: boolean }> {
  return request("/api/onboarding/status");
}

export function createWorkspace(input: OnboardingInput): Promise<Workspace> {
  return request("/api/onboarding", { method: "POST", body: JSON.stringify(input) });
}

export function fetchWorkspace(): Promise<Workspace> {
  return request("/api/workspace");
}
