# Hospitality Software Suite — Portfolio & Modularity Analysis

> **Purpose:** Decide which hospitality capabilities belong in one application, which must be separate systems, and how to package them as a core product plus add-ons.
> **Companion documents (functional requirements):**
> [PMS](property-management-system-functional-requirements.md) ·
> [CRS](crs-functional-requirements.md) ·
> [Booking Engine](booking-engine-functional-requirements.md) ·
> [Channel Manager](channel-manager-functional-requirements.md) ·
> [CRM & Guest Engagement](crm-guest-engagement-functional-requirements.md) ·
> [RMS](rms-functional-requirements.md) ·
> [Housekeeping & Maintenance](housekeeping-maintenance-functional-requirements.md) ·
> [POS & Ancillary](pos-ancillary-functional-requirements.md) ·
> [Payments](payments-functional-requirements.md) ·
> [AI Assistant Layer](ai-assistant-layer-functional-requirements.md) ·
> [Indonesia market entry](indonesia-market-entry-strategy.md)
> **Date:** 2026-11-07 · **Status:** draft for discussion

---

## 1. The Short Answer

| Decision | Recommendation |
|---|---|
| One app or many? | **One platform, several apps.** A single shared backend (tenant, property, inventory, guest, folio, events) with multiple purpose-built front-ends. Users see "apps"; you run one data model. |
| What is the core product? | **PMS Core** — inventory, rates, reservations, front desk, folio/billing, basic housekeeping status, end-of-day, reports, users. This is the thing a property cannot run without. |
| What are add-ons? | Booking Engine, Channel Manager, Payments, Guest CRM & Messaging, Operations mobile (housekeeping + maintenance), RMS, POS Lite, Guest Portal/App, Owner Portal, AI Assistant. |
| What must be a **separate system**? | **Channel Manager** (connectivity + certification workload), **RMS** (different user, heavy analytics), **CRM** (marketing user, cross-property guest identity), **POS** (restaurant workflows), **CRS** (only for multi-property; sits *above* PMS). These can still be sold as add-ons but should be independently deployable services with their own release cycle, and sellable to properties that run a competitor's PMS. |
| Traditional vs. modern users | **One product, two interaction modes** (Classic / Guided) plus a mobile Operations app. Do not build two separate products. |
| AI | **Assist, don't replace.** A cross-cutting AI layer that calls hosted foundation-model APIs (no custom model training), grounded on the property's own data, with humans approving anything that touches money, inventory or guest commitments. |

---

## 2. Why Not One Monolithic App

Hospitality systems differ on four axes. When two capabilities differ on **three or more**, they should be separate systems.

| Axis | Example contrast |
|---|---|
| **User** | Front desk agent (PMS) vs. revenue manager (RMS) vs. marketing manager (CRM) vs. housekeeper on a phone (Ops) |
| **Data gravity** | Inventory/folio (transactional, must be consistent) vs. historical pace & competitor rates (analytical) vs. guest identity across properties (master data) |
| **Change cadence** | OTA APIs change monthly and require partner certification (Channel Manager) vs. fiscal/tax logic that changes yearly (PMS) |
| **Buyer** | Single property owner (PMS) vs. chain HQ (CRS) vs. restaurant manager (POS) |

Applying the test:

| Capability | User | Data | Cadence | Buyer | Verdict |
|---|---|---|---|---|---|
| Reservations, front desk, folio | Same | Same | Same | Same | **Core PMS** |
| Booking Engine | Guest (public) | Same inventory | Same | Same | **Module of PMS** (must read inventory in real time; selling it separately requires a channel connection anyway) |
| Channel Manager | Reservations/revenue | Same inventory, but integration-heavy | Very different | Same, or other-PMS users | **Separate service, sold as add-on** |
| Payments | All | Tokens, settlements | Regulated | Same | **Platform service** (embedded, not a user app) |
| Housekeeping status | Front desk | Same | Same | Same | **Core PMS** (status only) |
| Housekeeping & maintenance mobile | Housekeepers, technicians | Tasks, photos | Different UI needs | Same | **Separate mobile app, shared backend, add-on** |
| CRM & messaging | Marketing, guest relations | Guest identity, consent, campaigns | Different | Sometimes separate | **Separate system, add-on** |
| RMS | Revenue manager | Analytical | Different | Often separate | **Separate system, add-on** |
| POS | Waiters, cashiers | Orders, menus | Different | Separate | **Separate system**; PMS ships a POS Lite for small properties |
| CRS | Central reservations, chain | Multi-property aggregate | Different | HQ | **Separate system** above PMS; single properties do not need it |
| Owner portal | External owner | Statements | Low | Same | **Module of PMS** |
| AI assistant | Everyone | Reads everything | Fast | Same | **Cross-cutting layer, add-on** |

