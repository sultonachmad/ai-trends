# Guest CRM, Messaging & Reputation — Functional Requirements

> **Document type:** Functional Requirements Specification
> **Scope:** Guest identity and profiles across properties, consent, segmentation, lifecycle communication, unified messaging inbox (email, SMS, WhatsApp and other chat, OTA messaging, web chat), guest portal / online check-in, surveys, review management
> **Positioning:** **Separate system** sold as the Guest pack add-on and standalone to properties on third-party PMSs. Reads reservation/stay events from the platform; owns guest identity, consent, communication history.
> **Priority key:** **M** must · **S** should · **C** could
> **Related:** [Portfolio architecture](hospitality-suite-portfolio-architecture.md) · [PMS](property-management-system-functional-requirements.md) · [Booking Engine](booking-engine-functional-requirements.md) · [AI Assistant Layer](ai-assistant-layer-functional-requirements.md)

---

## 1. Purpose

Know every guest, communicate with them at the right time on the channel they prefer, answer them fast, and turn stays into reviews and repeat bookings. For traditional operators this means fewer missed emails and phone calls; for modern operators it means automation with control.

### In scope
Guest identity and profile enrichment; consent and privacy; segmentation; automated lifecycle messages; campaigns; unified inbox; guest portal (pre-check-in, in-stay requests, check-out); surveys; review aggregation and response; feedback and complaint handling; loyalty-lite.

### Out of scope
Reservation creation (PMS/Booking Engine), folio and payments (PMS/Payments), full loyalty program accounting (optional Loyalty module).

---

## 2. Actors

| Role | Responsibilities |
|---|---|
| Guest | Receives messages, replies, uses portal, leaves reviews |
| Front desk / guest relations | Answers inbox, handles requests and complaints |
| Marketing manager | Segments, campaigns, templates, review strategy |
| General manager / owner | Reputation dashboard, complaint escalations |
| Systems: PMS/CRS (events), Booking Engine (abandoned carts, accounts), messaging providers (email, SMS, WhatsApp Business), OTA messaging APIs, review platforms (Google, OTAs, TripAdvisor-type), AI gateway |

---

## 3. Functional Requirements

### 3.1 Guest Identity and Profiles

| ID | Requirement | Priority |
|---|---|---|
| FR-CRM-001 | The system shall maintain a single guest profile per person across all properties in the organisation, merging identities from PMS, Booking Engine, channels and messaging using configurable matching rules (email, phone, name + DOB, document number). | M |
| FR-CRM-002 | The system shall keep a per-property view of the profile respecting legal-entity data-sharing rules. | M |
| FR-CRM-003 | The system shall enrich profiles with stay history, spend, channels used, preferences, communication history, survey scores, reviews and tags. | M |
| FR-CRM-004 | The system shall compute guest value indicators (lifetime nights, spend, average score, cancellation rate, last stay) and badges (first-time, repeat, VIP, at-risk). | S |
| FR-CRM-005 | The system shall support manual and rule-based merges with full audit and un-merge. | S |
| FR-CRM-006 | The system shall support company and agent contacts as profiles linked to their bookings. | S |

### 3.2 Consent and Privacy

| ID | Requirement | Priority |
|---|---|---|
| FR-CRM-010 | The system shall record consent per purpose (transactional, marketing, surveys) and per channel (email, SMS, WhatsApp, phone) with source, timestamp and wording version. | M |
| FR-CRM-011 | The system shall enforce consent before sending any non-transactional message and honor unsubscribe links and STOP keywords immediately. | M |
| FR-CRM-012 | The system shall support data-subject access, export and erasure requests, coordinating with the PMS for legally retained records. | M |
| FR-CRM-013 | The system shall support retention rules per data category and automatic anonymisation. | M |
| FR-CRM-014 | The system shall support quiet hours per guest time zone for non-urgent messages. | S |

### 3.3 Segmentation and Audiences

| ID | Requirement | Priority |
|---|---|---|
| FR-CRM-020 | The system shall allow building segments from profile, stay, booking, behaviour and survey attributes with AND/OR logic and preview counts. | M |
| FR-CRM-021 | The system shall support dynamic segments that update automatically and static lists. | M |
| FR-CRM-022 | The system shall provide pre-built segments (past guests not returned in 12 months, high spenders, OTA guests to convert direct, upcoming birthdays, cancelled bookings). | S |
| FR-CRM-023 | The system shall export segments to external email/ad platforms with consent flags. | S |

