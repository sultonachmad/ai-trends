# Channel Manager — Functional Requirements

> **Document type:** Functional Requirements Specification
> **Scope:** Two-way connectivity between the property's inventory/rates and external demand channels: OTAs, Google (free booking links, Hotel Ads, Vacation Rentals), GDS, metasearch, wholesalers and bed banks
> **Positioning:** **Separate service** sold as an add-on (Commerce pack) and standalone to properties on third-party PMSs. Owns no inventory; mirrors the platform's Inventory & Rates service outward and feeds bookings inward.
> **Priority key:** **M** must · **S** should · **C** could
> **Related:** [Portfolio architecture](hospitality-suite-portfolio-architecture.md) · [PMS](property-management-system-functional-requirements.md) · [CRS](crs-functional-requirements.md) · [Booking Engine](booking-engine-functional-requirements.md) · [RMS](rms-functional-requirements.md)

---

## 1. Purpose

Keep availability, rates and restrictions identical on every channel within seconds, receive every booking, modification and cancellation without manual re-keying, and give the property one view of channel performance and cost. Prevent overbookings and rate-parity errors, which are the two most expensive mistakes in small-property distribution.

### In scope
Channel connections and mapping; outbound ARI (availability, rates, inventory, restrictions) sync; inbound reservations; content sync; virtual card handling; message log and reconciliation; channel performance and commission reporting; Google connectivity; wholesale allotments.

### Out of scope
Direct booking UI (Booking Engine); pricing decisions (RMS); guest communication (CRM).

---

## 2. Actors

| Role | Responsibilities |
|---|---|
| Revenue manager / owner | Connects channels, decides what is sold where, monitors parity |
| Reservations agent | Handles inbound bookings that need attention (conflicts, unmapped products) |
| Finance | Reconciles commissions and OTA payouts |
| Channel partner support | Certification, mapping assistance |
| Systems: PMS/CRS (source of ARI; receiver of bookings), OTAs, Google Hotel Center, GDS providers, metasearch, wholesalers, RMS |

---

## 3. Functional Requirements

### 3.1 Channel Connections

| ID | Requirement | Priority |
|---|---|---|
| FR-CM-001 | The system shall provide a catalog of supported channels with connection type (direct API, partner, iCal), supported features (ARI push, reservation pull, content, VCC, messaging) and certification status. | M |
| FR-CM-002 | The system shall allow a property to connect a channel through a guided wizard: credentials or partner hotel ID, product mapping, test sync, go-live. | M |
| FR-CM-003 | The system shall support **iCal import/export** as a minimum-viability connection for vacation-rental platforms and small channels (availability only). | M |
| FR-CM-004 | The system shall support a property having multiple listings on the same channel (e.g., separate listings per villa). | S |
| FR-CM-005 | The system shall allow pausing a channel (close all sales) and resuming with a full re-sync. | M |
| FR-CM-006 | The system shall support channel-specific settings: currency, markup/markdown, commission rate, payment model (property-collect vs. channel-collect), lead time cut-off. | M |

### 3.2 Product Mapping

| ID | Requirement | Priority |
|---|---|---|
| FR-CM-010 | The system shall map platform unit types and rate plans to each channel's room/rate identifiers, supporting one-to-many (one rate plan to several channel rates) and derived channel rates. | M |
| FR-CM-011 | The system shall detect unmapped channel products and inbound bookings on unknown products and route them to an exception queue. | M |
| FR-CM-012 | The system shall support occupancy-based mapping (channel rate per occupancy) and bed-level mapping for hostel channels. | M |
| FR-CM-013 | The system shall support mapping of extras/meal plans where the channel supports them. | S |
| FR-CM-014 | The system shall provide a mapping health report per channel (missing rates, missing dates, mismatched occupancy limits). | M |

### 3.3 Outbound ARI Synchronisation