---

## 3. Target Architecture: One Platform, Many Apps

```
                        ┌──────────────────────────────────────────────┐
  Guests / public       │  Booking Engine · Guest Portal · Kiosk       │
                        └───────────────┬──────────────────────────────┘
                                        │
  Staff apps            ┌───────────────┴──────────────────────────────┐
                        │  PMS Web (Classic + Guided modes)            │
                        │  Operations Mobile (HK + Maintenance)        │
                        │  POS Lite · Owner Portal · CRS Console       │
                        │  CRM Console · RMS Console                   │
                        └───────────────┬──────────────────────────────┘
                                        │  one API, one identity, one event bus
  Platform services     ┌───────────────┴──────────────────────────────┐
                        │  Inventory & Rates  · Reservations · Folio   │
                        │  Guest Identity     · Tasks        · Payments│
                        │  Notifications      · Documents    · Reports │
                        │  AI Gateway (prompting, grounding, cost caps)│
                        └───────────────┬──────────────────────────────┘
                                        │
  Connectivity          ┌───────────────┴──────────────────────────────┐
                        │  Channel Manager (OTAs, Google, GDS, meta)   │
                        │  Lock · POS · Accounting · ID scan · Gov     │
                        └──────────────────────────────────────────────┘
```

Rules that make the modular model work:

1. **Every app talks to the platform API only.** No app reads another app's database.
2. **Inventory, rates and availability have one owner** (the Inventory & Rates service). The Booking Engine, Channel Manager, CRS and RMS read from it or write to it through the same API; none of them keeps a competing copy as truth.
3. **Events, not polling.** Reservation, stay, folio, task and unit-status events are published once; CRM, RMS, AI and integrations subscribe.
4. **Entitlements control add-ons.** A tenant's subscription toggles modules; the UI hides what isn't licensed; the API returns a clear "module not enabled" error.
5. **Each separate system must be sellable standalone** (Channel Manager, CRM, RMS, CRS) to a property that runs a third-party PMS. This is both a revenue option and a forcing function for clean APIs.

---

## 4. Packaging: Core + Add-ons

| Package | Contents | Who buys it |
|---|---|---|
| **PMS Core** | Property & inventory, rates & restrictions, reservations, front desk, folio/billing, taxes & invoicing, basic housekeeping status, night audit (auto), standard reports, users & audit | Every property |
| **Commerce pack** | Booking Engine, Payments, Channel Manager (incl. Google channel) | Any property selling online (nearly all) |
| **Guest pack** | CRM, unified messaging, guest portal & online check-in, reviews/reputation | Properties investing in direct business and repeat guests |
| **Operations pack** | Housekeeping & Maintenance mobile, task routing, inspections, vendor scheduling | 20+ units, dispersed rentals, resorts |
| **Revenue pack** | RMS (forecasts, recommendations, competitor rates), advanced BI | 30+ units or active revenue management |
| **Ancillary pack** | POS Lite, services/activity booking, gift cards | Properties with F&B, spa, activities |
| **Enterprise pack** | CRS, multi-property central config, portfolio reporting, SSO | Chains, management companies |
| **Owner pack** | Owner accounting, statements, owner portal, trust accounting | Vacation rental managers, condo-hotels |
| **AI Assistant** | Guest message drafting, review replies, translation, natural-language reports, document extraction, task voice capture | All, metered |

Pricing guidance (not a requirement): per-unit per-month for Core; add-ons as flat or per-unit; AI metered with a monthly cap the owner sets.

