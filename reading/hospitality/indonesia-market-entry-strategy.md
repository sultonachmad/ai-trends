# Indonesia Market Entry — "Ride Behind the Big Brands" Strategy & Gap Analysis

> **Purpose:** Define how the hospitality suite enters Indonesia as its first market, using the existing demand platforms (Traveloka, Tiket.com, Agoda, Booking.com, Airbnb, Google) and the aggregator brands (RedDoorz, OYO, Bobobox, Mamikos/Singgahsini, Rukita) as *demand and reference points*, not competitors, and identify the needs they leave uncovered.
> **Interpretation of "hit and run":** a guerrilla go-to-market: do not fight the big brands head-on (no OTA, no franchise brand), strike fast in the gaps they leave, land properties in a day with a small wedge product, and expand inside the account. The big brands bring demand; we bring the operating stack.
> **Date:** 2026-11-07 · **Status:** draft · Facts marked **[verify]** need confirmation with a local adviser or the source before being relied on.
> **Related:** [Portfolio architecture](hospitality-suite-portfolio-architecture.md) · [PMS](property-management-system-functional-requirements.md) · [Channel Manager](channel-manager-functional-requirements.md) · [CRM](crm-guest-engagement-functional-requirements.md) · [Payments](payments-functional-requirements.md) · [AI layer](ai-assistant-layer-functional-requirements.md)

---

## 1. Summary

| Question | Answer |
|---|---|
| Who is the customer? | The **independent operator**: hotel melati / budget hotel, guesthouse, villa and villa manager (Bali, Lombok, Yogyakarta), kos-kosan owner with 10–200 rooms, homestay cluster, glamping, small local chain of 3–10 properties. Independents hold roughly 63% of Indonesia's hotel property market (Mordor Intelligence via Industry.co.id, 2025). |
| What do the big brands do for us? | **Demand.** Traveloka, Tiket.com, Agoda, Booking.com, Airbnb and Google Maps bring the guests; our Channel Manager connects to them. RedDoorz/OYO have *trained* thousands of small owners to expect an app, a channel manager and dynamic pricing — then take 20%+ and the brand. We serve the ones who leave, the ones who never joined, and the ones who stay but want their own direct channel. |
| What is the wedge? | **"Sell more, get paid, reply faster" in one day:** WhatsApp inbox + QRIS/VA payment links + Channel Manager (Traveloka, Tiket, Agoda, Booking, Airbnb, Google). PMS Core comes second, once the property trusts the product. |
| Where are the gaps? | Government compliance (APOA, regional hotel tax reporting), kos-kosan operations, villa owner accounting, sharia-compliant hotels, WhatsApp/Instagram-born bookings, transfer-proof verification, cash and DP culture, Indonesian holiday demand patterns, low-connectivity islands, low-digital-literacy staff, and small local chains. See §4. |
| Residency and AI | Host guest data in a Jakarta cloud region; use AI providers reachable from Jakarta with PII minimisation; comply with PDP Law Art. 56 for anything crossing the border. See §6. |

---

## 2. Market Map

### 2.1 Demand platforms (connect to, never compete with)

| Platform | Role in Indonesia | Implication for the suite |
|---|---|---|
| **Traveloka** | Largest domestic OTA (flights + hotels + activities); strong in domestic leisure and secondary cities | Must-have channel at launch; direct API or via certified connectivity partner **[verify access terms]** |
| **Tiket.com** | #2 domestic OTA (Blibli/Djarum group); strong promotions, "Tiket Elite" hotels | Must-have channel at launch |
| **Agoda / Booking.com** | Dominant for inbound international (Bali, Jakarta business) | Must-have; Agoda especially for Bali |
| **Airbnb** | Villas, apartments, homestays; iCal and API connectivity | Must-have for villa/apartment segment; Airbnb messaging into CRM inbox |
| **Trip.com** | Chinese and regional inbound | Second wave |
| **Google Maps / Hotel search** | The #1 way Indonesians find a place to stay; Business Profile, reviews, "Book" link, free booking links | Treat as a first-class channel (Channel Manager §3.9); Business Profile review and message handling in CRM |
| **Instagram / TikTok / WhatsApp** | Where small villas and guesthouses actually get direct bookings ("DM untuk booking") | CRM inbox + AI extraction of booking requests from chat into quotes; WhatsApp Business API is the direct booking engine for many |
| **Klook, Traveloka Xperience, Tiket To Do** | Activities and tours | Ancillary pack later |

