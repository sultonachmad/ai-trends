/** Guests on a booking and their KTP or passport (backend: app/routers/guest_ids.py). */

import { request, requestBlob } from "@/lib/api-client";

export const DOC_TYPES = ["ktp", "passport"] as const;
export type DocType = (typeof DOC_TYPES)[number];
export const VISA_TYPES = ["visa_free", "voa", "b211a", "kitas", "kitap", "other"] as const;
export type VisaType = (typeof VISA_TYPES)[number];
export const GENDERS = ["male", "female"] as const;
export type Gender = (typeof GENDERS)[number];

export interface IdDocument {
  id: string;
  doc_type: string;
  /** Only the last digits, e.g. "••••0001"; null once the number was deleted. */
  masked_number: string | null;
  issuing_country: string | null;
  expires_on: string | null;
  visa_type: string | null;
  entry_date: string | null;
  confirmed_at: string | null;
  confirmed_by: string | null;
  has_image: boolean;
  usable: boolean;
}

export interface GuestOnBooking {
  guest_id: string;
  full_name: string;
  is_main: boolean;
  nationality: string | null;
  birth_date: string | null;
  gender: string | null;
  document: IdDocument | null;
}

export interface ReaderInfo {
  name: string;
  simulated: boolean;
}

export interface BookingGuests {
  booking_id: string;
  status: string;
  main_guest_ready: boolean;
  can_change: boolean;
  reader: ReaderInfo;
  guests: GuestOnBooking[];
}

export interface ReadFields {
  number: string | null;
  full_name: string | null;
  birth_date: string | null;
  gender: string | null;
  nationality: string | null;
  expires_on: string | null;
  visa_type: string | null;
  entry_date: string | null;
}

export interface ScanResult {
  scan_id: string;
  reader: ReaderInfo;
  fields: ReadFields;
}

export interface ConfirmIdInput {
  guest_id: string | null;
  doc_type: DocType;
  number: string;
  full_name: string;
  birth_date: string | null;
  gender: Gender | null;
  nationality: string | null;
  expires_on: string | null;
  visa_type: VisaType | null;
  entry_date: string | null;
  scan_id: string | null;
  checked: true;
}

export interface IdView {
  event: "confirmed" | "number_viewed" | "image_viewed";
  at: string;
  by: string;
  guest_id: string | null;
  document_id: string | null;
}

const base = (bookingId: string) => `/api/bookings/${bookingId}/guests`;
const json = (method: string, body: unknown) => ({ method, body: JSON.stringify(body) });

export const fetchGuests = (bookingId: string) => request<BookingGuests>(base(bookingId));

export function scanId(bookingId: string, docType: DocType, file: File) {
  const body = new FormData();
  body.append("file", file);
  body.append("doc_type", docType);
  return request<ScanResult>(`${base(bookingId)}/scan`, { method: "POST", body });
}

export const confirmId = (bookingId: string, input: ConfirmIdInput) =>
  request<BookingGuests>(base(bookingId), json("POST", input));

export const removeGuest = (bookingId: string, guestId: string) =>
  request<void>(`${base(bookingId)}/${guestId}`, { method: "DELETE" });

export const revealNumber = (bookingId: string, documentId: string) =>
  request<{ number: string }>(`${base(bookingId)}/documents/${documentId}/reveal`, {
    method: "POST",
  });

export const fetchIdImage = (bookingId: string, documentId: string) =>
  requestBlob(`${base(bookingId)}/documents/${documentId}/image`);

export const fetchIdHistory = (bookingId: string) =>
  request<IdView[]>(`${base(bookingId)}/history`);
