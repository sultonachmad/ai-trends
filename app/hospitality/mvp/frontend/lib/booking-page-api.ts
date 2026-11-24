/**
 * Direct booking page calls (backend: app/routers/booking_page.py). The `/api/book` and
 * `/api/guest-booking` routes are public: the page name or private token is the key.
 */

import { request } from "@/lib/api-client";

export interface BookingPagePlan {
  id: string;
  name: string;
  sold: boolean;
}

export interface BookingPageSetup {
  slug: string | null;
  is_published: boolean;
  plans: BookingPagePlan[];
}

export interface PublicPage {
  property_name: string;
  city: string | null;
  check_in_time: string;
  check_out_time: string;
  today: string;
  last_arrival: string;
  max_nights: number;
  deposit_percent: number;
  hold_minutes: number;
  whatsapp_phone: string | null;
  rooms: { id: string; name: string }[];
}

export interface PublicDay {
  date: string;
  available: boolean;
  lowest_price: string | null;
  min_stay: number | null;
}

export interface RateOption {
  rate_plan_id: string;
  name: string;
  total: string;
  deposit: string;
  non_refundable: boolean;
  free_cancellation_days: number | null;
}

export interface RoomResult {
  id: string;
  name: string;
  max_guests: number;
  options: RateOption[];
}

export interface Availability {
  nights: number;
  rooms: RoomResult[];
  unavailable_reason: "sold_out" | "closed" | "min_stay" | "too_many_guests" | null;
  min_stay: number | null;
}

export interface StayQuery {
  arrival: string;
  departure: string;
  adults: number;
  children: number;
}

export interface CheckoutOrder extends StayQuery {
  idempotency_key: string;
  room_type_id: string;
  rate_plan_id: string;
  guest_name: string;
  guest_phone: string;
  pay_choice: "deposit" | "full";
  expected_total: string;
  accepted_terms: boolean;
  language: "id" | "en";
}

export interface CheckoutResult {
  number: string;
  pay_url: string;
  booking_path: string;
  amount_due: string;
  total: string;
  hold_expires_at: string;
}

export interface GuestBooking {
  property_name: string;
  property_whatsapp: string | null;
  number: string;
  status: "awaiting_payment" | "confirmed" | "cancelled" | "in_house" | "checked_out" | "no_show";
  arrival: string;
  departure: string;
  nights: number;
  room_name: string;
  plan_name: string;
  adults: number;
  children: number;
  guest_name: string;
  phone_hint: string | null;
  total: string;
  paid: string;
  balance: string;
  non_refundable: boolean;
  free_cancellation_days: number | null;
  hold_expires_at: string | null;
  pay_url: string | null;
  can_cancel: boolean;
  refund_if_cancelled: boolean;
  refund_due: boolean;
  language: string | null;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  body: JSON.stringify(body),
});
const page = (slug: string) => `/api/book/${encodeURIComponent(slug)}`;
const guest = (token: string) => `/api/guest-booking/${encodeURIComponent(token)}`;

export const fetchBookingPageSetup = () => request<BookingPageSetup>("/api/booking-page");
export const saveBookingPageSetup = (body: {
  slug: string;
  is_published: boolean;
  sold_plan_ids: string[];
}) => request<BookingPageSetup>("/api/booking-page", json("PUT", body));

export const fetchPublicPage = (slug: string) => request<PublicPage>(page(slug));
export const fetchPublicCalendar = (slug: string, from: string, to: string) =>
  request<{ days: PublicDay[] }>(
    `${page(slug)}/calendar?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
  );
export const fetchAvailability = (slug: string, stay: StayQuery) => {
  const query = new URLSearchParams({
    arrival: stay.arrival,
    departure: stay.departure,
    adults: String(stay.adults),
    children: String(stay.children),
  });
  return request<Availability>(`${page(slug)}/availability?${query.toString()}`);
};
export const submitCheckout = (slug: string, order: CheckoutOrder) =>
  request<CheckoutResult>(`${page(slug)}/checkout`, json("POST", order));

export const fetchGuestBooking = (token: string) => request<GuestBooking>(guest(token));
export const cancelGuestBooking = (token: string, acceptNoRefund: boolean) =>
  request<GuestBooking>(`${guest(token)}/cancel`, json("POST", { accept_no_refund: acceptNoRefund }));
