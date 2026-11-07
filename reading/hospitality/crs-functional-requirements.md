# Central Reservation System (CRS) — Functional Requirements

> **Document type:** Functional Requirements Specification
> **Scope:** Multi-property reservation, availability and rate hub sitting above one or more PMS instances
> **Positioning:** Separate system in the **Enterprise pack**; single properties do not need it (the PMS acts as its own CRS). Must work with the suite's PMS *and* third-party PMSs.
> **Priority key:** **M** must · **S** should · **C** could
> **Related:** [Portfolio architecture](hospitality-suite-portfolio-architecture.md) · [PMS](property-management-system-functional-requirements.md) · [Channel Manager](channel-manager-functional-requirements.md) · [Booking Engine](booking-engine-functional-requirements.md)

---

## 1. Purpose

A CRS gives a chain, brand, franchise group or management company **one place** to see and sell inventory across all properties, apply brand-level rate and policy standards, run a central reservations office (call centre) and feed distribution consistently. The PMS stays the operational truth for each property; the CRS is the commercial truth for the portfolio.

### In scope
- Portfolio-wide availability, rates, restrictions and content
- Central reservations office workflows (phone, email, chat)
- Brand/central rate plans, policies and promotions pushed to properties
- Cross-property search, booking, and guest redirection
- Central distribution feed to Booking Engine and Channel Manager
- Portfolio reporting on bookings and pace

### Out of scope
- Front desk, folio, housekeeping (PMS)
- OTA connectivity itself (Channel Manager; the CRS feeds it)
- Pricing optimisation (RMS)

---

## 2. Actors

| Role | Responsibilities |
|---|---|
| Central reservations agent | Takes calls/emails, searches all properties, books, modifies, cancels |
| Central reservations supervisor | Queues, agent performance, overrides |
| Brand / portfolio revenue manager | Central rate plans, restrictions, promotions, parity |
| Brand content manager | Descriptions, images, amenities standards |
| Property manager | Sees central bookings, manages local overrides within allowed limits |
| Franchisee / owner | Reports, fee statements |
| Systems: PMS instances, Booking Engine, Channel Manager, RMS, CRM, call-centre telephony |

---

## 3. Functional Requirements

### 3.1 Portfolio and Property Registry

| ID | Requirement | Priority |
|---|---|---|
| FR-CRS-001 | The system shall maintain a registry of properties with brand, region, management type (owned, managed, franchised), contact details, time zone, currency and connected PMS type. | M |
| FR-CRS-002 | The system shall support hierarchical grouping (brand → region → cluster → property) for configuration inheritance and reporting. | M |
| FR-CRS-003 | The system shall allow properties to be in states: onboarding, live, suspended, offboarded, each affecting sellability. | M |
| FR-CRS-004 | The system shall maintain brand content standards (mandatory images, description length, amenity taxonomy) and flag properties not meeting them. | S |

### 3.2 Inventory and Availability Synchronisation

| ID | Requirement | Priority |
|---|---|---|
| FR-CRS-010 | The system shall receive availability, rates and restrictions (ARI) from each connected PMS in near real time via API or event stream, and record source and timestamp. | M |
| FR-CRS-011 | The system shall map each property's unit types and rate plans to central (brand) categories so that cross-property search compares like with like. | M |
| FR-CRS-012 | The system shall support the suite's PMS natively and third-party PMSs through adapters or industry-standard messages. | M |
| FR-CRS-013 | The system shall detect stale ARI (no update within a configurable window) and alert, and optionally close sale for that property. | M |
| FR-CRS-014 | The system shall support two inventory modes per property: **pass-through** (PMS is the only source; CRS never holds inventory) and **allocated** (CRS holds a central allotment the property has released to it). | S |
| FR-CRS-015 | The system shall write every booking back to the owning PMS synchronously and confirm only when the PMS acknowledges; if the PMS is unreachable, hold the booking in a queue and alert, with a configurable "accept and sync later" fallback. | M |

### 3.3 Central Rates, Policies and Promotions

| ID | Requirement | Priority |
|---|---|---|
| FR-CRS-020 | The system shall allow definition of central rate plans and policies (cancellation, deposit, inclusions) that are pushed to selected properties, with per-property price values. | M |
| FR-CRS-021 | The system shall allow property-level overrides within permitted limits (e.g., ±10% of brand price; cannot change cancellation policy). | S |
| FR-CRS-022 | The system shall support portfolio-wide promotions (promo codes, seasonal offers) with eligible properties and blackout dates. | M |
| FR-CRS-023 | The system shall support negotiated corporate and consortia programs applying to many properties, with account codes and reporting to the client. | M |
| FR-CRS-024 | The system shall monitor rate parity between central rates, Booking Engine and channel feeds and report discrepancies. | S |