### 2.2 Aggregators, brands and managed operators (reference points and sources of customers)

| Player | Model | What they do well | What they leave behind |
|---|---|---|---|
| **RedDoorz** (Sans, Urbanview, KoolKost, RedLiving) | Franchise/partner brand with its own app, pricing and distribution; ~4,300 partner properties across Indonesia and the Philippines, 300+ Indonesian cities; now adding 100–150 *company-operated* hotels by 2027 (TTG Asia) | Taught small owners to use an app and dynamic pricing; standardised cleanliness; brought OTA demand | Owners lose brand identity and ~20%+ of revenue; partner model is being de-emphasised in favour of company-operated hotels, which means **partner churn and "graduates"** who need their own stack |
| **OYO** | Asset-light franchise; multiple sub-brands (Townhouse, Vacation Homes); Indonesia footprint reduced after 2020 | Same pattern as RedDoorz | Many ex-OYO properties in tier-2/3 cities kept the "digital expectation" but have no software |
| **Bobobox, Bobocabin** | Owned brand (capsule, cabins) | Product innovation | Not a vendor; no software for others |
| **Mamikos / Singgahsini / Apik** | Kos listing marketplace + managed kos + operator training | Demand for kos; management for owners who hand over operations | Owners who **keep operating themselves** have no PMS; kos is excluded from PBJT hotel tax, which simplifies our compliance for that segment |
| **Rukita, Cove, Flokq** | Managed co-living with revenue share | Branded, tech-run co-living in Jakarta, Bandung, Yogyakarta, Medan, Solo | Only for owners willing to hand over the property; small independent co-living/kos owners are unserved |
| **Bali villa management companies** (many, e.g., Bukit Vista-type operators) | Manage foreign- and local-owned villas for a fee | Owner reporting, OTA listing | Mid-size managers (20–200 villas) often run on spreadsheets + a foreign PMS with no IDR owner accounting, no APOA, no local tax |
| **Local/foreign PMS & channel managers present** (VHP, Power Pro, STAAH, SiteMinder/Little Hotelier, Hotel Link, Cloudbeds, eZee, Hotelogix) **[verify current market shares]** | Software vendors | Incumbents in star hotels (VHP, Power Pro) and Bali boutique/villas (Hotel Link, SiteMinder, Cloudbeds) | Foreign tools: USD pricing, weak Bahasa, no APOA/regional tax, no QRIS-native flows, no kos/sharia/homestay models; local legacy tools: on-premise, desktop-only, weak mobile and messaging |

### 2.3 Payments and messaging rails

| Rail | Notes |
|---|---|
| **QRIS** | National QR standard; every e-wallet and bank app can pay a QRIS; the default "pay now" for walk-ins and small deposits |
| **Virtual accounts (BCA, Mandiri, BNI, BRI, Permata)** | The default online payment for domestic guests; many guests still pay by manual transfer and send a screenshot |
| **E-wallets** (GoPay, OVO, DANA, ShopeePay, LinkAja) | Via gateway |
| **Gateways** (Midtrans, Xendit, DOKU, Faspay, iPaymu) **[choose 1–2 at launch]** | Provide QRIS, VA, wallets, cards, payment links, payouts |
| **Cards** | Low penetration domestically; essential for international guests |
| **WhatsApp Business API** | The primary guest and staff communication channel; SMS is secondary; email is weak for domestic leisure |

---

## 3. The "Ride Behind" Strategy

### 3.1 Principles