---

## 5. Traditional vs. Modern Users: One App or Two?

### 5.1 Who they are

| Trait | Traditional user | Modern user |
|---|---|---|
| Typical property | Independent hotel, family B&B, campsite, older staff | Boutique, hostel chain, aparthotel, rental manager |
| Device | Desktop at front desk, printer, phone calls | Laptop + phone, tablet at desk, messaging apps |
| Workflow expectation | Dense grids, keyboard shortcuts, printed reports, "the tape chart" | Guided flows, search-first, automation, dashboards |
| Attitude to automation | Wants control and confirmation | Wants it done automatically with notifications |
| Guest communication | Phone, email | WhatsApp/chat, self-service |

### 5.2 Recommendation: single product, adaptive experience

Two products doubles build, QA, documentation and support cost and splits the roadmap. Instead:

1. **Two UI modes on the same screens, switchable per user:**
   - **Classic mode** — dense tables, tape chart as the home screen, keyboard shortcuts, printable everything, explicit confirm buttons, minimal animation.
   - **Guided mode** — search-first home ("What do you want to do?"), step-by-step check-in, cards, inline suggestions, automation on by default.
2. **Role-based defaults** — front desk defaults to Classic; managers and owners to Guided dashboards; housekeepers always get the mobile app.
3. **Property templates** choose sensible defaults per property type (B&B gets auto night audit, no groups module visible; hotel gets attended audit, groups on).
4. **Automation is always opt-in per property**, with a "review before send" setting so traditional users can approve before anything goes out (emails, rate pushes, auto-assignment).
5. **Low-tech guest channels remain first-class**: SMS and plain email alongside WhatsApp and the guest portal; printable registration cards alongside e-signature.
6. **AI as the bridge**: the natural-language assistant lets a traditional user type "show me tomorrow's arrivals with balance due" instead of learning the report builder, which lowers training cost rather than adding to it.
7. **Onboarding paths differ**: traditional users get spreadsheet import, a "run alongside your old system for 2 weeks" mode, and phone support; modern users get self-serve onboarding.

What stays separate: the **Operations mobile app** (phone-first, offline-tolerant) and the **guest-facing surfaces** (booking engine, portal, kiosk). These are different users on different devices, not a traditional/modern split.

---

## 6. Google as a Distribution Channel (OTA Alternative)

Google is not an OTA, but for many properties it is the highest-volume source of demand after OTAs, and it is commission-free or lower-cost. The Channel Manager must treat it as a first-class channel with its own requirements (see [Channel Manager FR §6.9](channel-manager-functional-requirements.md)).

| Google surface | What it is | How properties get on it |
|---|---|---|
| **Hotel search / Free Booking Links** | Price and availability shown on the hotel's Google listing and Maps, linking to the property's own booking engine; no commission | Property or connectivity partner sends an availability/rate/inventory (ARI) feed to Google Hotel Center |
| **Hotel Ads (paid)** | Same placement, auctioned; pay per click or commission per stay/booking | Same feed plus bidding configuration |
| **Google Business Profile (Maps listing)** | Business details, photos, reviews, Q&A, messaging, "Book" button | Claimed listing; a booking link can point to the booking engine |
| **Vacation Rentals** | Comparable surface for whole-unit rentals | Separate feed specification |
| **Things to Do** | Activities and tickets | For properties selling experiences |

Functional implications for the suite:

- The Channel Manager (or a Google connector) sends ARI for every bookable unit type and rate plan and keeps it in near real time; stale prices get the listing penalised or hidden.
- The Booking Engine must provide a **deep-linked landing page** that shows exactly the price Google displayed (price accuracy is enforced) and must report conversions back.
- CRM/reputation features should read and respond to Google reviews and messages.
- The Booking Engine's direct bookings from Google should be attributed as a distinct source ("Google free booking link", "Google Hotel Ads") for reporting and for RMS channel-cost calculations.
- Small properties without a connectivity partner need a **simple "Connect to Google" wizard** within the product.

---

## 7. AI Strategy: Improve Existing Services Without Training Models