### 3.4 Central Reservations Office

| ID | Requirement | Priority |
|---|---|---|
| FR-CRS-030 | The system shall provide a single search across all properties by location, dates, guests, brand, amenities, price range and distance from a point of interest, returning availability and lowest price per property. | M |
| FR-CRS-031 | The system shall allow an agent to book, modify and cancel any property's reservation with the same policies the property applies. | M |
| FR-CRS-032 | The system shall support agent scripts and property fact sheets visible during a call. | S |
| FR-CRS-033 | The system shall integrate with telephony (screen-pop of caller's profile and recent reservations by phone number). | C |
| FR-CRS-034 | The system shall support alternative-property suggestions when the requested property is full (same brand, nearby, similar price). | M |
| FR-CRS-035 | The system shall record the agent, channel and call outcome (booked, no availability, price objection, information only) for conversion reporting. | M |
| FR-CRS-036 | The system shall support email and chat enquiry queues with assignment and SLA timers. | S |
| FR-CRS-037 | The system shall support multi-property itineraries (one booking reference spanning stays at several properties). | C |

### 3.5 Guest and Account Data

| ID | Requirement | Priority |
|---|---|---|
| FR-CRS-040 | The system shall use a shared guest identity with the CRM (or hold one when no CRM is present) so repeat guests are recognised across properties. | M |
| FR-CRS-041 | The system shall hold corporate, agent and consortia accounts centrally and share them with properties. | M |
| FR-CRS-042 | The system shall respect data-sharing rules between legal entities (a franchisee may see only its own guests' details). | M |

### 3.6 Distribution Feed

| ID | Requirement | Priority |
|---|---|---|
| FR-CRS-050 | The system shall provide a single availability and rate feed to the Booking Engine and Channel Manager for all properties, so a chain's distribution is configured once. | M |
| FR-CRS-051 | The system shall support channel-specific content and rate plan selection at brand level with property exceptions. | S |
| FR-CRS-052 | The system shall expose a cross-property availability API for brand websites and partners. | M |

### 3.7 Reporting and Fees

| ID | Requirement | Priority |
|---|---|---|
| FR-CRS-060 | The system shall report bookings, revenue, cancellations and conversion by property, agent, channel, source, brand and period. | M |
| FR-CRS-061 | The system shall report pace and on-the-books for the portfolio, comparable with RMS figures. | S |
| FR-CRS-062 | The system shall calculate central reservation fees and brand fees per property per booking (fixed, percentage, per channel) and produce fee statements. | S |
| FR-CRS-063 | The system shall report content and parity compliance per property. | S |

### 3.8 Administration

| ID | Requirement | Priority |
|---|---|---|
| FR-CRS-070 | The system shall support roles scoped to brand, region or property. | M |
| FR-CRS-071 | The system shall log all configuration changes and bookings with user and time. | M |
| FR-CRS-072 | The system shall provide onboarding tooling for a new property: mapping wizard, test bookings, go-live checklist. | S |

---

## 4. Key Business Rules

| ID | Rule |
|---|---|
| BR-CRS-01 | The PMS is the authority for whether a specific booking can be accepted; the CRS never confirms without PMS acknowledgment unless the property has enabled the queued fallback. |
| BR-CRS-02 | Central policy fields marked "locked" cannot be overridden at property level. |
| BR-CRS-03 | When a property's ARI is stale beyond the threshold, the property is shown as "call to book" rather than offering an unverified price. |
| BR-CRS-04 | Fee calculations use the booking's confirmation date and the property's currency, converted at the month-end rate for consolidated statements. |

---

## 5. AI Assistance (API-based, no model training)

| Area | Assistance |
|---|---|
| Agent desk | Summarise the caller's history and preferences in two lines; suggest alternative properties with reasons |
| Enquiry queue | Extract dates, guests and property from free-text emails into a pre-filled search; draft replies in the enquirer's language |
| Content compliance | Draft missing property descriptions from amenity data for human editing; flag descriptions that contradict amenity facts |
| Parity | Explain in plain language why a parity discrepancy occurred from the audit trail |

---

## 6. Open Questions

| # | Question |
|---|---|
| Q1 | Which third-party PMSs must be supported at launch? |
| Q2 | Is call-centre telephony integration required for the first version? |
| Q3 | Are franchise fee statements in scope, or handled by finance? |