1. **Never compete for demand.** No OTA, no brand, no franchise. Every big brand is a channel or a reference.
2. **Monetise the churn of the aggregators.** RedDoorz's shift to company-operated hotels and OYO's contraction create a steady flow of "graduate" properties that know what dynamic pricing and a channel manager are, and now need their own. Target them explicitly ("Keluar dari aggregator? Bawa tamumu sendiri").
3. **Land in a day, expand in a quarter.** The wedge must be installable from a phone over WhatsApp with no training: connect OTAs, connect WhatsApp, turn on payment links. PMS Core, housekeeping and RMS follow once there is trust.
4. **Be local where foreign tools cannot be.** Compliance (APOA, PBJT reporting), payment rails (QRIS, VA, transfer proof), language (Bahasa Indonesia first; English second; regional UI later), holidays (Lebaran, Nataru, cuti bersama), and property types (kos, villa, homestay, sharia).
5. **Price in IDR per room per month** with a free tier for the wedge (e.g., inbox + payment links free; channel manager paid per connected channel; PMS per room). Owners compare against the aggregator commission they already pay.
6. **Sell through the people owners already trust:** local hotel associations (PHRI branches), villa management companies, kos communities, tourism village cooperatives (desa wisata), payment gateway partners, and WhatsApp-based reseller/onboarding agents in each city.

### 3.2 Beachheads

| Beachhead | Why | Entry product |
|---|---|---|
| **Bali villas and guesthouses** (Canggu, Ubud, Seminyak, Uluwatu) | Highest density of independents, international guests (cards, Airbnb, Agoda), APOA need, owner accounting need, English + Bahasa | Channel Manager + WhatsApp inbox + Owner statements |
| **Yogyakarta, Bandung, Malang, Solo budget hotels and guesthouses** | Domestic leisure, ex-aggregator properties, Traveloka/Tiket demand, holiday-driven | Channel Manager + Payment links + PMS Core |
| **Jakarta, Depok, Bandung, Surabaya kos-kosan and co-living** | Monthly billing, deposits, electricity, gender rules; nobody sells owner-operated kos software at scale | Kos module (monthly billing + WhatsApp reminders + QRIS) |
| **Lombok, Labuan Bajo, Toba, Raja Ampat** (priority destinations) | Low connectivity, lodges, homestays, dive resorts; foreign tools fail | Offline-tolerant PMS Lite + APOA |

### 3.3 What we deliberately do not build first

- A consumer booking marketplace or app (Traveloka/Tiket/Google own this).
- A brand or quality programme (RedDoorz owns this).
- Managed operations (Singgahsini/Rukita own this) — we are the software they or their competitors could run on.
- Full restaurant POS (local POS players such as Moka, Pawoon, Majoo exist **[verify]**; integrate instead).

---

## 4. Gaps the Big Brands and Foreign Tools Do Not Cover

These are the targets of the "hit". Each gap maps to requirement deltas in §5.