| ID | Requirement | Priority |
|---|---|---|
| FR-CM-020 | The system shall push availability, prices and restrictions to all connected channels within 30 seconds of a change in the platform, using deltas rather than full refreshes where the channel allows. | M |
| FR-CM-021 | The system shall support a scheduled full re-sync per channel (daily) and on-demand re-sync for a date range. | M |
| FR-CM-022 | The system shall respect channel-specific limits (max rolling window, rate limits, batch sizes) with queuing and retry with backoff. | M |
| FR-CM-023 | The system shall apply channel allocations (cap inventory per channel), channel-specific stop-sells and channel markups before sending. | M |
| FR-CM-024 | The system shall support channel-specific restrictions (e.g., minimum stay only on one OTA) layered on top of platform restrictions. | S |
| FR-CM-025 | The system shall maintain a per-channel view of "what the channel currently has" (last acknowledged ARI) and compare it with platform truth to detect drift. | M |
| FR-CM-026 | The system shall support "last unit" protection: optionally keep N units off channels for direct or walk-in sale. | S |
| FR-CM-027 | The system shall support closed-channel-by-rate (sell BAR on OTAs but non-refundable only direct). | M |

### 3.4 Inbound Reservations

| ID | Requirement | Priority |
|---|---|---|
| FR-CM-030 | The system shall receive new bookings, modifications and cancellations from channels by push or polling within the channel's SLA, and deliver them to the PMS with the channel reference, guest details, price breakdown, payment model, extras and special requests. | M |
| FR-CM-031 | The system shall acknowledge receipt to the channel only after durable storage, and retry delivery to the PMS until acknowledged. | M |
| FR-CM-032 | The system shall translate channel occupancy/room/rate codes back to platform products and attach commission amount and channel payout expectations. | M |
| FR-CM-033 | The system shall handle bookings for unavailable inventory (race conditions) by accepting, flagging as **overbooking risk**, and alerting the property with suggested alternatives. | M |
| FR-CM-034 | The system shall store virtual card details securely (via the Payments service) with activation date, amount and expiry, and surface them to the PMS for charging at the correct time. | S |
| FR-CM-035 | The system shall detect duplicate deliveries of the same channel reservation and ignore them idempotently. | M |
| FR-CM-036 | The system shall support channel-collect vs. property-collect flags affecting folio payment expectations. | M |
| FR-CM-037 | The system shall support guest messaging relays from channels (OTA messaging APIs) into the CRM inbox where available. | S |
| FR-CM-038 | The system shall support reporting no-shows, invalid cards and cancellations back to the channel where the channel API allows it. | S |

### 3.5 Content Synchronisation

| ID | Requirement | Priority |
|---|---|---|
| FR-CM-040 | The system shall push property and unit-type content (descriptions, photos, amenities, policies) to channels that accept content via API. | S |
| FR-CM-041 | The system shall show per-channel content completeness scores and missing mandatory fields. | S |
| FR-CM-042 | The system shall support channel-specific overrides of descriptions and photos. | C |

### 3.6 Parity and Monitoring

| ID | Requirement | Priority |
|---|---|---|
| FR-CM-050 | The system shall provide a full message log per channel (outbound ARI, inbound bookings) with payloads, status, retries and error text, searchable by date and reservation. | M |
| FR-CM-051 | The system shall alert on sync failures, stale channels, overbooking risks, and unmapped products via in-app, email and messaging notifications. | M |
| FR-CM-052 | The system shall provide a parity dashboard comparing prices on each channel and direct for a sample of dates, with explanations (markup, derived rate, channel discount program). | S |
| FR-CM-053 | The system shall integrate with rate-shopping data (own listing as seen publicly) to detect undercutting by wholesalers. | C |

### 3.7 Wholesale and Allotments

| ID | Requirement | Priority |
|---|---|---|
| FR-CM-060 | The system shall support wholesaler/tour-operator allotments with contracted inventory, release periods and net rates, separate from free-sale inventory. | S |
| FR-CM-061 | The system shall reconcile wholesaler bookings against allotments and report pickup. | S |
| FR-CM-062 | The system shall support bed-bank connections with net rate and markup handling. | C |

### 3.8 GDS and Metasearch

