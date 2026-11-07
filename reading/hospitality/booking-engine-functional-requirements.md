# Direct Booking Engine — Functional Requirements

> **Document type:** Functional Requirements Specification
> **Scope:** Guest-facing direct booking for any hospitality unit type (rooms, beds, apartments, villas, pitches, hourly units), embedded in the property's website and reachable from Google listings and marketing links
> **Positioning:** Module of the PMS platform (Commerce pack). It reads live inventory and rates from the platform; it never holds its own inventory. Can also be fed by the CRS for chains.
> **Priority key:** **M** must · **S** should · **C** could
> **Related:** [Portfolio architecture](hospitality-suite-portfolio-architecture.md) · [PMS](property-management-system-functional-requirements.md) · [Payments](payments-functional-requirements.md) · [Channel Manager](channel-manager-functional-requirements.md) · [CRM](crm-guest-engagement-functional-requirements.md)

---

## 1. Purpose

Convert demand that reaches the property directly (website, Google, social, email campaigns) into confirmed, paid bookings at zero commission, while capturing guest data and upsell revenue. The engine must be as fast and trustworthy as an OTA checkout, and work for traditional guests (simple, phone-number-visible, printable confirmation) and modern guests (mobile, wallet payments, instant messaging follow-up).

### In scope
Search and results, rate and package display, extras/upsell, checkout and payment, guest account, confirmation, modification/cancellation self-service, multi-property search for groups, promo/corporate codes, analytics and attribution, widgets and deep links, content management for the engine.

### Out of scope
Website CMS itself; OTA connectivity (Channel Manager); post-booking messaging campaigns (CRM); payment processing internals (Payments service).

---

## 2. Actors

| Role | Responsibilities |
|---|---|
| Guest / booker | Searches, compares, books, pays, manages booking |
| Property marketing/admin | Configures look & feel, content, promotions, tracking |
| Revenue manager | Chooses which rate plans and restrictions are sold direct |
| Systems: PMS/CRS (inventory, rates), Payments, CRM (profiles, consent), Google Hotel Center (landing page and conversion tracking), analytics tools |

---

## 3. Functional Requirements

### 3.1 Search and Availability

| ID | Requirement | Priority |
|---|---|---|
| FR-BE-001 | The engine shall accept dates (check-in/check-out, or date + hour block for hourly units), number of adults/children by age, number of units, and optional promo/corporate code. | M |
| FR-BE-002 | The engine shall show a calendar with availability and lowest price per date, including minimum-stay hints and closed dates. | M |
| FR-BE-003 | The engine shall support flexible-date search (±3 days, whole month) showing cheapest options. | S |
| FR-BE-004 | The engine shall return results from live platform availability, honoring restrictions, channel allocations and overbooking rules exactly as the PMS computes them. | M |
| FR-BE-005 | The engine shall support unit-type results for rooms/apartments/pitches, **bed-level results** for dorms (with gender filters), **whole-unit results** for villas/rentals, and **time-slot results** for hourly units. | M |
| FR-BE-006 | The engine shall support multi-unit bookings in one checkout (e.g., 2 rooms with different occupancies). | M |
| FR-BE-007 | The engine shall show "only N left" and sold-out states, and offer alternative dates or unit types when nothing matches. | S |
| FR-BE-008 | The engine shall support filters (price, bed type, view, accessibility, pet-friendly, kitchen) and sorting (price, recommended). | S |
| FR-BE-009 | The engine shall support multi-property search when fed by the CRS (choose property on a map/list first). | S |
| FR-BE-010 | The engine shall support a waitlist/notify-me request for sold-out dates, creating a lead in the CRM. | C |

### 3.2 Rates, Packages and Extras