### 7.1 Principles

1. **No custom model training.** Use hosted foundation models (large language and vision models) through their APIs, plus the vendor's built-in document and image understanding. Treat the model as a utility, like a payment gateway.
2. **Ground every answer in the property's own data.** Retrieve the reservation, the guest profile, the house rules, the rate policy, then ask the model to act on *that*, never on general knowledge alone.
3. **Human approval for anything binding.** Sending a quote, changing a rate, cancelling, refunding, moving a guest: AI drafts, a person confirms, unless the owner explicitly enables auto-mode for a narrow case (e.g., auto-reply to "what is the Wi-Fi password").
4. **Cost caps the owner controls.** Monthly AI budget per property, cheap models for classification and routing, larger models only for drafting and reasoning, response caching for repeated questions, batch processing for nightly jobs.
5. **Transparency.** Every AI-produced text or suggestion is labelled, logged with its inputs, and can be reported as wrong, which feeds prompt and retrieval improvements (not model retraining).

### 7.2 Where AI improves services already in the suite

| Existing function | AI assistance (API-based) | Value to a small owner |
|---|---|---|
| Guest messaging (CRM) | Classify intent, draft replies in guest's language, answer FAQ from the property's guide, flag urgent or unhappy guests | Replies in minutes instead of hours; no night staff needed for simple questions |
| Reviews (CRM) | Summarise themes across reviews, draft personalised responses, detect recurring problems per unit | Better scores, less time |
| Reservations | Turn an email or WhatsApp booking request into a structured quote; extract rooming lists from attachments | Fewer manual entries, fewer typos |
| Front desk | Read ID documents into the profile (vision), suggest unit assignment with reasons, summarise the guest's history at check-in | Faster check-in, personal touch |
| Housekeeping | Voice-to-task on mobile, photo-based damage description, translate tasks to the housekeeper's language | Works for multilingual teams |
| Maintenance | Categorise and prioritise requests from free text, suggest likely cause and parts from history | Fewer escalations |
| Revenue (RMS) | Explain forecasts and rate recommendations in plain language; summarise competitor movements; draft "what-if" scenarios | Owner understands and trusts pricing |
| Reports | Natural-language questions over the data model ("compare March occupancy to last year by channel") producing a saved report | No report builder training |
| Finance | Match invoices and payments, draft dunning emails, explain variances in the trial balance | Fewer audit surprises |
| Onboarding & support | In-app assistant grounded on product documentation and the property's configuration | Lower support cost, helps traditional users |

Forecasting is handled with transparent statistical methods inside the RMS (seasonality, pace, pickup curves) rather than custom-trained neural models; the language model is used to *explain* the numbers, not to produce them.

Full requirements are in the [AI Assistant Layer FR](ai-assistant-layer-functional-requirements.md).

---

## 8. Build Order (suggested)

| Phase | Deliver | Rationale |
|---|---|---|
| 1 | PMS Core + Payments + Booking Engine | A property can run and sell direct on day one |
| 2 | Channel Manager (top OTAs + Google) + Operations mobile | Online distribution and the most-used staff mobile workflows |
| 3 | CRM & messaging + Guest portal + AI Assistant v1 (messaging, reviews, reports) | Direct-revenue and service quality levers; AI gives differentiation early at low build cost |
| 4 | RMS + POS Lite + Owner pack | Revenue and ancillary for larger or specialised properties |
| 5 | CRS + Enterprise | Chains and management companies, once single-property product is proven |

---

## 9. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Add-ons drift into separate data models | One platform API, contract tests, shared event schema |
| Channel Manager certification effort | Start with 3–5 highest-volume OTAs + Google; consider a connectivity partner for the long tail |
| Two UI modes doubling design effort | Same components, different density/defaults; mode is a theme + layout preset, not a new screen set |
| AI cost overrun | Per-property budget, tiered models, caching, nightly batch, usage dashboard |
| AI mistakes with guests | Draft-and-approve default; narrow auto-reply allowlist; every message labelled and logged |
| Small owners overwhelmed by modules | Property-type templates hide unlicensed and irrelevant modules |