| ID | Requirement | Priority |
|---|---|---|
| FR-CM-070 | The system shall connect to GDS via a certified provider for corporate and travel-agent distribution, including negotiated rate codes. | C |
| FR-CM-071 | The system shall feed metasearch engines with price and availability linking to the Booking Engine, with click and conversion tracking. | S |

### 3.9 Google Channel (OTA Alternative)

| ID | Requirement | Priority |
|---|---|---|
| FR-CM-080 | The system shall connect the property to Google Hotel Center and send ARI for all sellable unit types and rate plans so the property appears with live prices on Google Search and Maps via **Free Booking Links** (commission-free). | M |
| FR-CM-081 | The system shall support **Hotel Ads** participation with bid strategy settings (per-click or commission-per-stay/booking) and budget caps per property. | S |
| FR-CM-082 | The system shall generate landing-page URLs per itinerary that open the Booking Engine at the exact displayed price and support Google's price-accuracy checks. | M |
| FR-CM-083 | The system shall send conversion data (bookings, value) back to Google for attribution. | M |
| FR-CM-084 | The system shall support the **Vacation Rentals** feed for whole-unit properties. | S |
| FR-CM-085 | The system shall link to the property's **Google Business Profile** to ensure the booking link, phone number, address and attributes match the platform content, and report mismatches. | S |
| FR-CM-086 | The system shall provide a Google performance view: impressions, clicks, bookings, cost, revenue, price-accuracy score, with comparisons to OTA cost per booking. | M |
| FR-CM-087 | The system shall offer a self-serve "Connect to Google" wizard for properties without a connectivity partner, including listing verification steps. | S |
| FR-CM-088 | The system shall support Google's **Things to Do** feed for properties selling activities when the Ancillary pack is enabled. | C |

### 3.10 Reporting and Finance

| ID | Requirement | Priority |
|---|---|---|
| FR-CM-090 | The system shall report production by channel: bookings, nights, revenue, ADR, lead time, cancellation rate, commission, net revenue and cost per booking. | M |
| FR-CM-091 | The system shall produce commission reconciliation statements per channel and period, matching channel invoices against bookings and flagging differences (cancelled, no-show, modified). | S |
| FR-CM-092 | The system shall export channel data to the RMS for channel-cost-aware pricing. | S |

### 3.11 Administration

| ID | Requirement | Priority |
|---|---|---|
| FR-CM-100 | The system shall operate in multi-tenant mode serving many properties, including properties whose PMS is a third party connected via API or standard messages. | M |
| FR-CM-101 | The system shall provide a partner certification sandbox for each channel connection. | S |
| FR-CM-102 | The system shall log all configuration changes with user and time. | M |

---

## 4. Key Business Rules

| ID | Rule |
|---|---|
| BR-CM-01 | The platform (PMS/CRS) is the only source of ARI; the Channel Manager never edits availability or prices on its own except by applying configured channel allocations and markups. |
| BR-CM-02 | A channel booking is never rejected to the channel for lack of inventory; it is accepted and flagged, because the channel has already confirmed to the guest. |
| BR-CM-03 | Inbound messages are processed idempotently by channel reference and version. |
| BR-CM-04 | Channel-collect bookings create a receivable from the channel, not a guest payment expectation. |
| BR-CM-05 | A channel with no successful ARI acknowledgment for the configured window is shown as "at risk" and the property is alerted. |

---

## 5. AI Assistance (API-based, no model training)

| Area | Assistance |
|---|---|
| Mapping | Suggest mappings between platform products and channel room/rate names by text similarity, for human confirmation |
| Error triage | Translate channel error payloads into a plain-language cause and a suggested fix |
| Parity | Explain each parity discrepancy with the configuration that caused it |
| Content | Draft channel-ready descriptions in the channel's required length and language from platform content |
| Performance | Weekly summary: which channels are growing, cost per booking trend, suggested allocation changes (recommendation only) |

---

## 6. Open Questions

| # | Question |
|---|---|
| Q1 | Which channels at launch (likely the top 3–5 OTAs, Google, iCal) and which via a connectivity partner? |
| Q2 | Will the service be sold standalone to third-party-PMS properties in the first release? |
| Q3 | Is GDS required for the initial target segment? |
