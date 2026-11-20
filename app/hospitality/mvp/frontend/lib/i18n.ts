/**
 * Two-language UI text (Bahasa Indonesia first, English second) — no library.
 *
 * `translate(locale, key, vars)` looks a key up in the chosen language, falls back
 * to English, and finally to the key itself so a missing entry is visible instead
 * of blank. `{name}` placeholders are filled from `vars`.
 */

export const LOCALES = ["id", "en"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "id";

const en = {
  "common.loading": "Loading…",
  "common.retry": "Try again",
  "common.loadFailed": "Could not load this page: {reason}",
  "language.label": "Language",
  "language.id": "Bahasa Indonesia",
  "language.en": "English",
  "onboarding.title": "Set up your property",
  "onboarding.subtitle": "Three answers and your workspace is ready.",
  "onboarding.propertyName": "Property name",
  "onboarding.propertyNamePlaceholder": "e.g. Villa Senja Ubud",
  "onboarding.propertyType": "Property type",
  "onboarding.city": "City or area",
  "onboarding.cityPlaceholder": "e.g. Ubud",
  "onboarding.submit": "Create workspace",
  "onboarding.nameTooShort": "Property name needs at least 2 characters.",
  "onboarding.cityRequired": "Please enter the city or area.",
  "propertyType.villa_portfolio": "Villa",
  "propertyType.guesthouse": "Guesthouse",
  "propertyType.homestay_cluster": "Homestay",
  "propertyType.hotel": "Hotel",
  "propertyType.hostel": "Hostel",
  "propertyType.resort": "Resort",
  "propertyType.serviced_apartment": "Serviced apartment",
  "propertyType.coliving_kos": "Kos / co-living",
  "propertyType.lodge": "Lodge",
  "propertyType.campsite": "Campsite / glamping",
  "propertyType.condo_hotel": "Condo hotel",
  "propertyType.marina": "Marina",
  "propertyType.day_use": "Day use",
  "dashboard.welcome": "Welcome, {name}",
  "dashboard.property": "Property",
  "dashboard.plan": "Plan",
  "dashboard.planName": "{plan} plan",
  "dashboard.linksUsed": "{used} of {limit} payment links used this month",
  "dashboard.linksUnlimited": "{used} payment links this month (no limit)",
  "dashboard.owner": "Owner",
  "dashboard.staff": "Staff",
  "dashboard.inbox": "WhatsApp inbox",
  "dashboard.inboxEmpty": "No conversations yet. Guest chats will appear here.",
  "dashboard.paymentLinks": "Payment links",
  "dashboard.paymentLinksEmpty": "No payment links yet. Links you send to guests will appear here.",
  "dashboard.comingSoon": "Coming soon",
} as const;

export type MessageKey = keyof typeof en;

const id: Record<MessageKey, string> = {
  "common.loading": "Memuat…",
  "common.retry": "Coba lagi",
  "common.loadFailed": "Halaman tidak dapat dimuat: {reason}",
  "language.label": "Bahasa",
  "language.id": "Bahasa Indonesia",
  "language.en": "English",
  "onboarding.title": "Siapkan properti Anda",
  "onboarding.subtitle": "Tiga jawaban dan ruang kerja Anda siap dipakai.",
  "onboarding.propertyName": "Nama properti",
  "onboarding.propertyNamePlaceholder": "mis. Villa Senja Ubud",
  "onboarding.propertyType": "Jenis properti",
  "onboarding.city": "Kota atau daerah",
  "onboarding.cityPlaceholder": "mis. Ubud",
  "onboarding.submit": "Buat ruang kerja",
  "onboarding.nameTooShort": "Nama properti minimal 2 karakter.",
  "onboarding.cityRequired": "Mohon isi kota atau daerah.",
  "propertyType.villa_portfolio": "Vila",
  "propertyType.guesthouse": "Guesthouse",
  "propertyType.homestay_cluster": "Homestay",
  "propertyType.hotel": "Hotel",
  "propertyType.hostel": "Hostel",
  "propertyType.resort": "Resor",
  "propertyType.serviced_apartment": "Apartemen servis",
  "propertyType.coliving_kos": "Kos / co-living",
  "propertyType.lodge": "Penginapan (lodge)",
  "propertyType.campsite": "Perkemahan / glamping",
  "propertyType.condo_hotel": "Kondotel",
  "propertyType.marina": "Marina",
  "propertyType.day_use": "Sewa harian (day use)",
  "dashboard.welcome": "Selamat datang, {name}",
  "dashboard.property": "Properti",
  "dashboard.plan": "Paket",
  "dashboard.planName": "Paket {plan}",
  "dashboard.linksUsed": "{used} dari {limit} tautan pembayaran terpakai bulan ini",
  "dashboard.linksUnlimited": "{used} tautan pembayaran bulan ini (tanpa batas)",
  "dashboard.owner": "Pemilik",
  "dashboard.staff": "Staf",
  "dashboard.inbox": "Kotak masuk WhatsApp",
  "dashboard.inboxEmpty": "Belum ada percakapan. Chat tamu akan muncul di sini.",
  "dashboard.paymentLinks": "Tautan pembayaran",
  "dashboard.paymentLinksEmpty":
    "Belum ada tautan pembayaran. Tautan yang Anda kirim ke tamu akan muncul di sini.",
  "dashboard.comingSoon": "Segera hadir",
};

const MESSAGES: Record<Locale, Partial<Record<string, string>>> = { en, id };

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (LOCALES as readonly string[]).includes(value);
}

export function translate(
  locale: Locale,
  key: string,
  vars: Record<string, string | number> = {},
): string {
  const template = MESSAGES[locale][key] ?? MESSAGES.en[key] ?? key;
  return template.replace(/\{(\w+)\}/g, (placeholder, name: string) =>
    name in vars ? String(vars[name]) : placeholder,
  );
}

/** Every property type the backend accepts (app/models/tenant/organisation/property.py). */
export const ALL_PROPERTY_TYPES = [
  "hotel",
  "resort",
  "serviced_apartment",
  "hostel",
  "guesthouse",
  "villa_portfolio",
  "campsite",
  "condo_hotel",
  "coliving_kos",
  "lodge",
  "marina",
  "day_use",
  "homestay_cluster",
] as const;

/** Property types offered at onboarding (a subset of what the backend accepts). */
export const ONBOARDING_PROPERTY_TYPES = [
  "villa_portfolio",
  "guesthouse",
  "homestay_cluster",
  "hotel",
  "hostel",
  "resort",
  "serviced_apartment",
  "coliving_kos",
  "lodge",
  "campsite",
] as const;
