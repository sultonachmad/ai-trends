# Payments Service — Functional Requirements

> **Document type:** Functional Requirements Specification
> **Scope:** Embedded payment platform used by the PMS, Booking Engine, Guest portal, POS Lite and Channel Manager: tokenisation, authorisations, captures, refunds, payment links, terminals, OTA virtual cards, scheduled payments, reconciliation, chargebacks
> **Positioning:** **Platform service** (Commerce pack). It has no primary user interface of its own beyond settings, reconciliation and dispute screens; other apps call it. Card data is handled by a PCI-certified gateway/acquirer; the service stores tokens only.
> **Priority key:** **M** must · **S** should · **C** could
> **Related:** [Portfolio architecture](hospitality-suite-portfolio-architecture.md) · [PMS §6.12](property-management-system-functional-requirements.md) · [Booking Engine](booking-engine-functional-requirements.md) · [Channel Manager](channel-manager-functional-requirements.md)

---

## 1. Purpose

Take money reliably at every touchpoint, reduce no-show and chargeback losses, keep the property out of PCI scope, and reconcile automatically so the owner's books match the bank.

---

## 2. Actors

| Role | Responsibilities |
|---|---|
| Guest | Pays online, at terminal, via link |
| Front desk / outlet staff | Takes payments, pre-authorises, refunds within limits |
| Finance | Reconciles, manages disputes, refunds above limits |
| Owner / admin | Configures gateways, methods, limits, payout accounts |
| Systems: payment gateways/acquirers, card terminals, wallets, bank transfer providers, PMS, Booking Engine, POS, Channel Manager (VCC), accounting export |

---

## 3. Functional Requirements

### 3.1 Payment Methods and Configuration

| ID | Requirement | Priority |
|---|---|---|
| FR-PAY-001 | The service shall support card-not-present (hosted fields, payment links), card-present (integrated terminals), wallets, bank transfer/open-banking, local methods per country, cash recording, vouchers, and direct-bill as a non-cash settlement. | M |
| FR-PAY-002 | The service shall support multiple gateways/acquirers per organisation and per property, with routing rules (by currency, method, property). | S |
| FR-PAY-003 | The service shall allow configuring which methods are offered per touchpoint (booking engine, portal, front desk, POS). | M |
| FR-PAY-004 | The service shall support surcharge rules where legal, and fee disclosure. | C |

### 3.2 Tokenisation and Security

| ID | Requirement | Priority |
|---|---|---|
| FR-PAY-010 | The service shall store only gateway tokens and masked card data (last four, brand, expiry); full card numbers never enter the platform. | M |
| FR-PAY-011 | The service shall support network tokens / account updater where available to reduce expired-card failures. | S |
| FR-PAY-012 | The service shall support 3-D Secure / strong customer authentication for online payments and exemptions (MIT, low value) where allowed. | M |
| FR-PAY-013 | The service shall support merchant-initiated transactions (MIT) for later charges on stored tokens (no-show fees, incidentals) with proper flagging. | M |
| FR-PAY-014 | The service shall maintain an audit log of every payment operation with user/system, time, amount, result and gateway reference. | M |

### 3.3 Authorisation, Capture and Refund

| ID | Requirement | Priority |
|---|---|---|
| FR-PAY-020 | The service shall support authorise, incremental authorise, capture (partial/full), release, reverse, sale, refund (partial/full, to original method), and void. | M |
| FR-PAY-021 | The service shall track authorisation expiry and alert before incidentals pre-authorisations lapse during long stays, with automatic re-authorisation where configured. | S |
| FR-PAY-022 | The service shall enforce refund approval thresholds by role. | M |
| FR-PAY-023 | The service shall provide idempotent operations keyed by the calling app's reference to prevent duplicate charges. | M |
| FR-PAY-024 | The service shall support multi-currency charging where the acquirer allows, recording settlement currency and rate. | S |