| ID | Requirement | Priority |
|---|---|---|
| FR-BE-020 | The engine shall display each eligible rate plan with name, inclusions, cancellation and payment policy in plain language, and total price for the stay with taxes and mandatory fees clearly itemised. | M |
| FR-BE-021 | The engine shall display prices in the guest's chosen currency for information while charging in the property's currency (or in the guest's currency when multi-currency pricing is enabled). | M |
| FR-BE-022 | The engine shall support promo codes, corporate codes and member-only rates revealed on login or code entry. | M |
| FR-BE-023 | The engine shall offer add-ons and extras (breakfast, parking, transfers, late checkout, equipment, activities) with per-stay, per-night, per-person pricing and availability checks for limited-quantity items. | M |
| FR-BE-024 | The engine shall support upsell prompts (upgrade to a higher unit type for +X) configured by the property. | S |
| FR-BE-025 | The engine shall display mandatory fees (resort, cleaning, tourist tax) before checkout so the final amount never surprises the guest, in compliance with price-display laws in the property's jurisdiction. | M |
| FR-BE-026 | The engine shall support length-of-stay and early-booking discounts shown as strike-through pricing with the reason. | S |
| FR-BE-027 | The engine shall support gift vouchers and loyalty points as (partial) payment where enabled. | C |

### 3.3 Checkout and Payment

| ID | Requirement | Priority |
|---|---|---|
| FR-BE-030 | The engine shall collect booker details, occupant names when required, estimated arrival time, special requests and consents, with per-property configuration of required fields. | M |
| FR-BE-031 | The engine shall collect payment according to the rate plan's policy: card guarantee only, deposit, full prepayment or instalments, through the Payments service with hosted fields (no card data touches the engine). | M |
| FR-BE-032 | The engine shall support wallet payments (Apple Pay, Google Pay), bank transfer instructions, and local payment methods as configured. | S |
| FR-BE-033 | The engine shall support strong customer authentication (3-D Secure) when required. | M |
| FR-BE-034 | The engine shall create the reservation in the PMS atomically with payment authorisation; if either fails, no booking is created and the guest sees a clear message. | M |
| FR-BE-035 | The engine shall display and send a confirmation (email and optionally SMS/WhatsApp) with confirmation number, policy summary, directions, and a link to manage the booking. | M |
| FR-BE-036 | The engine shall support abandoned-cart capture (with consent) and hand off to the CRM for recovery messages. | S |
| FR-BE-037 | The engine shall support guest accounts (email/password or social/one-time-code login) to prefill details and view booking history. | S |
| FR-BE-038 | The engine shall support booking on behalf of someone else (booker ≠ guest) and company billing details. | M |
| FR-BE-039 | The engine shall support a policy acceptance checkbox with versioned terms stored with the booking. | M |

### 3.4 Self-Service Management

| ID | Requirement | Priority |
|---|---|---|
| FR-BE-040 | The guest shall be able to view, modify (dates, unit, extras, occupants) and cancel a booking via a secure link, with price difference and cancellation fees shown before confirming. | M |
| FR-BE-041 | Modifications shall respect the same restrictions and policies as new bookings; disallowed changes shall direct the guest to contact the property. | M |
| FR-BE-042 | The guest shall be able to pay an outstanding balance or deposit via a link. | M |
| FR-BE-043 | The guest shall be able to add extras after booking. | S |
| FR-BE-044 | The engine shall hand off to the guest portal / online check-in flow when the Guest pack is enabled. | S |

### 3.5 Design, Content and Localisation

| ID | Requirement | Priority |
|---|---|---|
| FR-BE-050 | The engine shall be fully responsive and meet WCAG 2.2 AA. | M |
| FR-BE-051 | The engine shall support property branding (logo, colours, fonts, images) and a hosted page or embeddable widget/iframe. | M |
| FR-BE-052 | The engine shall support multiple languages for UI and property content, with fallback to a default language. | M |
| FR-BE-053 | The engine shall show property and unit-type content (descriptions, photos, amenities, policies, map) from the platform content store. | M |
| FR-BE-054 | The engine shall support cookie consent and privacy notice presentation per jurisdiction. | M |
| FR-BE-055 | The engine shall display a visible phone number and "call us" option for guests who prefer to book by phone, capturing the lead. | S |
| FR-BE-056 | The engine shall load the first results view within 2 seconds on a mid-range mobile device (functional performance target). | M |

### 3.6 Attribution, Analytics and Google Integration

| ID | Requirement | Priority |
|---|---|---|
| FR-BE-060 | The engine shall record source, medium, campaign (UTM) and referrer for every session and booking, and pass them to the PMS reservation as source/channel. | M |
| FR-BE-061 | The engine shall provide deep-link URLs that pre-fill dates, guests, unit type, rate plan and promo code. | M |
| FR-BE-062 | The engine shall serve **Google landing pages**: a deep link from Google Hotel Ads / Free Booking Links must open the exact itinerary with the same price Google displayed, and the engine shall report conversions back to Google (conversion tracking). | M |
| FR-BE-063 | The engine shall tag bookings originating from Google surfaces as distinct sources for reporting. | M |
| FR-BE-064 | The engine shall integrate with web analytics and ad platforms via a tag manager with e-commerce events (search, view, add extra, checkout, purchase). | S |
| FR-BE-065 | The engine shall provide a funnel report (searches → results → rate selected → checkout → confirmed) by device, language and source. | M |
| FR-BE-066 | The engine shall support A/B testing of layout or messaging variants. | C |

### 3.7 Group and Special Flows

| ID | Requirement | Priority |
|---|---|---|
| FR-BE-070 | The engine shall support group booking links where attendees book from a block at the group rate, showing block availability. | S |
| FR-BE-071 | The engine shall support quote requests for large groups or long stays, creating a lead/quote in the PMS. | S |
| FR-BE-072 | The engine shall support long-stay enquiries (monthly) with monthly pricing display. | S |
| FR-BE-073 | The engine shall support activity/service-only bookings (spa, tours) without accommodation when the Ancillary pack is enabled. | C |

### 3.8 Administration

| ID | Requirement | Priority |
|---|---|---|
| FR-BE-080 | The property shall be able to choose which unit types and rate plans are sold on the engine, independently from other channels. | M |
| FR-BE-081 | The property shall be able to configure required fields, payment methods, languages, currencies, terms, and confirmation templates. | M |
| FR-BE-082 | The property shall be able to preview the engine as a guest before publishing changes. | S |
| FR-BE-083 | The engine shall support a maintenance mode with a message and phone number. | M |

---

## 4. Key Business Rules

| ID | Rule |
|---|---|
| BR-BE-01 | Prices shown must equal prices charged for the same itinerary within the session; if inventory or price changes before checkout completes, the guest is informed and must re-confirm. |
| BR-BE-02 | A booking is created only after the required payment step succeeds; the reservation and payment are linked by a single idempotency key to prevent duplicates. |
| BR-BE-03 | The engine never applies a rate plan whose restrictions fail for any night of the stay. |
| BR-BE-04 | Mandatory fees and taxes are shown at or before the first price display in jurisdictions with all-in pricing laws. |

---

## 5. AI Assistance (API-based, no model training)

| Area | Assistance |
|---|---|
| Content | Generate and translate unit-type descriptions from structured facts, for human approval |
| Search help | A chat/assist box that converts "a quiet room for two next weekend with parking" into a search, grounded on the property's facts; never invents availability |
| Policy explanation | Plain-language summary of the cancellation and payment policy in the guest's language, generated from the structured policy |
| Abandonment | Draft personalised recovery messages for the CRM to send |
| Funnel insight | Weekly plain-language summary of conversion changes and likely causes from the analytics data |

---

## 6. Open Questions

| # | Question |
|---|---|
| Q1 | Hosted page only, or also a JavaScript widget and a headless API for custom front-ends? |
| Q2 | Which wallets and local payment methods are required at launch? |
| Q3 | Will Google connectivity be direct (Hotel Center) or via a connectivity partner for the first release? |
