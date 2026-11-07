# Hospitality Property Management System (PMS) — Functional Requirements

> **Document type:** Functional Requirements Specification (FRS)
> **Scope:** A general-purpose PMS for any lodging or hospitality property, not only hotels
> **Version:** 1.0 (draft) · **Date:** 2026-11-07
> **Priority key:** **M** = Must have (MVP) · **S** = Should have (release 2) · **C** = Could have (later / optional module)

---

## Table of Contents

1. [Purpose and Scope](#1-purpose-and-scope)
2. [Property Types Supported](#2-property-types-supported)
3. [Glossary](#3-glossary)
4. [Actors and User Roles](#4-actors-and-user-roles)
5. [Core Domain Model](#5-core-domain-model)
6. [Functional Requirements](#6-functional-requirements)
   - 6.1 [Organization, Property and Inventory Setup](#61-organization-property-and-inventory-setup)
   - 6.2 [Rates, Pricing and Availability](#62-rates-pricing-and-availability)
   - 6.3 [Reservations](#63-reservations)
   - 6.4 [Groups, Blocks and Events](#64-groups-blocks-and-events)
   - 6.5 [Distribution: Booking Engine and Channel Management](#65-distribution-booking-engine-and-channel-management)
   - 6.6 [Guest Profiles and CRM](#66-guest-profiles-and-crm)
   - 6.7 [Front Desk Operations: Arrival, Stay and Departure](#67-front-desk-operations-arrival-stay-and-departure)
   - 6.8 [Unit Assignment and Room Moves](#68-unit-assignment-and-room-moves)
   - 6.9 [Housekeeping](#69-housekeeping)
   - 6.10 [Maintenance and Asset Management](#610-maintenance-and-asset-management)
   - 6.11 [Folios, Billing and Charges](#611-folios-billing-and-charges)
   - 6.12 [Payments, Deposits and Refunds](#612-payments-deposits-and-refunds)
   - 6.13 [Taxes, Fees and Invoicing](#613-taxes-fees-and-invoicing)
   - 6.14 [Accounts Receivable and City Ledger](#614-accounts-receivable-and-city-ledger)
   - 6.15 [Night Audit and End-of-Day](#615-night-audit-and-end-of-day)
   - 6.16 [Long-Stay, Residential and Lease Management](#616-long-stay-residential-and-lease-management)
   - 6.17 [Ancillary Services: F&B, Spa, Activities and Rentals](#617-ancillary-services-fb-spa-activities-and-rentals)
   - 6.18 [Guest Self-Service and Communication](#618-guest-self-service-and-communication)
   - 6.19 [Access Control and Keys](#619-access-control-and-keys)
   - 6.20 [Owner and Third-Party Management](#620-owner-and-third-party-management)
   - 6.21 [Multi-Property and Chain Management](#621-multi-property-and-chain-management)
   - 6.22 [Loyalty and Memberships](#622-loyalty-and-memberships)
   - 6.23 [Revenue Management Support](#623-revenue-management-support)
   - 6.24 [Reporting and Analytics](#624-reporting-and-analytics)
   - 6.25 [Users, Security and Audit](#625-users-security-and-audit)
   - 6.26 [Regulatory and Compliance](#626-regulatory-and-compliance)
   - 6.27 [Integrations and APIs](#627-integrations-and-apis)
   - 6.28 [Configuration, Localization and Notifications](#628-configuration-localization-and-notifications)
   - 6.29 [Business Continuity and Offline Operation](#629-business-continuity-and-offline-operation)
7. [Key Business Rules](#7-key-business-rules)
8. [State Models](#8-state-models)
9. [Property-Type Applicability Matrix](#9-property-type-applicability-matrix)
10. [Non-Functional Requirements (Summary)](#10-non-functional-requirements-summary)
11. [Assumptions, Constraints and Open Questions](#11-assumptions-constraints-and-open-questions)

---

## 1. Purpose and Scope

### 1.1 Purpose

This document specifies what a Property Management System (PMS) must do to run the daily commercial, operational and financial work of a hospitality property. It is written to be **property-type agnostic**: the same core supports a 400-room city hotel, a 12-bed hostel, a resort with villas, a serviced-apartment block with monthly leases, a campsite with pitches, and a portfolio of vacation rentals owned by third parties.

### 1.2 In Scope

- Inventory definition for any sellable unit (room, bed, apartment, villa, pitch, cabin, pod, desk, meeting space)
- Rates, availability, restrictions and distribution
- The reservation and stay lifecycle, from enquiry to post-departure
- Front desk, housekeeping and maintenance operations
- Guest folios, payments, taxes, invoicing, receivables and end-of-day close
- Long-stay and lease billing
- Owner accounting for managed or rental-pool properties
- Guest self-service, messaging and digital access
- Multi-property operations, reporting, security, compliance and integrations

### 1.3 Out of Scope (handled by integrated systems)

| Capability | Expected external system |
|---|---|
| Full general ledger, payroll, procurement | ERP / accounting system |
| Restaurant table service and kitchen display | F&B POS |
| Dynamic price optimization algorithms | Revenue Management System (RMS) — PMS provides data and receives rates |
| Marketing automation campaigns | CRM / CDP / email platform |
| Detailed event/banquet production (BEOs, floor plans) | Sales & Catering system (PMS holds blocks and billing) |
| Lock hardware and Wi-Fi infrastructure | Lock / network vendors via integration |

### 1.4 Design Principles

1. **One unit abstraction.** Every sellable thing is a *unit* belonging to a *unit type*. Rooms, beds, pitches and apartments are configurations, not separate code paths.
2. **Flexible time grain.** Stays may be priced and held by night, by day, by hour or by month.
3. **Folio as the financial truth.** Every charge, payment and adjustment posts to a folio and is auditable.
4. **Configuration over customization.** Property-type behaviour is driven by settings and templates.
5. **API-first.** Every function available in the UI is available through an API.

---

## 2. Property Types Supported

| Code | Property type | Distinguishing characteristics |
|---|---|---|
| HTL | Hotel (city, business, boutique, budget) | Nightly room stays, high turnover, front desk, often F&B and groups |
| RES | Resort / all-inclusive | Packages, activities, multiple outlets, villas, meal plans, wristbands |
| SAP | Serviced apartment / aparthotel | Mixed nightly and monthly stays, kitchens, weekly cleaning, utilities |
| HST | Hostel | Bed-level inventory in shared dorms, gender-specific rooms, lockers, age rules |
| BNB | B&B / guesthouse / inn | Small team, owner-operated, simple workflows, breakfast inclusion |
| VRM | Vacation rental / villa portfolio | Whole-unit rental, dispersed locations, third-party owners, cleaning between stays |
| CMP | Campsite / RV park / glamping | Pitches and plots, vehicle and equipment details, seasonal pitches, electricity hookup |
| CDH | Condo-hotel / rental pool | Units owned by individuals, revenue sharing, owner stays and blocks |
| CLV | Co-living / student housing | Room or bed leases, term contracts, community spaces, recurring billing |
| LDG | Lodge / cabin / eco-retreat | Remote operation, seasonal opening, activity bundles, limited connectivity |
| CRZ | Marina / boat stays (optional) | Berths as units, vessel dimensions as constraints |
| MTG | Day-use / micro-stay / capsule | Hourly blocks, multiple turns per day |

---

## 3. Glossary

| Term | Definition |
|---|---|
| **Property** | A single operating location with its own inventory, business date and configuration |
| **Unit** | The smallest physically assignable sellable item: a room, bed, apartment, pitch, villa, berth or pod |
| **Unit type** | A category of interchangeable units sold at the same price (e.g., Deluxe King, 6-Bed Mixed Dorm, Serviced Pitch) |
| **Component unit** | A unit that is part of a larger unit (e.g., two bedrooms that can also sell as one suite; beds within a dorm) |
| **Rate plan** | A set of prices plus conditions (inclusions, cancellation policy, payment terms, eligibility) |
| **Restriction** | A rule limiting bookability: closed, min/max stay, closed to arrival/departure, min advance booking |
| **Reservation** | A commitment for one or more units over a period for one or more guests |
| **Stay** | The in-house phase of a reservation, from check-in to check-out |
| **Folio** | A guest or company account holding charges and payments |
| **Routing** | Rules that direct specific charges to a different folio (e.g., room to company, extras to guest) |
| **Business date** | The PMS operational date, advanced by night audit, which may differ from calendar date |
| **Block / allotment** | Inventory held for a group, company or wholesaler, released by a cut-off date |
| **City ledger** | Accounts receivable for direct-billed companies, agents and groups |
| **OOO / OOS** | Out of Order (removed from inventory) / Out of Service (sellable but not preferred) |
| **ADR / RevPAR / Occupancy** | Average daily rate / revenue per available unit / sold units ÷ available units |
| **Channel** | A source through which reservations arrive (direct web, OTA, GDS, phone, walk-in, wholesaler) |
| **Owner statement** | Periodic report of revenue, expenses and payouts for a unit owner |

---

## 4. Actors and User Roles

| Role | Primary responsibilities |
|---|---|
| Guest / booker | Searches, books, modifies, pays, checks in online, messages the property |
| Front desk agent / receptionist | Arrivals, departures, walk-ins, payments, guest requests |
| Reservations agent | Phone/email bookings, modifications, groups, waitlists |
| Front office manager / duty manager | Overrides, room moves, disputes, night audit oversight |
| Night auditor | End-of-day close, rate posting, no-show handling, reports |
| Housekeeping supervisor | Assigns cleaning tasks, inspects units, manages lost & found and linen |
| Housekeeper / room attendant | Cleans units, updates status via mobile |
| Maintenance technician / engineer | Resolves work orders, preventive maintenance |
| Revenue manager | Rates, restrictions, forecasts, channel strategy |
| Sales / events manager | Groups, corporate accounts, contracts, blocks |
| Finance / accounts receivable | Invoices, city ledger, reconciliations, refunds, exports to GL |
| General manager / owner-operator | Dashboards, approvals, overall configuration |
| Property owner (third party) | Views statements, books owner stays, blocks dates |
| Portfolio / chain administrator | Multi-property configuration, central reservations, brand standards |
| System administrator | Users, roles, integrations, settings |
| External systems | OTAs, channel manager, RMS, POS, locks, payment gateway, ERP, government portals |

---

## 5. Core Domain Model

```
Organization ──< Property ──< Building/Area ──< Unit ──< Component Unit (bed, sub-room)
                    │                            │
                    ├──< Unit Type ─────────────┘
                    ├──< Rate Plan ──< Rate (date × unit type × occupancy)
                    ├──< Restriction (date × unit type × rate plan × channel)
                    ├──< Package / Add-on
                    └──< Reservation ──< Reserved Unit (dates, unit type, assigned unit)
                              │                 └──< Guest (occupants)
                              ├──> Booker / Company / Travel Agent / Group
                              └──< Folio ──< Transaction (charge, payment, adjustment)
Guest Profile ──< Stay History, Preferences, Documents, Consents
Owner ──< Unit Ownership ──< Owner Statement
Task (housekeeping / maintenance) ──> Unit
```

Key modelling requirements:

- A **reservation** can contain multiple **reserved units**, each with its own dates, unit type, rate plan and occupants.
- A **unit** can be sellable on its own, as part of a combination (connecting rooms, multi-bedroom villa), or as component parts (beds in a dorm). Selling one must reduce availability of the others correctly.
- **Time grain** is configured per unit type: `night`, `day`, `hour-block`, `month`.

---

## 6. Functional Requirements

Requirement IDs use the format `FR-<MODULE>-<NNN>`.

### 6.1 Organization, Property and Inventory Setup

| ID | Requirement | Priority |
|---|---|---|
| FR-INV-001 | The system shall support an organization containing one or more properties, each with its own address, time zone, currency, language, tax jurisdiction, check-in/check-out times and business date. | M |
| FR-INV-002 | The system shall allow a property to be classified by property type (Section 2) and pre-load default configuration templates for that type. | S |
| FR-INV-003 | The system shall allow definition of buildings, floors, wings, zones or sites to group units physically. | M |
| FR-INV-004 | The system shall allow definition of unit types with name, description, multilingual content, photos, maximum occupancy (adults/children/infants), base occupancy, bed configuration, size, amenities and accessibility features. | M |
| FR-INV-005 | The system shall allow definition of individual units with number/name, unit type, location, features (view, floor, smoking, accessible, pet-friendly), connecting relationships and sort order. | M |
| FR-INV-006 | The system shall support **bed-level inventory**, where a dorm or shared room contains individually sellable beds, with optional gender restriction (male/female/mixed) at room level. | M |
| FR-INV-007 | The system shall support **combinable units** (e.g., 3-bedroom villa sellable as whole or as separate bedrooms; connecting rooms sold as a family suite) and keep parent/child availability consistent. | S |
| FR-INV-008 | The system shall support **pitch/plot inventory** with attributes such as dimensions, surface, electric hookup amperage, water/sewer connection and maximum vehicle length. | S |
| FR-INV-009 | The system shall allow configuring the **time grain** per unit type: nightly, daily (day-use), hourly blocks with configurable duration and turnaround buffer, or monthly. | M |
| FR-INV-010 | The system shall allow units to be marked as non-sellable (staff use, owner use, model room) and excluded from availability and occupancy statistics. | M |
| FR-INV-011 | The system shall support seasonal opening and closing periods per property, area or unit type. | M |
| FR-INV-012 | The system shall allow definition of non-unit inventory with limited quantity (parking spaces, cots/cribs, rollaway beds, lockers, bikes, kayaks, EV chargers) that can be reserved alongside stays. | S |
| FR-INV-013 | The system shall allow definition of amenities and facilities (pool, gym, kitchen, laundry) for display and filtering. | S |
| FR-INV-014 | The system shall keep an effective-dated history of unit configuration changes (e.g., a room reclassified from Standard to Superior from a given date). | S |
| FR-INV-015 | The system shall support virtual / run-of-house unit types that can be fulfilled by any unit from a defined set. | S |

### 6.2 Rates, Pricing and Availability

| ID | Requirement | Priority |
|---|---|---|
| FR-RAT-001 | The system shall allow creation of rate plans with code, name, description, validity period, applicable unit types, channels, market segment and booking source. | M |
| FR-RAT-002 | The system shall store prices per date, unit type, rate plan and occupancy (per-unit price, per-person price, or base price plus extra adult/child charges). | M |
| FR-RAT-003 | The system shall support price per bed (dorms), per pitch plus per person/vehicle/pet (campsites), per hour block (day-use), and per month (long stay). | M |
| FR-RAT-004 | The system shall support **derived rate plans** calculated from a parent rate by percentage or fixed amount (e.g., Non-Refundable = BAR − 10%), updating automatically when the parent changes. | M |
| FR-RAT-005 | The system shall support length-of-stay pricing (discounts or different prices for 7+, 28+ nights) and weekly/monthly rates. | M |
| FR-RAT-006 | The system shall support day-of-week pricing and seasonal pricing calendars. | M |
| FR-RAT-007 | The system shall support restrictions per date, unit type, rate plan and channel: stop-sell, closed to arrival (CTA), closed to departure (CTD), minimum stay, maximum stay, min/max stay through, minimum and maximum advance booking. | M |
| FR-RAT-008 | The system shall support bulk updates of rates and restrictions across date ranges, days of week, unit types and rate plans. | M |
| FR-RAT-009 | The system shall support packages that bundle a stay with inclusions (breakfast, parking, spa credit, activities), with configurable posting rules (per night, per stay, per person) and revenue allocation to departments. | M |
| FR-RAT-010 | The system shall support meal plans (room only, bed & breakfast, half board, full board, all-inclusive) as rate attributes or packages. | S |
| FR-RAT-011 | The system shall support negotiated / corporate rates and agent/wholesale rates restricted to specific profiles or codes. | M |
| FR-RAT-012 | The system shall support promo codes with validity windows, usage limits, eligible stay dates and stacking rules. | S |
| FR-RAT-013 | The system shall support member-only or loyalty-tier rates. | S |
| FR-RAT-014 | The system shall support cancellation policies (free until X days/hours before arrival, then a percentage, first night, or full stay) and no-show policies attached to rate plans. | M |
| FR-RAT-015 | The system shall support deposit/payment policies (pay at property, deposit percentage at booking, full prepayment, scheduled installments). | M |
| FR-RAT-016 | The system shall support occupancy-based price adjustments (rule-based dynamic pricing: e.g., +10% when occupancy > 80%) as an optional built-in capability. | C |
| FR-RAT-017 | The system shall accept rate and restriction updates from an external RMS and record their source. | S |
| FR-RAT-018 | The system shall display a real-time availability grid (by unit type and date) showing physical inventory, sold, blocked, out-of-order and remaining. | M |
| FR-RAT-019 | The system shall allow configurable overbooking limits per unit type and date. | S |
| FR-RAT-020 | The system shall support channel-specific inventory allocation (e.g., cap at 5 units on a given OTA) and channel rate markups or parity rules. | S |
| FR-RAT-021 | The system shall support a "rate shopping" view showing all eligible rate plans and total prices for a requested stay, sorted by price. | M |
| FR-RAT-022 | The system shall support mandatory fees per stay or per night (resort fee, cleaning fee, pet fee, linen fee) with configurable tax treatment and display. | M |
| FR-RAT-023 | The system shall version rate changes and keep a history of who changed what and when. | M |

### 6.3 Reservations

| ID | Requirement | Priority |
|---|---|---|
| FR-RES-001 | The system shall allow creation of a reservation by searching availability for dates (or hour block), number of guests and optional filters (unit type, features, accessibility). | M |
| FR-RES-002 | The system shall support multi-unit reservations, each line with independent dates, unit type, rate plan, occupants and price. | M |
| FR-RES-003 | The system shall support stays where the unit type or rate changes mid-stay (split stays) while remaining one reservation. | S |
| FR-RES-004 | The system shall capture booker details separately from occupant/guest details, and allow multiple named guests per unit. | M |
| FR-RES-005 | The system shall capture source, channel, market segment, travel agent, company, booking reference from channel, and commission details. | M |
| FR-RES-006 | The system shall capture estimated arrival time, transport details (flight, vehicle registration, RV/boat dimensions) and special requests. | M |
| FR-RES-007 | The system shall support reservation statuses: enquiry/quote, tentative/option (with expiry), confirmed, guaranteed, waitlisted, checked-in, checked-out, cancelled, no-show. | M |
| FR-RES-008 | The system shall allow sending a quote/proposal to a prospective guest with an expiry date and a link to confirm and pay. | S |
| FR-RES-009 | The system shall automatically release tentative/option reservations at expiry and notify the responsible user. | S |
| FR-RES-010 | The system shall support waitlists per date and unit type and alert staff when inventory becomes available. | S |
| FR-RES-011 | The system shall allow modification of dates, unit types, occupants, rate plans and add-ons, recalculating price and showing the difference before confirmation. | M |
| FR-RES-012 | The system shall allow the user to keep the original price on modification (price lock) subject to permission. | S |
| FR-RES-013 | The system shall support cancellation with automatic calculation of cancellation fees according to the attached policy, with override permission and a mandatory reason. | M |
| FR-RES-014 | The system shall support reinstating a cancelled reservation if inventory is available. | S |
| FR-RES-015 | The system shall generate a unique confirmation number and send confirmation, modification and cancellation communications using templates. | M |
| FR-RES-016 | The system shall prevent double-booking of an assigned unit across overlapping time ranges, including turnaround buffers. | M |
| FR-RES-017 | The system shall support walk-in reservations created directly at check-in. | M |
| FR-RES-018 | The system shall support day-use and hourly reservations with start/end times and multiple turns per day. | S |
| FR-RES-019 | The system shall support reservations for add-on inventory (parking, cots, equipment) with availability checks. | S |
| FR-RES-020 | The system shall support complimentary and house-use reservations with an authorization trail. | M |
| FR-RES-021 | The system shall support owner stays and owner blocks for third-party-owned units (see 6.20). | S |
| FR-RES-022 | The system shall detect potential duplicate reservations (same guest, overlapping dates) and warn the user. | S |
| FR-RES-023 | The system shall record a complete change history per reservation (field, old value, new value, user, timestamp, source). | M |
| FR-RES-024 | The system shall allow attaching notes, alerts (shown at check-in), traces/follow-up tasks with due dates to reservations. | M |
| FR-RES-025 | The system shall support guest age categories configurable per property (adult, teen, child, infant) and enforce age policies (e.g., adults-only, hostel age limits). | M |
| FR-RES-026 | The system shall support pet details and pet policies (count, size, fee, allowed unit types). | S |
| FR-RES-027 | The system shall support booking-level guarantees (credit card, deposit, company guarantee, voucher). | M |
| FR-RES-028 | The system shall support search of reservations by name, confirmation number, channel reference, phone, email, company, dates, status and unit. | M |

### 6.4 Groups, Blocks and Events

| ID | Requirement | Priority |
|---|---|---|
| FR-GRP-001 | The system shall allow creation of group/allotment blocks with contracted units per unit type per date, group rate, cut-off date and release rules. | M |
| FR-GRP-002 | The system shall track block pickup (booked vs. contracted) and wash/attrition. | M |
| FR-GRP-003 | The system shall automatically release unpicked inventory at cut-off date or on a rolling release schedule. | M |
| FR-GRP-004 | The system shall support rooming list import (CSV/Excel) and bulk creation of individual reservations from a block. | M |
| FR-GRP-005 | The system shall support a group master folio with routing rules (e.g., room and tax to master, incidentals to guests). | M |
| FR-GRP-006 | The system shall support bulk check-in, bulk unit assignment, bulk key encoding and bulk check-out for groups. | S |
| FR-GRP-007 | The system shall support wholesaler / tour-operator allotments with rolling releases and separate statements. | S |
| FR-GRP-008 | The system shall support booking of function/meeting spaces by time slot, with setup style, capacity and associated catering items posted to the group folio. | C |
| FR-GRP-009 | The system shall support exclusive-use / buyout bookings that block an entire property or area. | S |
| FR-GRP-010 | The system shall support group contracts with deposit schedules and attrition clauses, and reminders for due deposits. | S |

### 6.5 Distribution: Booking Engine and Channel Management

| ID | Requirement | Priority |
|---|---|---|
| FR-DST-001 | The system shall provide (or integrate with) a direct booking engine with real-time availability, rate display, add-on upsell, payment capture and confirmation. | M |
| FR-DST-002 | The booking engine shall be mobile-responsive, multilingual, multi-currency in display, and accessible (WCAG 2.2 AA). | M |
| FR-DST-003 | The booking engine shall support promo codes, corporate codes, member login and guest account for managing bookings. | S |
| FR-DST-004 | The booking engine shall support booking dorm beds, whole units, pitches and hourly slots according to unit-type time grain. | M |
| FR-DST-005 | The system shall integrate with channel managers and/or directly with OTAs to push availability, rates and restrictions and receive reservations, modifications and cancellations in near real time. | M |
| FR-DST-006 | The system shall map local unit types and rate plans to channel products and flag unmapped or failed items. | M |
| FR-DST-007 | The system shall support virtual card (VCC) handling for OTA-collected payments, including activation date and amount. | S |
| FR-DST-008 | The system shall track OTA commissions per reservation and support commission reports. | S |
| FR-DST-009 | The system shall provide a channel message log showing every outbound update and inbound reservation with success/failure status, and allow re-sync. | M |
| FR-DST-010 | The system shall support GDS connectivity through an intermediary for corporate travel. | C |
| FR-DST-011 | The system shall support metasearch feeds (price and availability) via integration. | C |
| FR-DST-012 | The system shall support an embeddable widget and deep-link URLs with pre-filled search parameters and tracking (UTM) attribution. | S |
| FR-DST-013 | The system shall handle inbound reservations for unavailable inventory (overbooking from channel delay) by accepting them, flagging the conflict and alerting staff. | M |

### 6.6 Guest Profiles and CRM

| ID | Requirement | Priority |
|---|---|---|
| FR-GST-001 | The system shall maintain guest profiles with personal details, contact information, address, nationality, language, date of birth and identity documents. | M |
| FR-GST-002 | The system shall maintain company, travel agent, group and owner profiles, linked to individual guest profiles. | M |
| FR-GST-003 | The system shall store guest preferences (unit features, pillow type, dietary needs, accessibility needs) and display them at booking and check-in. | M |
| FR-GST-004 | The system shall show stay history, total spend, cancellations, no-shows and reviews per profile. | M |
| FR-GST-005 | The system shall support VIP levels and guest flags (e.g., VIP, repeat guest, do-not-rent/blacklist with reason and approval). | M |
| FR-GST-006 | The system shall detect and merge duplicate profiles with audit trail, preserving history. | S |
| FR-GST-007 | The system shall record marketing and data-processing consents per channel with timestamp and source. | M |
| FR-GST-008 | The system shall support data-subject requests: export, rectification, anonymization/erasure, subject to legal retention rules for financial and police records. | M |
| FR-GST-009 | The system shall support segmentation and export of guest lists to CRM/marketing platforms respecting consent. | S |
| FR-GST-010 | The system shall support guest documents storage (ID scans, signed registration cards, contracts) with access restrictions and retention policies. | S |
| FR-GST-011 | The system shall record guest feedback and complaints with category, severity, owner, resolution and compensation. | S |

### 6.7 Front Desk Operations: Arrival, Stay and Departure

| ID | Requirement | Priority |
|---|---|---|
| FR-FDO-001 | The system shall display arrivals, in-house and departures lists for the business date with filters (VIP, group, unit status, balance due, ETA). | M |
| FR-FDO-002 | The system shall support check-in validating: unit assignment, unit ready status, guarantee/payment, required guest data, ID document capture and age rules. | M |
| FR-FDO-003 | The system shall support early check-in and late check-out with optional fees and availability check. | M |
| FR-FDO-004 | The system shall capture registration cards with digital signature (on tablet or guest device) and store them as documents. | S |
| FR-FDO-005 | The system shall support ID/passport scanning with data extraction into the profile. | S |
| FR-FDO-006 | The system shall support pre-authorization of a payment card for incidentals at check-in. | M |
| FR-FDO-007 | The system shall support issuing keys (physical, RFID card, PIN code, mobile key) as part of check-in via lock integration. | S |
| FR-FDO-008 | The system shall support stay extensions and early departures with automatic re-pricing and policy-based fees. | M |
| FR-FDO-009 | The system shall support check-out with folio review, settlement, invoice issuance, key deactivation and unit status change to dirty/vacant. | M |
| FR-FDO-010 | The system shall support express check-out (automatic settlement to card on file, emailed invoice). | S |
| FR-FDO-011 | The system shall prevent check-out with an outstanding balance unless transferred to city ledger or authorized by a manager. | M |
| FR-FDO-012 | The system shall support guest messages, wake-up calls and task reminders for in-house guests. | S |
| FR-FDO-013 | The system shall support a lost & found register (item, location, finder, date, guest match, return/disposal). | S |
| FR-FDO-014 | The system shall support a shift handover log and cash drawer opening/closing per user with variance reporting. | M |
| FR-FDO-015 | The system shall support guest locator and occupant lists (who is in which unit) for safety and emergency evacuation reports. | M |
| FR-FDO-016 | The system shall support a "tape chart" / timeline view of units vs. dates with drag-and-drop to move, extend or shorten stays. | M |

### 6.8 Unit Assignment and Room Moves

| ID | Requirement | Priority |
|---|---|---|
| FR-ASN-001 | The system shall allow manual assignment of a specific unit to a reserved unit line at any time before or during check-in. | M |
| FR-ASN-002 | The system shall provide automatic assignment based on configurable rules: unit type, guest preferences, VIP, accessibility, length of stay, housekeeping readiness, minimizing gaps, keeping groups together. | S |
| FR-ASN-003 | The system shall support bed assignment in dorms, respecting gender restrictions and keeping a party together when possible. | M |
| FR-ASN-004 | The system shall support pitch assignment honoring vehicle size and hookup requirements. | S |
| FR-ASN-005 | The system shall support upgrades (free or paid) with reason codes and optional price change. | M |
| FR-ASN-006 | The system shall support in-house room moves, transferring the folio, updating housekeeping status of both units and re-encoding keys. | M |
| FR-ASN-007 | The system shall allow locking a unit assignment ("do not move") for guests who requested a specific unit. | M |
| FR-ASN-008 | The system shall warn when an assigned unit becomes out of order and propose alternatives. | M |

### 6.9 Housekeeping

| ID | Requirement | Priority |
|---|---|---|
| FR-HSK-001 | The system shall maintain unit housekeeping status: clean, dirty, inspected, in progress, out of order, out of service, and front-office status: vacant, occupied, due out, arrival. | M |
| FR-HSK-002 | The system shall generate daily cleaning tasks automatically by task type: departure clean, stay-over clean, turndown, deep clean, linen change, inspection. | M |
| FR-HSK-003 | The system shall support configurable cleaning frequency per unit type or rate plan (daily, every N days, weekly for long stays, on request, opt-out for eco programs). | M |
| FR-HSK-004 | The system shall support assignment of tasks to housekeepers by section, with workload balancing based on credits/standard minutes per task type. | S |
| FR-HSK-005 | The system shall provide a mobile interface for housekeepers to view tasks, start/finish cleaning, report issues with photos and update status in real time. | M |
| FR-HSK-006 | The system shall support inspection checklists and pass/fail outcomes before a unit becomes inspected/ready. | S |
| FR-HSK-007 | The system shall prioritize cleaning of units with early arrivals or VIP arrivals. | S |
| FR-HSK-008 | The system shall support do-not-disturb, service refused and sleep-out reporting, raising alerts for discrepancies. | S |
| FR-HSK-009 | The system shall support housekeeping discrepancy reports comparing housekeeping status with front-office status (skips and sleepers). | S |
| FR-HSK-010 | The system shall support minibar and consumption posting from the housekeeping device to the guest folio. | S |
| FR-HSK-011 | The system shall support turnover scheduling for dispersed units (vacation rentals) with routes, cleaner/vendor assignment, travel times and cleaning fees payable to vendors. | S |
| FR-HSK-012 | The system shall support linen and amenity inventory tracking per unit or per floor/store. | C |
| FR-HSK-013 | The system shall support bed-level status within shared rooms (bed stripped, made). | S |
| FR-HSK-014 | The system shall report housekeeping productivity (units cleaned per attendant, average time, inspection failures). | S |

### 6.10 Maintenance and Asset Management

| ID | Requirement | Priority |
|---|---|---|
| FR-MNT-001 | The system shall allow any user (and optionally guests) to raise a maintenance request linked to a unit or public area, with category, priority, description and photos. | M |
| FR-MNT-002 | The system shall manage work orders through statuses (open, assigned, in progress, on hold, completed, verified) with SLA timers by priority. | M |
| FR-MNT-003 | The system shall allow placing a unit out of order (removing from inventory) or out of service for a date range with reason, linked to a work order, and alert affected reservations. | M |
| FR-MNT-004 | The system shall support preventive maintenance schedules per asset or unit (e.g., HVAC filter every 90 days, deep clean quarterly). | S |
| FR-MNT-005 | The system shall maintain an asset register (asset type, location, serial, warranty, vendor, installation date). | C |
| FR-MNT-006 | The system shall record parts used, labour time and cost per work order. | C |
| FR-MNT-007 | The system shall support external vendor assignment for work orders, important for dispersed and owner-managed units. | S |
| FR-MNT-008 | The system shall support recharging maintenance costs to unit owners (see 6.20) or to guests for damages. | S |
| FR-MNT-009 | The system shall integrate with IoT/building systems to raise work orders automatically from sensor alerts (leak, temperature, energy). | C |

### 6.11 Folios, Billing and Charges

| ID | Requirement | Priority |
|---|---|---|
| FR-BIL-001 | The system shall create at least one folio per reservation automatically and support multiple folios (windows) per reservation. | M |
| FR-BIL-002 | The system shall automatically post accommodation charges and package components per night (or per time grain) during end-of-day. | M |
| FR-BIL-003 | The system shall allow manual posting of charges using configurable transaction codes mapped to departments, revenue categories, tax rules and GL accounts. | M |
| FR-BIL-004 | The system shall support routing instructions per transaction code and date range (e.g., accommodation to company folio, everything else to guest). | M |
| FR-BIL-005 | The system shall support transfers of charges between folios, reservations and the city ledger, with audit trail. | M |
| FR-BIL-006 | The system shall support adjustments, corrections and voids with reason codes; voids allowed only on the same business date and adjustments thereafter. | M |
| FR-BIL-007 | The system shall support splitting a charge by amount or percentage across folios. | S |
| FR-BIL-008 | The system shall support recurring charges (daily parking, pet fee, equipment rental) with start and end dates. | M |
| FR-BIL-009 | The system shall support package allowances and over/under tracking (e.g., breakfast allowance consumed at outlet). | S |
| FR-BIL-010 | The system shall support posting from external POS systems to the guest folio by unit number/guest name, with credit limit checks. | M |
| FR-BIL-011 | The system shall support credit limits per reservation and alert when exceeded. | S |
| FR-BIL-012 | The system shall support passer-by / non-resident folios for selling services to non-staying customers. | S |
| FR-BIL-013 | The system shall support a "pro forma" folio showing projected charges for the full stay. | M |
| FR-BIL-014 | The system shall support multi-currency display of folios using configured exchange rates while keeping the base currency of record. | S |
| FR-BIL-015 | The system shall support damage and security deposit handling separate from revenue. | S |

### 6.12 Payments, Deposits and Refunds

| ID | Requirement | Priority |
|---|---|---|
| FR-PAY-001 | The system shall support payment methods: cash, card (present and not present), bank transfer, digital wallets, vouchers/gift cards, loyalty points, direct bill, OTA virtual card, and local methods configured per country. | M |
| FR-PAY-002 | The system shall integrate with payment gateways using tokenization so that no full card number is stored in the PMS (PCI DSS scope reduction). | M |
| FR-PAY-003 | The system shall support pre-authorization, incremental authorization, capture, release and reversal. | M |
| FR-PAY-004 | The system shall support payment links sent by email/SMS/messaging for deposits and balances. | M |
| FR-PAY-005 | The system shall support scheduled payments and deposit due dates with automatic charge attempts and reminders, and flag reservations with overdue deposits. | M |
| FR-PAY-006 | The system shall support refunds to the original payment method (full/partial), with permission-based approval thresholds. | M |
| FR-PAY-007 | The system shall support 3-D Secure / strong customer authentication where required. | M |
| FR-PAY-008 | The system shall record deposits as liabilities until the stay is consumed, and transfer them to the folio on check-in or per configuration. | M |
| FR-PAY-009 | The system shall support card-present terminals integrated with the PMS (amount pushed to terminal, result returned). | S |
| FR-PAY-010 | The system shall support cash handling with foreign currency acceptance and change in base currency. | S |
| FR-PAY-011 | The system shall support chargeback recording, evidence pack export (registration card, signature, folio, communications) and status tracking. | S |
| FR-PAY-012 | The system shall reconcile payments with gateway settlement reports. | S |

### 6.13 Taxes, Fees and Invoicing

| ID | Requirement | Priority |
|---|---|---|
| FR-TAX-001 | The system shall support multiple taxes per transaction code: percentage, fixed per unit, fixed per person per night, tiered by price or length of stay, inclusive or exclusive. | M |
| FR-TAX-002 | The system shall support tourist/city taxes with exemptions (age, residency, business travel, length of stay caps) and generate tourist tax returns. | M |
| FR-TAX-003 | The system shall support tax rule changes effective from a date, applying the correct rate based on the stay date. | M |
| FR-TAX-004 | The system shall support long-stay tax exemptions (e.g., stays beyond N consecutive nights exempt from occupancy tax, applied retroactively if required). | S |
| FR-TAX-005 | The system shall issue invoices/receipts with sequential numbering per legal entity/property, without gaps, according to local fiscal rules. | M |
| FR-TAX-006 | The system shall support credit notes to correct issued invoices; issued invoices shall be immutable. | M |
| FR-TAX-007 | The system shall support invoices addressed to a company with tax ID, and changing invoice addressee before issuance. | M |
| FR-TAX-008 | The system shall support e-invoicing / fiscal device integration where legally mandated. | S |
| FR-TAX-009 | The system shall support configurable invoice templates per language and legal entity. | M |
| FR-TAX-010 | The system shall support deposit invoices and final invoices that net off deposits. | S |

### 6.14 Accounts Receivable and City Ledger

| ID | Requirement | Priority |
|---|---|---|
| FR-ARL-001 | The system shall maintain AR accounts for companies, agents, groups, OTAs and owners, with credit limits and payment terms. | M |
| FR-ARL-002 | The system shall allow transferring folio balances at check-out to an approved AR account. | M |
| FR-ARL-003 | The system shall generate AR invoices and statements, with aging (current, 30, 60, 90+). | M |
| FR-ARL-004 | The system shall record payments against AR invoices, including partial payments and unallocated receipts. | M |
| FR-ARL-005 | The system shall support dunning reminders by email based on aging rules. | S |
| FR-ARL-006 | The system shall support commission payable statements for travel agents. | S |
| FR-ARL-007 | The system shall support write-offs with approval. | S |

### 6.15 Night Audit and End-of-Day

| ID | Requirement | Priority |
|---|---|---|
| FR-AUD-001 | The system shall maintain a business date per property that only advances when the end-of-day process completes. | M |
| FR-AUD-002 | The end-of-day process shall run pre-checks: arrivals not checked in, departures not checked out, unbalanced cash drawers, pending interface postings, open OOO without end dates. | M |
| FR-AUD-003 | The end-of-day process shall post room and package charges, recurring charges and taxes for all in-house reservations. | M |
| FR-AUD-004 | The end-of-day process shall handle no-shows according to policy (mark no-show, post fee, charge guarantee, release inventory). | M |
| FR-AUD-005 | The end-of-day process shall generate and archive a standard report pack (manager's flash, trial balance, revenue by department, payments, in-house list, occupancy statistics). | M |
| FR-AUD-006 | The system shall support fully automated (unattended) end-of-day at a scheduled time for small properties with no night staff. | M |
| FR-AUD-007 | The system shall produce a daily trial balance where opening balance + charges − payments = closing balance across guest ledger, deposit ledger and city ledger. | M |
| FR-AUD-008 | The system shall lock financial postings for closed business dates; corrections shall be made as adjustments on the current date. | M |

### 6.16 Long-Stay, Residential and Lease Management

| ID | Requirement | Priority |
|---|---|---|
| FR-LNG-001 | The system shall support long-stay reservations/leases with start date, end date or open-ended term, notice period and renewal options. | M (SAP, CLV) |
| FR-LNG-002 | The system shall support recurring billing cycles (weekly, monthly, custom) with pro-rating for partial periods. | M (SAP, CLV) |
| FR-LNG-003 | The system shall generate periodic invoices automatically and attempt auto-payment from stored payment methods. | M (SAP, CLV) |
| FR-LNG-004 | The system shall support lease contracts generated from templates with e-signature. | S |
| FR-LNG-005 | The system shall support security deposits held for the term, with deductions and refund at move-out. | M (SAP, CLV) |
| FR-LNG-006 | The system shall support utility metering (electricity, water, gas) by reading entry or meter integration, and bill consumption to the resident. | S (SAP, CLV, CMP) |
| FR-LNG-007 | The system shall support move-in and move-out inspections with checklist, photos and condition report. | S |
| FR-LNG-008 | The system shall support resident maintenance requests via the guest portal. | S |
| FR-LNG-009 | The system shall support seasonal pitch contracts for campsites (fixed pitch for a season, pricing per season). | S (CMP) |
| FR-LNG-010 | The system shall support academic-term contracts and bed-level leases for student/co-living housing. | C (CLV) |
| FR-LNG-011 | The system shall support mail/parcel logging and notification for residents. | C |

### 6.17 Ancillary Services: F&B, Spa, Activities and Rentals

| ID | Requirement | Priority |
|---|---|---|
| FR-ANC-001 | The system shall define outlets/departments (restaurant, bar, spa, shop, activities desk) with their own transaction codes. | M |
| FR-ANC-002 | The system shall provide a lightweight built-in POS for small properties (breakfast, bar, shop) that posts to folios or takes direct payment. | S |
| FR-ANC-003 | The system shall support bookable services with time slots and capacity (spa treatments, tours, classes, airport transfers) linked to guests and folios. | S |
| FR-ANC-004 | The system shall support upselling of add-ons before arrival and during stay (pre-arrival emails, booking engine, guest app). | S |
| FR-ANC-005 | The system shall support breakfast/meal-plan lists for kitchens and outlets (who is entitled to which meal on which date). | M |
| FR-ANC-006 | The system shall support all-inclusive entitlements and wristband/credential identification of eligible guests. | C (RES) |
| FR-ANC-007 | The system shall support equipment rental tracking with deposit and return (bikes, kayaks, BBQ). | C |
| FR-ANC-008 | The system shall support gift cards / vouchers sold online and redeemed for stays or services. | S |

### 6.18 Guest Self-Service and Communication

| ID | Requirement | Priority |
|---|---|---|
| FR-GSS-001 | The system shall provide a guest web portal (no app install required) to view and manage the reservation, pay balances and request services. | M |
| FR-GSS-002 | The system shall support online pre-check-in: collect guest details, ID document, arrival time, signature, payment and policy acceptance. | M |
| FR-GSS-003 | The system shall support online check-out with folio review and payment. | S |
| FR-GSS-004 | The system shall support self-check-in kiosks and contactless arrival (code or mobile key delivered after pre-check-in). | S |
| FR-GSS-005 | The system shall send automated, templated, multilingual communications triggered by lifecycle events (confirmation, pre-arrival, check-in instructions, in-stay, post-stay, review request). | M |
| FR-GSS-006 | The system shall provide a unified inbox for guest messages across email, SMS and messaging apps, linked to the reservation. | S |
| FR-GSS-007 | The system shall support a digital guest guide (house rules, Wi-Fi, directions, local tips) per property and unit. | S |
| FR-GSS-008 | The system shall support guest service requests (extra towels, late checkout, maintenance issue) converted into tasks. | S |
| FR-GSS-009 | The system shall support post-stay surveys and review request links, and import of public review scores. | S |
| FR-GSS-010 | The system shall allow guests to opt out of non-essential messages while still receiving transactional messages. | M |
| FR-GSS-011 | The system shall support AI-assisted reply suggestions and FAQ automation for guest messages, with human review for policy-sensitive actions. | C |

### 6.19 Access Control and Keys

| ID | Requirement | Priority |
|---|---|---|
| FR-ACC-001 | The system shall integrate with electronic lock systems to issue, duplicate and cancel keys (RFID cards, mobile keys). | S |
| FR-ACC-002 | The system shall generate time-bound PIN codes for keypad locks (vacation rentals, cabins, self-check-in), valid from check-in to check-out time. | S |
| FR-ACC-003 | The system shall automatically revoke access at check-out, cancellation or room move. | S |
| FR-ACC-004 | The system shall support access rights to common areas (gym, pool, parking, floors) based on reservation or rate plan. | C |
| FR-ACC-005 | The system shall issue temporary codes to cleaners and vendors linked to their task window. | C |
| FR-ACC-006 | The system shall log every key/code issuance with user and timestamp. | S |

### 6.20 Owner and Third-Party Management

| ID | Requirement | Priority |
|---|---|---|
| FR-OWN-001 | The system shall link units to one or more owners with ownership percentage and effective dates. | M (VRM, CDH) |
| FR-OWN-002 | The system shall support management agreement types: commission on revenue, fixed fee, revenue share, rental pool distribution, guaranteed rent. | M (VRM, CDH) |
| FR-OWN-003 | The system shall support owner stays, friend-of-owner stays and owner blocks, with configured limits and fee rules. | M (VRM, CDH) |
| FR-OWN-004 | The system shall calculate owner revenue per period, allocating accommodation revenue, deducting commissions, cleaning fees, maintenance, OTA commissions and other expenses per agreement. | M (VRM, CDH) |
| FR-OWN-005 | The system shall support rental pool calculations (pooled revenue distributed by points, unit size or nights available). | S (CDH) |
| FR-OWN-006 | The system shall generate owner statements with detailed lines and attachments (expense receipts), and record payouts. | M (VRM, CDH) |
| FR-OWN-007 | The system shall provide an owner portal showing bookings, occupancy, revenue, statements and the ability to request owner blocks. | S |
| FR-OWN-008 | The system shall support owner tax reporting exports. | C |
| FR-OWN-009 | The system shall support trust/escrow accounting for guest funds held before the stay where legally required. | S (VRM) |

### 6.21 Multi-Property and Chain Management

| ID | Requirement | Priority |
|---|---|---|
| FR-MPR-001 | The system shall allow a single user login with access to multiple properties based on role. | M |
| FR-MPR-002 | The system shall support central configuration (rate plans, transaction codes, templates, policies) with property-level inheritance and overrides. | S |
| FR-MPR-003 | The system shall support central reservations: search availability across properties and book any property from one screen. | S |
| FR-MPR-004 | The system shall maintain a shared guest profile across properties, subject to data-sharing rules per legal entity. | S |
| FR-MPR-005 | The system shall provide consolidated portfolio reporting across properties and currencies. | S |
| FR-MPR-006 | The system shall support multiple legal entities with separate invoicing sequences, tax IDs and financial exports. | M |
| FR-MPR-007 | The system shall support cross-property transfers of guests and folio balances. | C |

### 6.22 Loyalty and Memberships

| ID | Requirement | Priority |
|---|---|---|
| FR-LOY-001 | The system shall support membership enrollment and tiers with qualification rules (nights, stays, spend). | C |
| FR-LOY-002 | The system shall accrue points per eligible revenue and support redemption for stays or services. | C |
| FR-LOY-003 | The system shall display member benefits at booking and check-in (upgrade eligibility, late checkout, welcome amenity). | C |
| FR-LOY-004 | The system shall integrate with external loyalty platforms. | C |

### 6.23 Revenue Management Support

| ID | Requirement | Priority |
|---|---|---|
| FR-RMS-001 | The system shall provide on-the-books data (by date, unit type, rate plan, segment, channel) and pickup since a reference date. | M |
| FR-RMS-002 | The system shall provide historical occupancy, ADR, RevPAR and booking pace reports, and same-time-last-year comparisons. | M |
| FR-RMS-003 | The system shall export reservation, cancellation and inventory data to an external RMS on schedule or by event stream. | S |
| FR-RMS-004 | The system shall support budget and forecast entry per month/segment and compare actuals against them. | S |
| FR-RMS-005 | The system shall support competitor rate import and display alongside own rates. | C |
| FR-RMS-006 | The system shall record denials/regrets (requests that could not be fulfilled) and lost business with reasons. | S |

### 6.24 Reporting and Analytics

| ID | Requirement | Priority |
|---|---|---|
| FR-RPT-001 | The system shall provide a standard report library covering operations (arrivals, departures, in-house, housekeeping), finance (revenue, payments, ledger balances, taxes), sales (production by source, segment, company, agent) and statistics (occupancy, ADR, RevPAR, ALOS). | M |
| FR-RPT-002 | Occupancy statistics shall be calculable per unit, per bed (hostels), per pitch, and per available hour (day-use), and exclude non-sellable/OOO units according to configurable rules. | M |
| FR-RPT-003 | The system shall provide role-based dashboards with KPIs for the current day, month-to-date and year-to-date. | M |
| FR-RPT-004 | The system shall support report filters, sorting, grouping, and export to PDF, CSV and Excel. | M |
| FR-RPT-005 | The system shall support scheduled report delivery by email. | S |
| FR-RPT-006 | The system shall support a custom report builder over a documented data model. | S |
| FR-RPT-007 | The system shall provide data warehouse/BI connectivity (read replica, export, or event stream). | S |
| FR-RPT-008 | The system shall support total-revenue metrics (TRevPAR, GOPPAR inputs, ancillary revenue per guest). | C |
| FR-RPT-009 | The system shall produce government statistical returns (tourism statistics by nationality, arrivals, nights). | S |

### 6.25 Users, Security and Audit

| ID | Requirement | Priority |
|---|---|---|
| FR-SEC-001 | The system shall support role-based access control with granular permissions per function and per property. | M |
| FR-SEC-002 | The system shall support configurable approval thresholds (discounts, refunds, rate overrides, write-offs) with manager override via credentials. | M |
| FR-SEC-003 | The system shall support SSO (SAML/OIDC) and multi-factor authentication. | S |
| FR-SEC-004 | The system shall log every create/update/delete of business data and every sensitive view (e.g., ID document, full guest data export) with user, time, IP/device and before/after values. | M |
| FR-SEC-005 | The system shall mask sensitive data by role (ID numbers, contact details, card data). | M |
| FR-SEC-006 | The system shall support session timeout, password policies and account lockout. | M |
| FR-SEC-007 | The system shall support temporary/seasonal staff accounts with expiry dates. | S |
| FR-SEC-008 | The system shall support device-based restrictions (e.g., cash functions only on front desk terminals). | C |

### 6.26 Regulatory and Compliance

| ID | Requirement | Priority |
|---|---|---|
| FR-CMP-001 | The system shall support guest registration requirements per jurisdiction (mandatory fields by nationality) and electronic submission to police/immigration portals where available. | M |
| FR-CMP-002 | The system shall comply with data protection laws (e.g., GDPR, PDPA, CCPA): lawful basis tracking, consent, retention schedules, right to access and erasure. | M |
| FR-CMP-003 | The system shall support PCI DSS-compliant payment handling through tokenization and hosted payment fields. | M |
| FR-CMP-004 | The system shall support short-term rental registration numbers and night caps per unit where local regulations limit rental days per year, and block bookings beyond the cap. | S (VRM) |
| FR-CMP-005 | The system shall support fiscal compliance (invoice numbering, fiscal printers, e-invoicing, tax reports) per country. | M |
| FR-CMP-006 | The system shall support accessibility information for units and accessible booking flows. | M |
| FR-CMP-007 | The system shall support fire safety and occupancy limits per unit and per property, preventing over-occupancy. | M |
| FR-CMP-008 | The system shall support configurable data retention and automated anonymization after the legal period. | M |

### 6.27 Integrations and APIs

| ID | Requirement | Priority |
|---|---|---|
| FR-INT-001 | The system shall expose a documented, versioned REST (or GraphQL) API covering inventory, rates, reservations, profiles, folios, housekeeping and reports. | M |
| FR-INT-002 | The system shall emit webhooks/events for key lifecycle events (reservation created/modified/cancelled, check-in, check-out, folio posted, unit status changed). | M |
| FR-INT-003 | The system shall integrate with: channel managers/OTAs, payment gateways, POS, door locks, accounting/ERP, RMS, CRM, messaging providers, kiosk, telephone/PBX, Wi-Fi portals, ID scanners, government portals. | M (core set) / S (others) |
| FR-INT-004 | The system shall support industry standards where applicable (e.g., HTNG/OpenTravel messages). | S |
| FR-INT-005 | The system shall provide a GL export mapping transaction codes to accounting accounts, by day, with journals that balance. | M |
| FR-INT-006 | The system shall support data import for onboarding (units, profiles, future reservations, open balances) with validation reports. | M |
| FR-INT-007 | The system shall support an integration marketplace or app framework with OAuth-scoped access for third parties. | C |
| FR-INT-008 | The system shall monitor integration health and alert administrators of failures. | M |

### 6.28 Configuration, Localization and Notifications

| ID | Requirement | Priority |
|---|---|---|
| FR-CFG-001 | The system shall support multiple UI and guest-facing languages, including right-to-left scripts. | M |
| FR-CFG-002 | The system shall support local date, time, number and address formats and multiple currencies. | M |
| FR-CFG-003 | The system shall allow configuration of codes: market segments, sources, reason codes, transaction codes, cancellation reasons, VIP levels, preferences. | M |
| FR-CFG-004 | The system shall allow configuration of communication and document templates with merge fields and conditional sections. | M |
| FR-CFG-005 | The system shall allow configuration of custom fields on reservations, profiles and units. | S |
| FR-CFG-006 | The system shall provide in-app and push notifications for operational events (VIP arrival, overdue deposit, OOO unit with arrival, integration failure). | S |
| FR-CFG-007 | The system shall allow configuration of workflows/automation rules ("when X then Y") without code. | C |

### 6.29 Business Continuity and Offline Operation

| ID | Requirement | Priority |
|---|---|---|
| FR-BCP-001 | The system shall generate and automatically distribute downtime reports (arrivals, in-house, balances, unit status) at a scheduled interval for use during outages. | M |
| FR-BCP-002 | The system shall support limited offline operation on front desk and housekeeping devices with synchronization on reconnect, for remote properties. | C (LDG, CMP) |
| FR-BCP-003 | The system shall support backdated entry of transactions that occurred during an outage, flagged for audit. | S |

---

## 7. Key Business Rules

| ID | Rule |
|---|---|
| BR-01 | Availability for a unit type on a date = sellable units − (sold + blocked + OOO) + permitted overbooking. Out-of-service units remain sellable. |
| BR-02 | Selling a parent unit (whole villa) makes all child units unavailable for the overlapping period, and selling any child makes the parent unavailable. |
| BR-03 | For hourly time grain, a unit cannot be booked within the configured turnaround buffer after a previous booking ends. |
| BR-04 | A reservation's price is calculated per date using the rate valid for the stay date at time of booking; later rate changes do not affect confirmed bookings unless the booking is modified and the price is not locked. |
| BR-05 | Restrictions are evaluated against the arrival date (CTA, min advance), departure date (CTD) and each stay date (stop-sell, min/max stay through). |
| BR-06 | Cancellation fees are calculated according to the policy attached at booking time, using the property's local time. |
| BR-07 | A unit can be checked into only if its front-office status is vacant and housekeeping status meets the property's readiness rule (clean or inspected). Managers may override with a reason. |
| BR-08 | Posted transactions are never deleted. Same-day voids are allowed with permission; prior-day corrections are adjustments. |
| BR-09 | Issued invoices are immutable; corrections require a credit note and a new invoice. |
| BR-10 | Folio balance must be zero at check-out unless transferred to an AR account or approved by a manager. |
| BR-11 | Guest data subject to legal retention (police registration, invoices) is retained for the legal period even when an erasure request is received; other data is anonymized. |
| BR-12 | Occupancy limits (max adults, children, total) per unit type cannot be exceeded without manager override, and never beyond the fire-safety limit. |
| BR-13 | Owner blocks and owner stays reduce availability but are excluded from revenue statistics; whether they count in occupancy is configurable. |
| BR-14 | Deposits are liabilities until the corresponding service date or check-in; forfeited deposits become revenue on cancellation per policy. |
| BR-15 | All date logic uses the property's time zone and business date. |

---

## 8. State Models

### 8.1 Reservation Status

```
Enquiry/Quote ──► Tentative (expires) ──► Confirmed ──► Guaranteed ──► Checked-in ──► Checked-out
      │                 │                     │              │              │
      └──► Expired      └──► Released         ├──► Cancelled ┤              └──► (Early departure → Checked-out)
                                              └──► No-show ◄─┘
Waitlisted ──► Confirmed (when inventory frees) / Cancelled
```

### 8.2 Unit Status (two independent dimensions)

| Front-office status | Housekeeping status |
|---|---|
| Vacant | Dirty → In progress → Clean → Inspected |
| Occupied | Dirty / Clean (stay-over) |
| Due out / Due in | — |
| Out of Order (no sale) | Linked to work order |
| Out of Service (sale allowed, not preferred) | Linked to work order |

### 8.3 Work Order Status

`Open → Assigned → In progress → (On hold) → Completed → Verified/Closed`

### 8.4 Lease Status (long stay)

`Draft → Signed → Active → Notice given → Ended → Settled`

---

## 9. Property-Type Applicability Matrix

✔ = core · ○ = optional · — = not usually needed

| Module | HTL | RES | SAP | HST | BNB | VRM | CMP | CDH | CLV | LDG |
|---|---|---|---|---|---|---|---|---|---|---|
| Inventory: room-level units | ✔ | ✔ | ✔ | ○ | ✔ | ✔ | ○ | ✔ | ✔ | ✔ |
| Inventory: bed-level | — | — | — | ✔ | — | — | — | — | ✔ | ○ |
| Inventory: pitches/plots | — | ○ | — | — | — | — | ✔ | — | — | ○ |
| Combinable units | ○ | ✔ | ○ | ○ | ○ | ✔ | — | ○ | ○ | ○ |
| Hourly / day-use | ○ | ○ | — | — | — | — | — | — | — | — |
| Groups & blocks | ✔ | ✔ | ○ | ✔ | ○ | ○ | ○ | ○ | ○ | ○ |
| Channel management | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ○ | ✔ |
| Front desk | ✔ | ✔ | ✔ | ✔ | ✔ | ○ | ✔ | ✔ | ○ | ✔ |
| Self check-in / digital keys | ○ | ○ | ✔ | ○ | ○ | ✔ | ○ | ○ | ✔ | ○ |
| Housekeeping (on-site) | ✔ | ✔ | ✔ | ✔ | ✔ | — | ○ | ✔ | ○ | ✔ |
| Turnover scheduling (dispersed) | — | ○ | — | — | — | ✔ | — | ○ | — | ○ |
| Long-stay / leases | ○ | — | ✔ | ○ | — | ○ | ○ | — | ✔ | — |
| Utility metering | — | — | ○ | — | — | ○ | ✔ | — | ✔ | — |
| Ancillary POS / services | ✔ | ✔ | ○ | ✔ | ○ | ○ | ✔ | ○ | ○ | ✔ |
| All-inclusive entitlements | — | ✔ | — | — | — | — | — | — | — | ○ |
| Owner management | — | ○ | ○ | — | — | ✔ | ○ | ✔ | ○ | ○ |
| Night audit (attended) | ✔ | ✔ | ○ | ○ | — | — | ○ | ✔ | — | ○ |
| Night audit (automatic) | ○ | ○ | ✔ | ✔ | ✔ | ✔ | ✔ | ○ | ✔ | ✔ |
| Offline operation | — | ○ | — | — | — | — | ○ | — | — | ✔ |

---

## 10. Non-Functional Requirements (Summary)

Functional scope is the focus of this document; the following NFRs constrain how functions are delivered.

| ID | Category | Requirement |
|---|---|---|
| NFR-01 | Availability | Core reservation and front desk functions available 99.9% monthly; planned maintenance outside peak check-in/check-out hours. |
| NFR-02 | Performance | Availability search < 1 s (p95) for a single property; check-in transaction < 2 s; channel updates dispatched < 30 s after change. |
| NFR-03 | Scalability | Support from 1 to 5,000+ units per property and 1,000+ properties per organization. |
| NFR-04 | Concurrency | Inventory updates must be transactionally safe to prevent double booking under concurrent channel and staff bookings. |
| NFR-05 | Security | Encryption in transit (TLS 1.2+) and at rest; OWASP ASVS L2; annual penetration testing. |
| NFR-06 | Data residency | Configurable hosting region to meet local data residency laws. |
| NFR-07 | Backup & recovery | RPO ≤ 15 minutes, RTO ≤ 4 hours. |
| NFR-08 | Usability | Mobile-first housekeeping and maintenance UIs; front desk tasks completable in ≤ 3 screens for standard check-in. |
| NFR-09 | Accessibility | Guest-facing interfaces conform to WCAG 2.2 AA. |
| NFR-10 | Auditability | Audit logs immutable and retained per policy (default 7 years for financial data). |
| NFR-11 | Interoperability | Public API with versioning and at least 12 months deprecation notice. |

---

## 11. Assumptions, Constraints and Open Questions

### 11.1 Assumptions

- The PMS is cloud-hosted (SaaS) and multi-tenant, with web and mobile clients.
- Card payments are processed by an external PCI-certified gateway.
- Full accounting is done in an external system receiving daily GL exports.
- Revenue optimization algorithms live in an external RMS; the PMS offers rule-based pricing only.

### 11.2 Constraints

- Fiscal and police-registration rules differ by country and require localized modules.
- OTA connectivity depends on partner certification and their API limits.
- Lock integration depends on vendor support for cloud APIs.

### 11.3 Open Questions

| # | Question | Impact |
|---|---|---|
| Q1 | Which countries/jurisdictions are in scope for the first release (determines fiscal, tax and police-registration modules)? | FR-TAX, FR-CMP |
| Q2 | Will the built-in booking engine be required, or will a third-party engine be integrated? | FR-DST |
| Q3 | Which property types are in the first target segment (drives MVP prioritization of bed-level, pitch, lease and owner modules)? | Section 9 |
| Q4 | Is a built-in POS required, or only interfaces to external POS? | FR-ANC-002 |
| Q5 | Is owner trust accounting required (legal requirement in some regions for vacation rental managers)? | FR-OWN-009 |
| Q6 | What level of offline operation is required for remote properties? | FR-BCP-002 |
| Q7 | Should loyalty be native or always integrated with an external program? | FR-LOY |
| Q8 | What AI features (message drafting, auto-assignment, demand forecasting) are in scope, and what human-approval controls are required? | FR-GSS-011, FR-ASN-002, FR-RMS |

---

*End of document.*