### 3.4 Payment Links and Scheduled Payments

| ID | Requirement | Priority |
|---|---|---|
| FR-PAY-030 | The service shall generate secure payment links with amount, description, expiry, and optional token storage for later charges, deliverable via CRM channels. | M |
| FR-PAY-031 | The service shall support payment schedules (deposit now, balance X days before arrival, instalments) attached to a reservation, with automatic attempts, retries on failure, and notifications. | M |
| FR-PAY-032 | The service shall report overdue scheduled payments to the PMS so reservations can be flagged or auto-cancelled per policy. | M |

### 3.5 Terminals

| ID | Requirement | Priority |
|---|---|---|
| FR-PAY-040 | The service shall integrate card terminals so the amount is pushed from the PMS/POS and the result returned, avoiding manual re-keying. | S |
| FR-PAY-041 | The service shall support tap-to-pay on mobile devices for housekeeping/outlets where available. | C |

### 3.6 OTA Virtual Cards and Channel Settlements

| ID | Requirement | Priority |
|---|---|---|
| FR-PAY-050 | The service shall store OTA virtual card details as tokens with activation date, amount and expiry, and charge them on or after activation per the PMS instruction. | S |
| FR-PAY-051 | The service shall reconcile channel-collect payouts (bank transfers from OTAs) against expected amounts per booking. | S |

### 3.7 Reconciliation and Accounting

| ID | Requirement | Priority |
|---|---|---|
| FR-PAY-060 | The service shall import gateway settlement reports and match transactions, fees and payouts to platform records, flagging exceptions. | M |
| FR-PAY-061 | The service shall provide daily payment summaries per property, method and gateway for the PMS end-of-day pack and GL export. | M |
| FR-PAY-062 | The service shall support cash declarations and bank deposit recording for cash reconciliation. | S |

### 3.8 Disputes and Risk

| ID | Requirement | Priority |
|---|---|---|
| FR-PAY-070 | The service shall receive chargeback notifications, link them to the reservation, assemble an evidence pack (confirmation, policies accepted, registration card, signatures, communications, folio) and track outcome and deadlines. | S |
| FR-PAY-071 | The service shall apply basic risk rules (velocity, mismatched country, high value first booking) to flag bookings for review before charging. | S |
| FR-PAY-072 | The service shall support pre-arrival card validation (zero-value auth) to reduce no-shows on invalid cards. | M |

### 3.9 Administration

| ID | Requirement | Priority |
|---|---|---|
| FR-PAY-080 | The service shall provide a transaction search with filters and export. | M |
| FR-PAY-081 | The service shall support roles for taking payments, refunding within/above limits, and configuring gateways. | M |
| FR-PAY-082 | The service shall monitor gateway health and fail over or alert. | S |

---

## 4. Key Business Rules

| ID | Rule |
|---|---|
| BR-PAY-01 | A refund never exceeds the captured amount of the original transaction. |
| BR-PAY-02 | Every operation is idempotent by caller reference; a repeated request returns the original result. |
| BR-PAY-03 | Stored tokens are used only for the purposes consented to (guarantee, incidentals, scheduled payments) and for the reservation they belong to. |
| BR-PAY-04 | Deposits taken before arrival are reported as liabilities until the stay is consumed. |

---

## 5. AI Assistance (API-based, no model training)

| Area | Assistance |
|---|---|
| Reconciliation | Explain unmatched items in plain language and propose likely matches for human confirmation |
| Disputes | Draft the chargeback response narrative from the evidence pack |
| Failed payments | Draft guest messages for declined scheduled payments in the guest's language via CRM |
| Risk review | Summarise why a booking was flagged, from the rule outputs |

---

## 6. Open Questions

| # | Question |
|---|---|
| Q1 | Which gateways/acquirers and countries at launch? |
| Q2 | Will the suite act as a payment facilitator (own merchant onboarding) or integrate third-party gateways only? |