### 3.4 Lifecycle Automation

| ID | Requirement | Priority |
|---|---|---|
| FR-CRM-030 | The system shall provide a journey/automation builder triggered by platform events (booking confirmed, X days before arrival, checked in, mid-stay, checked out, cancelled, no-show, abandoned cart, birthday) with conditions, delays and channel selection. | M |
| FR-CRM-031 | The system shall ship default journeys per property type (hotel, hostel, rental, campsite, aparthotel) that can be edited. | M |
| FR-CRM-032 | The system shall support multilingual templates with merge fields from the reservation, property and guest, and conditional blocks. | M |
| FR-CRM-033 | The system shall support channel fallback (WhatsApp → SMS → email) when a channel is unavailable or unconsented. | S |
| FR-CRM-034 | The system shall support a "review before send" mode per journey for properties that want human approval. | M |
| FR-CRM-035 | The system shall support upsell offers in pre-arrival messages (upgrade, breakfast, late checkout) linked to Booking Engine or portal purchase. | S |
| FR-CRM-036 | The system shall report journey performance (sent, delivered, opened, clicked, replied, converted, revenue). | M |
| FR-CRM-037 | The system shall suppress automated messages when a human conversation is active on the same thread, unless the message is transactional. | S |

### 3.5 Campaigns

| ID | Requirement | Priority |
|---|---|---|
| FR-CRM-040 | The system shall support one-off and scheduled campaigns to segments over email, SMS and WhatsApp (template messages), with send-time optimisation per time zone. | M |
| FR-CRM-041 | The system shall support A/B tests of subject lines and content. | S |
| FR-CRM-042 | The system shall track attribution of bookings to campaigns via links and promo codes. | M |
| FR-CRM-043 | The system shall enforce frequency caps per guest. | S |

### 3.6 Unified Inbox

| ID | Requirement | Priority |
|---|---|---|
| FR-CRM-050 | The system shall consolidate conversations from email, SMS, WhatsApp and other chat apps, web chat widget, Booking Engine contact forms, OTA messaging, and Google Business Profile messages into one inbox, threaded per guest and linked to reservations. | M |
| FR-CRM-051 | The system shall show reservation context (dates, unit, balance, status, notes) beside each conversation. | M |
| FR-CRM-052 | The system shall support assignment, status (open, pending, resolved), tags, internal notes, snooze and SLA timers with alerts. | M |
| FR-CRM-053 | The system shall support canned responses and template insertion with merge fields. | M |
| FR-CRM-054 | The system shall support in-line translation of inbound and outbound messages. | S |
| FR-CRM-055 | The system shall support actions from the inbox: create task (housekeeping/maintenance), send payment link, send portal link, flag complaint, add preference to profile. | M |
| FR-CRM-056 | The system shall support a mobile inbox for managers and owners with push notifications. | S |
| FR-CRM-057 | The system shall support shared team visibility (who is typing, collision warnings). | S |
| FR-CRM-058 | The system shall provide an inbound phone-call log (manual or via telephony integration) so phone conversations appear in the thread. | C |
| FR-CRM-059 | The system shall support after-hours auto-acknowledgement with expected response time. | M |

### 3.7 Guest Portal and Self-Service

| ID | Requirement | Priority |
|---|---|---|
| FR-CRM-060 | The system shall provide a mobile web portal (no app install) linked from messages: booking summary, pre-check-in (details, ID, signature, payment, ETA), digital guide, requests, chat, check-out, invoice download. | M |
| FR-CRM-061 | The portal shall collect pre-check-in data per the property's required fields and push it to the PMS profile and registration record. | M |
| FR-CRM-062 | The portal shall support service requests that become tasks in the Operations app or PMS. | S |
| FR-CRM-063 | The portal shall support upsell purchases and extras. | S |
| FR-CRM-064 | The portal shall display access instructions and door codes/mobile keys after pre-check-in is complete and conditions are met (payment, ID). | S |
| FR-CRM-065 | The portal shall support house rules acceptance and local registration forms. | M |
| FR-CRM-066 | The portal shall be branded per property and available in the guest's language. | M |

### 3.8 Surveys and Feedback