| # | Gap | Who nearly covers it | Why it stays open | What we deliver |
|---|---|---|---|---|
| G1 | **Foreign-guest immigration reporting (APOA)** — hotels, apartments, losmen, guesthouses, villas *and kos* must report foreign guests to Imigrasi via the APOA app (Immigration Law 6/2011 Art. 72(2); renewed enforcement push in 2025, QR-code variant) | Nobody in software; staff re-type passports into APOA | OTAs and aggregators do not touch check-in; foreign PMSs do not know APOA | Passport OCR → APOA submission (API if available, otherwise structured export + assisted entry) with audit trail **[verify integration options]** |
| G2 | **Regional hotel tax (PBJT jasa perhotelan)** — max 10% under UU HKPD 1/2022; hotel services outside VAT; many regencies require online reporting / "tapping box" devices for transaction data **[verify per region]** | Legacy local PMSs partly | Foreign tools treat it as a generic tax; nobody automates the monthly e-SPTPD/online report | Correct "nett / ++" pricing (service charge 10% + PBJT 10%), per-region tax rule packs, monthly return export, tapping-box/online reporting interface |
| G3 | **Kos-kosan operations** — monthly rent, deposit, parent as payer, gender-restricted buildings, visiting rules, prepaid electricity tokens (PLN), water, laundry add-ons, late payment reminders | Mamikos (marketplace + managed), Rukita (managed) | They serve owners who hand over the property or only list it; owner-operators have nothing | Kos module on the PMS long-stay model: bed/room leases, recurring IDR invoices, QRIS/VA, WhatsApp reminders, token/meter billing |
| G4 | **Villa owner accounting** (Bali, Lombok): foreign and local owners, management fee models, owner stays, expenses in IDR with USD/AUD reporting, pondok wisata/villa licence tracking, withholding tax on owner payouts **[verify tax treatment]** | Spreadsheets; some foreign PMSs with owner modules in USD | No IDR-native owner statements, no local tax, no APOA | Owner pack localised: IDR statements, multi-currency reporting, expense receipts, payout records, licence/renewal reminders |
| G5 | **Hotel syariah / family-only policies** — marriage proof for couples at check-in, no unmarried mixed couples, prayer times/qibla info, halal F&B flags, Ramadan operating hours | None | Niche nobody digitised; large in Java, Sumatra, Aceh | Property-type template "Syariah": check-in document rules, policy display on booking engine, Ramadan calendars |
| G6 | **WhatsApp/Instagram-born bookings** — most direct bookings for villas and guesthouses arrive as chat; staff type them into spreadsheets | WhatsApp Business (no booking logic) | OTAs want the booking on their platform; foreign CRMs are email-first | CRM inbox with WhatsApp as the primary channel; AI extraction of chat requests into availability search and quote; payment link in the same thread; booking confirmed from chat |
| G7 | **Transfer-proof verification ("bukti transfer")** — guests pay by bank transfer and send a screenshot; staff verify manually against bank mutations | None | Cards are rare; VA costs fees small owners avoid | AI vision reads the screenshot (bank, amount, date, reference) and matches against gateway/VA or manual bank-statement import; flags mismatches and fakes for human check |
| G8 | **Cash and DP (down payment) culture** — partial deposits, cash on arrival, "DP 50%" terms, refunds via transfer | Partly in local PMSs | Foreign booking engines assume card guarantee | Deposit schedules with QRIS/VA links, cash drawer, refund-by-transfer records, Indonesian policy templates |
| G9 | **Indonesian demand calendar** — Lebaran/mudik (Idul Fitri) peaks and Ramadan dips, Nataru (Christmas–New Year), cuti bersama long weekends, school holidays per province, Nyepi in Bali, pilgrim and ziarah traffic, pesantren calendars | RedDoorz/OYO internally | RMS tools ship Western calendars | RMS event packs: national holidays, cuti bersama, provincial school calendars, Bali ceremonies, city events |
| G10 | **Low-connectivity islands** — intermittent internet in NTT, Papua, Maluku, parts of Sumatra/Kalimantan | None (on-prem legacy only) | Cloud-only products fail | Offline-tolerant front desk and housekeeping (local cache, sync later), SMS fallbacks, printed downtime reports |
| G11 | **Low-digital-literacy, multilingual staff** — family-run operations, older staff, regional languages | RedDoorz trains its partners | Foreign tools assume English-literate staff | Bahasa-first UI, "big button" housekeeping mode, WhatsApp-based status updates, AI translation to regional languages for instructions **[verify model quality for regional languages]** |
| G12 | **Groups, weddings, "gathering", retreats, pesantren and school trips** — big domestic group business, booked by phone/WhatsApp with rooming lists in Excel | Star hotels via sales teams | Aggregators ignore groups; small properties have no group tooling | Group blocks, rooming-list import (AI-assisted), master folio, WhatsApp group quotes |
| G13 | **Small local chains (3–10 properties)** — local brands in Yogyakarta, Bandung, Medan | CRS is enterprise-priced | Too small for enterprise CRS | "CRS Lite": cross-property availability, shared guest base, consolidated reporting at SME price |
| G14 | **Domestic identity capture** — KTP (NIK) for domestic guests, passport + visa/VoA/KITAS for foreigners | Manual | Foreign tools do not know KTP layout | KTP OCR, NIK validation format, foreign document types |
| G15 | **Homestay and desa wisata clusters** — village cooperatives pooling 10–50 homestays with shared booking | Government programmes, Airbnb listings | No pooled inventory tool | Multi-host "cluster" property type: pooled availability, fair rotation, per-host payouts |
| G16 | **Hourly / transit / capsule** — airport transit hotels, capsule pods, "short stay" | Bobobox for itself | Nightly-only PMSs | Hourly time grain already in PMS Core (FR-INV-009) |
| G17 | **OTA price and promotion chaos** — Traveloka/Tiket promo programs, "cashback" campaigns, flash sales with channel-specific discounts | Channel managers partially | Parity rules differ from Western OTAs | Channel-specific promotion mapping and net-rate visibility per channel |
| G18 | **Owner-operator finance basics** — no accountant; needs daily cash book, simple P&L, tax amounts due | Spreadsheets | Full ERP too heavy | "Buku kas" view, monthly tax summary, export to local accounting apps (Jurnal, Accurate) **[verify]** |

