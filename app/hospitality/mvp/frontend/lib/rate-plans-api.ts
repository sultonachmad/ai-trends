/**
 * Rate plan calls (backend: app/routers/rate_plans.py).
 */

import { request } from "@/lib/api-client";

export type MealPlan = "room_only" | "breakfast";

export interface RoomPrice {
  room_type_id: string;
  /** Whole rupiah, as the server sends it ("750000.00"). */
  amount: string;
}

export interface RatePlan {
  id: string;
  name: string;
  meal_plan: MealPlan;
  non_refundable: boolean;
  /** Free cancellation until this many days before arrival; null when non-refundable. */
  free_cancellation_days: number | null;
  is_active: boolean;
  prices: RoomPrice[];
}

export interface RatePlanInput {
  name: string;
  meal_plan: MealPlan;
  non_refundable: boolean;
  free_cancellation_days?: number;
  prices: { room_type_id: string; amount: number }[];
}

const base = "/api/rate-plans";
const json = (method: string, body: unknown) => ({ method, body: JSON.stringify(body) });

export const fetchRatePlans = () => request<RatePlan[]>(base);
export const createRatePlan = (input: RatePlanInput) =>
  request<RatePlan>(base, json("POST", input));
export const updateRatePlan = (id: string, changes: Partial<RatePlanInput & { is_active: boolean }>) =>
  request<RatePlan>(`${base}/${id}`, json("PATCH", changes));