| ID | Requirement | Priority |
|---|---|---|
| FR-CRM-070 | The system shall send post-stay surveys (and optional in-stay pulse) with configurable questions, NPS/CSAT scoring and per-department ratings. | M |
| FR-CRM-071 | The system shall alert staff immediately for low in-stay scores so issues can be fixed before departure. | S |
| FR-CRM-072 | The system shall route satisfied respondents to public review sites and unhappy ones to a private follow-up. | S |
| FR-CRM-073 | The system shall track complaints: category, severity, owner, resolution, compensation, root cause, and link to unit for recurring issues. | M |

### 3.9 Reputation Management

| ID | Requirement | Priority |
|---|---|---|
| FR-CRM-080 | The system shall aggregate reviews from Google, OTAs and review sites into one view with score trends, by property and period. | M |
| FR-CRM-081 | The system shall allow responding to reviews from within the system where platform APIs allow, and otherwise provide copy-ready drafts with a link. | M |
| FR-CRM-082 | The system shall categorise review themes (cleanliness, staff, location, value, noise, Wi-Fi) and trend them over time. | S |
| FR-CRM-083 | The system shall link reviews to the stay and unit when identifiable, feeding housekeeping and maintenance insight. | S |
| FR-CRM-084 | The system shall benchmark scores against a configurable competitor set where data is available. | C |
| FR-CRM-085 | The system shall track review-request conversion by journey. | S |

### 3.10 Loyalty-Lite and Direct Conversion

| ID | Requirement | Priority |
|---|---|---|
| FR-CRM-090 | The system shall support a simple membership (sign-up, member rate access, perks) without points accounting, upgradeable to the full Loyalty module. | S |
| FR-CRM-091 | The system shall support "book direct next time" offers to OTA guests with personal codes. | S |
| FR-CRM-092 | The system shall measure direct-booking share among repeat guests. | S |

### 3.11 Administration and Integration

| ID | Requirement | Priority |
|---|---|---|
| FR-CRM-100 | The system shall connect to the suite's platform via events and API, and to third-party PMSs via adapters. | M |
| FR-CRM-101 | The system shall manage messaging provider accounts (sender identities, WhatsApp Business templates and approval status, SMS sender IDs, email domains with authentication). | M |
| FR-CRM-102 | The system shall support roles (agent, marketer, manager) and per-property scope. | M |
| FR-CRM-103 | The system shall log all outbound communications and their delivery status. | M |

---

## 4. Key Business Rules

| ID | Rule |
|---|---|
| BR-CRM-01 | Transactional messages (confirmation, payment, check-in instructions, safety) are sent regardless of marketing consent; everything else requires consent for that channel. |
| BR-CRM-02 | A merged profile keeps all source identifiers; unmerge restores them. |
| BR-CRM-03 | WhatsApp marketing uses approved templates only; free-form replies are allowed within the provider's service window. |
| BR-CRM-04 | When a reservation is cancelled, all pending automated messages for it are cancelled. |
| BR-CRM-05 | Review responses are never auto-published; a person approves each one unless the property enables auto-publish for 5-star reviews with no text. |

---

## 5. AI Assistance (API-based, no model training)

| Area | Assistance |
|---|---|
| Inbox | Intent classification (booking question, check-in, complaint, request, spam), urgency and sentiment flags, suggested replies grounded on the reservation, policies and digital guide, in the guest's language |
| FAQ auto-reply | Answer an owner-approved list of questions automatically (Wi-Fi, parking, check-in time, directions) and hand over to a human for anything else |
| Summaries | One-paragraph summary of a long thread or a guest's history before a call or check-in |
| Reviews | Draft responses matching the property's tone; summarise weekly themes and recurring unit-level issues |
| Campaigns | Draft subject lines and copy variants from a brief; suggest segments likely to respond based on past campaign results |
| Surveys | Classify free-text answers into themes and highlight actionable complaints |
| Cost control | Cheap model for classification on every message; larger model only when a draft is requested; cache FAQ answers per property |

---

## 6. Open Questions

| # | Question |
|---|---|
| Q1 | Which messaging channels at launch (email, SMS, WhatsApp are assumed; which others)? |
| Q2 | Is the guest portal part of this product or the Booking Engine? (Recommended here, as it is post-booking.) |
| Q3 | Which review platforms expose APIs sufficient for in-app responses? |