---

## 5. Requirement Deltas for Indonesia (FR-ID)

Additions to the system FR documents. Priority applies to the Indonesian launch.

### 5.1 PMS

| ID | Requirement | Priority | Gap |
|---|---|---|---|
| FR-ID-001 | Support Indonesian tax packs: PBJT jasa perhotelan per regency/city (rate, base, exemptions), PBJT restaurant for outlets, service charge as a distinct line, "nett" and "++" price display modes. | M | G2 |
| FR-ID-002 | Generate monthly regional tax return data (per-region format) and support online reporting / tapping-box transaction feeds where mandated. | S | G2 |
| FR-ID-003 | Capture KTP/NIK for domestic guests and passport, visa type and permit (VoA, KITAS/KITAP) for foreigners; OCR both. | M | G14 |
| FR-ID-004 | Report foreign guests to APOA at check-in: API integration if available, otherwise structured export and assisted entry, with submission log. | M | G1 |
| FR-ID-005 | Syariah property template: marriage-proof requirement, mixed-couple policy, policy text on booking engine, Ramadan hours. | S | G5 |
| FR-ID-006 | Kos module: room/bed leases, monthly invoices in IDR with pro-rating, deposit, payer ≠ occupant (parent), electricity token/meter billing, gender restriction, house rules, late-payment reminders via WhatsApp. | M (kos segment) | G3 |
| FR-ID-007 | Homestay cluster property type: pooled inventory across hosts with rotation rules and per-host payouts. | C | G15 |
| FR-ID-008 | Offline-tolerant front desk (cache today's arrivals, in-house, departures; queue postings) and scheduled printed/WhatsApp downtime reports. | S | G10 |
| FR-ID-009 | Bahasa Indonesia as the default UI language with full coverage; English secondary. | M | G11 |
| FR-ID-010 | BPS hotel statistics export (monthly occupancy survey fields) **[verify format]**. | C | — |
| FR-ID-011 | "Buku kas" daily cash book and monthly tax-due summary; export to local accounting apps. | S | G18 |
| FR-ID-012 | Owner pack in IDR with multi-currency reporting, withholding tax handling on payouts **[verify]**, licence tracking. | S (villa segment) | G4 |

### 5.2 Payments

| ID | Requirement | Priority | Gap |
|---|---|---|---|
| FR-ID-020 | QRIS (static and dynamic), virtual accounts, e-wallets and cards via at least one licensed Indonesian gateway at launch. | M | G8 |
| FR-ID-021 | Payment links shareable over WhatsApp with IDR amount and expiry; DP (partial deposit) schedules. | M | G8 |
| FR-ID-022 | Transfer-proof intake: guest uploads screenshot; system extracts bank, amount, date, reference; matches to bank statement import or VA; flags duplicates and edited images for human review. | M | G7 |
| FR-ID-023 | Cash-first operations: drawer, deposits to bank, refunds by transfer with proof. | M | G8 |

### 5.3 Channel Manager

| ID | Requirement | Priority | Gap |
|---|---|---|---|
| FR-ID-030 | Launch connections: Traveloka, Tiket.com, Agoda, Booking.com, Airbnb, Google (free booking links); Trip.com and Expedia second wave. | M | — |
| FR-ID-031 | Map OTA promotion programmes (channel-funded discounts, flash sales, cashback) and show net rate per channel. | S | G17 |
| FR-ID-032 | Support Traveloka/Tiket-specific content and policy fields (e.g., breakfast, check-in rules, payment at hotel). | M | — |

### 5.4 CRM & Guest Engagement

| ID | Requirement | Priority | Gap |
|---|---|---|---|
| FR-ID-040 | WhatsApp Business API as the primary channel: inbox, approved templates in Bahasa, payment links, booking confirmations, pre-arrival, review requests. | M | G6 |
| FR-ID-041 | Instagram and TikTok DM intake (where APIs allow) and a "DM to booking" flow: AI extracts dates/guests/unit → availability → quote → payment link → confirmation, all inside the thread. | S | G6 |
| FR-ID-042 | Google Business Profile reviews and messages in the inbox; Traveloka/Tiket review aggregation. | M | — |
| FR-ID-043 | Journeys templated for Indonesian guests: Bahasa, WhatsApp-first, holiday greetings (Lebaran, Natal, Imlek, Nyepi) with opt-in. | S | G9 |

### 5.5 RMS

| ID | Requirement | Priority | Gap |
|---|---|---|---|
| FR-ID-050 | Indonesian event packs: national holidays, cuti bersama, provincial school holidays, Lebaran/mudik windows, Ramadan, Nataru, Nyepi and Bali ceremonies, major city events. | M | G9 |
| FR-ID-051 | Channel-cost-aware recommendations including OTA promotion participation. | S | G17 |

### 5.6 Operations (Housekeeping & Maintenance)

| ID | Requirement | Priority | Gap |
|---|---|---|---|
| FR-ID-060 | WhatsApp-based task notifications and status replies for staff without the app. | S | G11 |
| FR-ID-061 | Offline task list sync for remote properties. | S | G10 |
| FR-ID-062 | Instruction translation to Bahasa and (where model quality allows) regional languages. | C | G11 |

### 5.7 AI Assistant Layer

| ID | Requirement | Priority | Gap |
|---|---|---|---|
| FR-ID-070 | Bahasa Indonesia and colloquial chat ("bahasa gaul", abbreviations) handled in intent classification and drafting; English for international guests. | M | G6, G11 |
| FR-ID-071 | Transfer-proof screenshot reading (vision) with structured output and confidence; never auto-confirms payment without a match. | M | G7 |
| FR-ID-072 | KTP/passport OCR with field validation; data handled under the identity-document data class (approved providers/regions only). | M | G14 |
| FR-ID-073 | Rooming-list extraction from Excel/WhatsApp images for group bookings. | S | G12 |
| FR-ID-074 | Per-property AI budget denominated in IDR with default caps by property size. | M | — |

---

## 6. Data Residency, Privacy and AI Providers

| Topic | Position |
|---|---|
| **Hosting** | Run the platform in a Jakarta cloud region (AWS ap-southeast-3, Google Cloud asia-southeast2, Alibaba Cloud Jakarta; Microsoft Indonesia Central **[verify GA status]**). Keeps guest PII, identity documents and financial records in-country, which simplifies PDP compliance and customer conversations even where the law permits transfer. |
| **PDP Law (UU 27/2022)** | Fully in force since October 2024. Cross-border transfer (Art. 56) requires adequacy of the destination, or adequate safeguards, or data-subject consent; the Constitutional Court upheld the tiered framework in 2025 and implementing regulations and a data protection authority are still being completed **[verify current status]**. Obtain explicit consent wording for any processing that crosses the border, keep records of processing, appoint a DPO when thresholds apply, and implement data-subject rights (already in PMS FR-GST-008, CRM FR-CRM-012). |
| **AI providers** | Hosted Claude models are reachable from the Jakarta AWS region via cross-region inference profiles; in-region availability varies by model and must be checked against the live AWS availability table. Google's Jakarta region may offer in-region models **[verify]**. Policy: (1) PII minimisation before any AI call (names → placeholders, document numbers never sent unless the feature requires it); (2) identity-document OCR only through providers/regions approved for that data class, or a local OCR service; (3) consent and privacy notice name AI processing; (4) per-feature data-policy enforcement in the AI Gateway (FR-AI-007). |
| **Government systems** | APOA (Imigrasi), regional tax portals (Bapenda per region), BPS statistics, OSS/NIB business licensing, CHSE certification — all are candidates for integration or export; verify API availability per system, most will start as assisted export. |
| **Language of records** | Contracts and consumer-facing terms in Bahasa Indonesia (Law 24/2009 and Perpres 63/2019 on use of Indonesian in agreements) **[verify applicability to online terms]**. |

---

## 7. Go-to-Market Sequence

| Phase | Months | Product | Segment | Channel to market |
|---|---|---|---|---|
| 0 | 0–3 | WhatsApp inbox + payment links (QRIS/VA) + transfer-proof verification; free tier | Bali villas/guesthouses; Yogyakarta/Bandung guesthouses | WhatsApp onboarding agents, Instagram, villa managers |
| 1 | 3–6 | Channel Manager (Traveloka, Tiket, Agoda, Booking, Airbnb, Google) + Booking Engine (WhatsApp-confirm flow) | Same + ex-aggregator budget hotels | PHRI branches, gateway partner co-marketing |
| 2 | 6–12 | PMS Core with Indonesian tax pack, APOA, KTP/passport OCR; Operations mobile | Budget hotels, villas | Direct sales in 4 cities; reseller agents |
| 3 | 9–15 | Kos module; Owner pack (IDR) | Kos owners (Jakarta, Depok, Bandung, Yogyakarta, Surabaya); villa managers | Kos communities, villa management companies |
| 4 | 12–18 | RMS with Indonesian calendar; CRS Lite; AI v1 full bundle | Small chains, active revenue managers | Upsell inside base |
| 5 | 18+ | Offline PMS Lite for islands; homestay clusters | Priority destinations | Tourism offices, cooperatives |

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| Traveloka/Tiket connectivity requires partner certification or a connectivity partner; timelines uncertain | Start certification immediately; use a certified intermediary for launch while direct connection is pursued |
| RedDoorz counters by offering "software-only" to partners | Our differentiation is local compliance, kos/villa/sharia models, and owning the direct channel; keep price below their commission equivalent |
| Incumbent local PMS vendors (VHP, Power Pro) in star hotels | Not our beachhead; target independents and sub-3-star first |
| Regional tax rules vary by regency | Tax packs as configuration, start with Bali, Jakarta, Yogyakarta, Bandung, Surabaya |
| APOA has no public API | Assisted export and semi-automated entry; lobby via associations; keep audit trail |
| Low willingness to pay | Free wedge; IDR per-room pricing; AI metered with low default caps; value framed against commissions and no-show losses |
| Regional-language AI quality | Bahasa first; regional languages only where tested |

---

## 9. Open Questions

| # | Question |
|---|---|
| Q1 | Which connectivity route for Traveloka and Tiket.com at launch (direct vs. partner), and what are the certification requirements? |
| Q2 | Which payment gateway(s) at launch, and are we a merchant-of-record or integrator only? |
| Q3 | Does APOA expose any integration path beyond the app/QR flow? |
| Q4 | Which regencies mandate online transaction reporting / tapping boxes, and what formats? |
| Q5 | Kos first or villas first for the long-stay/owner modules? (Bali villas recommended for revenue; kos for volume.) |
| Q6 | Status of PDP implementing regulations and the data protection authority at time of launch. |
| Q7 | In-region AI model availability in Jakarta for the chosen provider at time of build. |

---

## Sources

- Imigrasi: hotels must report foreign guests via APOA — [imigrasi.go.id (Mar 2025)](https://imigrasi.go.id/berita/2025/03/26/pengelola-penginapan-wajib-lapor-keberadaan-tamu-asing-lewat-apoa), [CNN Indonesia](https://www.cnnindonesia.com/nasional/20250327173414-25-1213826/ditjen-imigrasi-pengelola-penginapan-wajib-laporkan-tamu-wna-via-apoa), [Bisnis.com](https://kabar24.bisnis.com/read/20250326/15/1864968/ada-aturan-baru-prabowo-bakal-awasi-gerak-gerik-orang-asing-di-ri), [Antara Jatim (Madiun)](https://jatim.antaranews.com/berita/1035118/kantor-imigrasi-madiun-perkuat-pengawasan-orang-asing-lewat-apoa), [Times Indonesia (Kediri)](https://timesindonesia.co.id/peristiwa-daerah/591441/imigrasi-kediri-perketat-pengawasan-wna-lewat-apoa), [APOA guide, Imigrasi Yogyakarta](https://jogja.imigrasi.go.id/wp-content/uploads/2025/09/Panduan-Aplikasi-APOA-1.pdf), [IDX Channel (Tangerang)](https://www.idxchannel.com/news/penginapan-di-tangerang-kini-wajib-laporkan-data-tamu-wna/all)
- PBJT hotel services under UU HKPD — [Ortax: jenis objek PBJT](https://ortax.org/kenali-jenis-objek-pbjt), [DDTC: UU HKPD atur ulang pajak jasa hotel](https://news.ddtc.co.id/uu-hkpd-atur-ulang-ketentuan-pajak-atas-jasa-hotel-ini-perinciannya-35111), [DDTC: apa itu PBJT jasa perhotelan](https://news.ddtc.co.id/apa-itu-pbjt-jasa-perhotelan-di-uu-hkpd-1802161), [DDTC: PPN vs PBJT](https://news.ddtc.co.id/berita/nasional/1803539/hotel-sediakan-jasa-biro-perjalanan-wisata-kena-pajak-ppn-atau-pbjt), [Kemenko Ekonomi on PBJT incentives](https://ekon.go.id/unduh/publikasi/5602/menjaga-pemulihan-sektor-pariwisata-di-daerah-pemerintah-siapkan-insentif-fiskal-untuk-pbjt-jasa-kesenian-dan-hiburan)
- RedDoorz / OYO / market — [TTG Asia: 100th Sans](https://www.ttgasia.com/2025/08/07/reddoorz-opens-100th-sans-in-bali-amid-rising-budget-demand/), [TTG Asia: 150 company-operated hotels by 2027](https://www.ttgasia.com/?p=115977), [Skift: Amit Saberwal (Apr 2026)](https://skift.com/2026/04/09/amit-saberwal-on-growing-hotels-in-a-shifting-market/), [Investortrust: RedDoorz +25% H1 2025](https://investortrust.id/business/75450/transformasi-digital-bikin-pendapatan-reddoorz-naik-25-di-semester-i-2025), [Industry.co.id: independents 62.85%](https://www.industry.co.id/read/148310/pacu-pertumbuhan-di-indonesia-reddoorz-tambah-100-hotel-yang-dikelola-langsung), [Sacra: OYO](https://sacra.com/research/oyo-rooms), [KrASIA: OYO in SEA](https://kr-asia.com/as-oyo-casts-its-shadow-on-southeast-asia-its-traditional-budget-hotels-who-will-suffer-most)
- Kos / co-living — [DailySocial: Mamikos Singgahsini](https://en.dailysocial.id/post/Stopover-services-are-a-strategy-for-expanding-the-Mamikos-business-in-cooperation-with-property-owner-partners), [DailySocial: Rukita](https://en.dailysocial.id/post/get-to-know-startup-proptech-rukita-provide-co-living-services), [Rukita expansion Oct 2025](https://www.rukita.co/stories/rukita-expansion-coliving-units), [DailySocial: Rukita RuOptions](https://en.dailysocial.id/post/make-it-easy-for-property-owners-to-manage-business-rukita-launches-ruoptions-service)
- AI region availability — [AWS: Bedrock regional availability by model](https://docs.aws.amazon.com/bedrock/latest/userguide/models-region-compatibility.html), [AWS blog: global cross-region inference incl. Indonesia](https://aws.amazon.com/blogs/machine-learning/global-cross-region-inference-for-latest-anthropic-claude-opus-sonnet-and-haiku-models-on-amazon-bedrock-in-thailand-malaysia-singapore-indonesia-and-taiwan), [Claude on Amazon Bedrock](https://platform.claude.com/docs/en/api/claude-on-amazon-bedrock)
- PDP Law cross-border — [Conflict of Laws: Constitutional Court decision on Art. 56](https://conflictoflaws.net/2026/cross-border-personal-data-transfers-the-remaining-issues-following-the-indonesian-constitutional-court-decision/), [SSEK: Data protection in Indonesia overview](https://ssek.com/blog/data-protection-in-indonesia-a-brief-overview/), [Rajah & Tann: PDP Law updates](https://www.rajahtannasia.com/?p=188802), [Norton Rose Fulbright: PDP Law highlights](https://www.nortonrosefulbright.com/en-il/knowledge/publications/31bce8f0/highlights-of-indonesias-personal-data-protection-law)
