# Phase 1 — Channel Manager and Direct Booking Page (WhatsApp-confirm)

Source: `reading/hospitality/indonesia-market-entry-strategy.md` §7 (Phase 1, months 3–6), with §3.1, §4 (G6, G8) and §5.3 (FR-ID-030 to 032); `reading/hospitality/channel-manager-functional-requirements.md` (FR-CM, BR-CM); `reading/hospitality/booking-engine-functional-requirements.md` (FR-BE, BR-BE). Builds on Phase 0 (`.claude/prds/phase-0-whatsapp-wedge.prd.md`): WhatsApp inbox, payment links, transfer-proof verification.

## Problem

An independent villa or guesthouse sells the same rooms on several online travel agencies (Traveloka, Tiket.com, Agoda, Booking.com, Airbnb) and directly over WhatsApp. Staff update availability and prices by hand in each extranet and retype every booking into a spreadsheet, so a room sold on one channel stays open on the others. The two most expensive results are double bookings and prices that differ between channels. Direct guests have no page where they can check dates and book, so they wait for a chat reply or book through an agency that charges commission.

Left unsolved, properties keep paying commission on bookings they could take directly, lose money and reviews to overbookings, and we have no paid product to follow the free Phase 0 wedge.

## Evidence

- Assumption — needs validation via the Phase 0 pilot properties (ask each how many channels they sell on, how they update them, and how many double bookings they had last quarter) and 10–15 interviews with ex-aggregator budget hotels. No direct user evidence exists yet; the sources are the strategy and requirements documents.
- Channel Manager requirements §1: overbookings and rate-parity errors are "the two most expensive mistakes in small-property distribution" (unsourced).
- Strategy §4 G6: most direct bookings for villas and guesthouses arrive as chat and are typed into spreadsheets (unsourced observation).
- Strategy §4 G8: deposits ("DP 50%"), cash on arrival and refunds by transfer are the norm; foreign booking engines assume a card guarantee (unsourced observation).
- Strategy §3.1: properties leaving RedDoorz and OYO already know what a channel manager is and now need their own (unsourced).

## Users

- **Primary**: the owner-operator or revenue-minded manager of an independent villa, guesthouse or budget hotel (1–30 units) already using the Phase 0 inbox, who lists on two or more channels and updates them by hand. The need is triggered every time a booking arrives or a price changes.
- **Secondary**: front-desk or reservations staff who handle bookings that need attention (possible double booking, a channel room that is not matched to one of ours).
- **Guest** (indirect): finds the property through Instagram, Google or a shared link, checks dates and price, books, pays a deposit and gets confirmation in WhatsApp. Has no account.
- **Not for**: properties on a third-party PMS wanting only the channel manager (standalone sale is deferred), chains needing multi-property search, hostels sold by the bed, hourly units, kos-kosan (Phase 3), and properties that need GDS or wholesaler allotments.

## Hypothesis

We believe **one calendar of rooms, prices and availability that updates every connected channel, receives every booking, and powers a direct booking page with a deposit and WhatsApp confirmation** will **stop double bookings and manual re-keying and move some bookings to commission-free direct sale** for **independent villas, guesthouses and ex-aggregator budget hotels**.
We'll know we're right when **a pilot property keeps at least one channel connected for 4 weeks with no double booking caused by a missed update, and takes at least 3 paid direct bookings through the booking page in that time**.

*Drafted from the source documents — the targets are proposals, not validated numbers.*

## Success Metrics

All targets are provisional and are configurable values where the product acts on them; revise after pilot data exists.

| Metric | Target | How measured |
|---|---|---|
| Time from a change in the calendar to the channel receiving it | Within 30 seconds (FR-CM-020) | Change saved → channel acknowledgement, from the message log |
| Channel bookings that reach the bookings list without retyping | 100%; none lost, none duplicated | Bookings sent by the channel vs. bookings in the list |
| Double bookings caused by a missed or late update | 0 per pilot property in 4 weeks | Bookings flagged "overbooking risk" where the earlier booking was more than 30 seconds old |
| Time from sign-up to first channel connected and matched | Under 1 day ("land in a day", strategy §3.1) | Tenant created → first channel live |
| Paid direct bookings per pilot property | At least 3 in the first 4 weeks | Bookings from the booking page with deposit paid |
| Direct bookings completed without staff involvement | At least 70% of direct bookings paid by QRIS or VA | Direct bookings paid by gateway ÷ all direct bookings |
| Pilot properties with a channel still connected in week 4 | At least 60% | Properties with a live, healthy connection in week 4 |

## Scope

**MVP** — everything below works end to end with a **simulated online travel agency** and **real iCal calendars**, so it runs without partner certification. Certified connections replace the simulator later without changing behaviour. The property's own calendar is the single source of truth: channels and the booking page only reflect it (BR-CM-01).

1. **Rooms, prices and availability.** The operator lists room types (name, how many units, how many guests), sets one or more rate plans with a price per night, and uses a calendar to change price, close dates and set a minimum stay for any date range. Availability is worked out from units minus bookings.
2. **Bookings list.** One list holds every booking from every source — a channel, the booking page, or entered by staff for a WhatsApp or walk-in guest — with dates, room type, guest, price, source, payment state and status. A booking reduces availability; a cancellation gives it back.
3. **Channel connections.** A catalogue of channels shows what each supports. The operator connects one through guided steps: enter the channel's property ID, match each of our room types and rate plans to the channel's, run a test, go live. A channel can be paused (closed for sale) and resumed with a full refresh. Per-channel settings: commission rate, price increase or decrease, who collects payment (property or channel). (FR-CM-001, 002, 005, 006, 010)
4. **Updates out.** Any change to availability, price or restrictions reaches every connected channel within 30 seconds, sending only what changed. A daily full refresh and an on-demand refresh for a date range are available. Failed updates are retried. The property can hold back a number of units from channels and can keep a rate plan direct-only. (FR-CM-020 to 023, 026, 027)
5. **Bookings in.** New bookings, changes and cancellations from a channel land in the bookings list with the channel's reference, guest details, price, commission and who collects payment. The same message arriving twice has no effect. A booking for a room that is no longer free is still accepted, flagged "overbooking risk" and shown to staff, because the channel has already confirmed it to the guest. A booking for a channel room that is not matched goes to a "needs attention" list. (FR-CM-030 to 033, 035, 036; BR-CM-02, 03, 04)
6. **Calendar links (iCal).** The operator can export a calendar link per room type for Airbnb and similar sites, and import theirs, so dates blocked on either side are blocked on the other. Availability only — no prices or guest details. (FR-CM-003)
7. **Health and history.** A log per channel shows every update sent and booking received, with status, retries and the error in plain words, searchable by date and booking. The property is alerted in the product when an update fails repeatedly, a channel has had no successful update for a set time ("at risk"), a booking is flagged, or a channel room is unmatched. The product can show what each channel last accepted and where it differs from our calendar. (FR-CM-011, 014, 025, 050, 051; BR-CM-05)
8. **Direct booking page.** Each property gets a public page: the guest picks dates and number of guests, sees available room types with the total price and the cancellation and payment terms in plain words, enters name and WhatsApp number, accepts the terms and books. The page opens in Bahasa Indonesia with an English switch and works well on a phone. A link can open the page with dates and room type already filled in. (FR-BE-001, 002, 004, 020, 030, 039, 050, 052, 061, 080)
9. **Deposit and WhatsApp confirmation.** After booking, the guest pays the deposit or the full amount by QRIS, virtual account or manual transfer with a screenshot, using the Phase 0 payment page. The room is held while payment is awaited and released if it is not paid in time. When the payment is confirmed, the booking is confirmed and the guest receives a WhatsApp message with the booking number, dates, amount paid, balance due and a link to view or cancel the booking. The conversation appears in the inbox so staff can carry on from there. (FR-BE-031, 032, 035, 040, 042; strategy G8)
10. **Channel report.** Bookings, nights, revenue, commission and net revenue by source, including direct, for a chosen period. (FR-CM-090)
11. **Plan limit.** The Free plan allows a set number of connected channels (default 1; calendar links and the booking page do not count). Usage is visible and a further connection is refused with a clear message. No billing.
12. **Tenant separation and configuration.** A property sees only its own rooms, bookings, connections and logs. Limits, time windows and defaults in this document are configurable values. Changes to connections and matching are recorded with who and when. (FR-CM-100, 102)

**Out of scope**

- Certified connections to Traveloka, Tiket.com, Agoda, Booking.com, Expedia, Trip.com — need partner certification or a connectivity partner (strategy risk 1, Q1); the simulator stands in.
- Google Free Booking Links, Hotel Ads, Vacation Rentals and Business Profile (FR-CM-080 to 088) — need a Google connectivity partner; pre-filled booking links are built so this can follow.
- Pushing descriptions and photos to channels, and content completeness scores (FR-CM-040 to 042).
- Price comparison across channels ("parity dashboard") and rate shopping (FR-CM-052, 053).
- Channel promotion programmes and net-rate display (FR-ID-031); Traveloka/Tiket-specific content fields (FR-ID-032) — arrive with the certified connections.
- Wholesaler allotments, bed banks, GDS, metasearch (FR-CM-060 to 071).
- Virtual card handling, channel guest messaging, reporting no-shows back to channels (FR-CM-034, 037, 038).
- Commission reconciliation against channel invoices and export to revenue management (FR-CM-091, 092).
- Sale of the channel manager on its own to properties using another PMS (requirements Q2).
- Booking page: promo and corporate codes, extras and upgrades, guest accounts, several rooms in one booking, flexible-date search, filters, group and long-stay flows, embeddable widget and custom branding beyond name and logo, funnel analytics, A/B tests, other currencies, self-service date changes (the guest contacts the property in WhatsApp instead).
- Tax itemisation (PBJT, service charge) — the Indonesian tax pack is Phase 2; prices here are entered and shown as final all-in prices.
- Automatic refunds — staff refund by transfer outside the product and record it.
- Check-in, folios, invoices, housekeeping — PMS Core, Phase 2.
- AI help (matching suggestions, error explanations, weekly summaries) — later AI bundle.
- Billing and paid plans — limit only.

## Delivery Milestones
<!-- Business outcomes, not engineering tasks. /plan turns each into a plan. -->
<!-- Status: pending | in-progress | complete -->

| # | Milestone | Outcome | Status | Plan |
|---|---|---|---|---|
| 1 | Rooms, prices and availability | An operator can set up room types and rate plans and change price, closed dates and minimum stay on a calendar | complete | `.claude/plans/phase-1-m1-rooms-rates-availability.plan.md` |
| 2 | Bookings list | Staff can enter a booking for a WhatsApp or walk-in guest and see every booking in one list; availability follows bookings and cancellations | complete | `.claude/plans/phase-1-m2-bookings-list.plan.md` |
| 3 | Channel connections | An operator can connect the simulated agency, match rooms and rates, pause and resume it, and is stopped at the plan's channel limit | complete | `.claude/plans/phase-1-m3-channel-connections.plan.md` |
| 4 | Updates out | A change in the calendar reaches every connected channel within 30 seconds; staff can see the history, refresh on demand and are warned when a channel falls behind | complete | `.claude/plans/phase-1-m4-updates-out.plan.md` |
| 5 | Bookings in | Channel bookings, changes and cancellations appear in the bookings list on their own, never twice; possible double bookings and unmatched rooms are flagged for staff | complete | `.claude/plans/phase-1-m5-bookings-in.plan.md` |
| 6 | Calendar links | Dates blocked on Airbnb or a similar site block the property's calendar and the other way round | complete | `.claude/plans/phase-1-m6-calendar-links.plan.md` |
| 7 | Direct booking page | A guest can check dates, see the price and terms, book and pay a deposit; the booking is confirmed in WhatsApp and appears in the bookings list and the inbox | complete | `.claude/plans/phase-1-m7-direct-booking-page.plan.md` |
| 8 | Channel report | An operator can see bookings, revenue, commission and net revenue by source for a period | complete | `.claude/plans/phase-1-m8-channel-report.plan.md` |

## Decisions (answered by product owner, 2026-11-20)

| Topic | Decision |
|---|---|
| PRD coverage | Channel Manager and Booking Engine in one PRD |
| Channel connections in this build | A simulated online travel agency plus real iCal calendar links |
| Rooms, prices and availability | A minimal built-in calendar and bookings list in this phase; the Phase 2 PMS extends it |
| Plan | A limit on connected channels as a configurable value, no billing |
| Free plan channel limit | 1 connected channel; calendar links and the booking page are not counted |
| Deposit on direct bookings | 50% by default ("DP 50%"), set per property from 10% to 100%; the balance is paid at the property |
| Hold while a direct booking awaits payment | 60 minutes for QRIS and virtual account; up to 24 hours once the guest has uploaded a transfer screenshot that staff have not yet decided on |
| Cancellation terms on the booking page | Two per rate plan: "free cancellation until N days before arrival" (N set by the property, default 7) or "non-refundable". Refunds are made by staff outside the product |
| Direct-booking deposits and the 30 payment links a month | Not counted — a direct booking is never blocked by the link limit |
| Prices | Entered and shown as final all-in amounts until the Phase 2 tax pack exists, with "sudah termasuk pajak dan layanan" where the property confirms it |
| Booking page address | A hosted page on our domain with a short property name chosen by the owner; the owner's own domain is deferred |
| Meaning of "WhatsApp-confirm flow" | The guest books and pays on the page; the confirmation and all follow-up happen in WhatsApp. Staff do not confirm each request by hand before payment |
| Simulator model | Imitates Booking.com's model for updates and bookings, and includes Traveloka-style "pay at hotel" bookings |
| Configurability | Limits, percentages and time windows above are configurable values with these numbers as defaults |

## Open Questions

- [ ] Connectivity route for the real agencies (strategy Q1: direct certification or a certified intermediary, and which channel first). Does not block the MVP; start the enquiry now because timelines are uncertain.
- [ ] No user evidence yet for the problem in the pilot segment — ask the Phase 0 pilot properties how many channels they sell on and how they update them, before milestone 3.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The simulator hides real channel constraints (rate limits, date windows, certification tests, message formats) | High | High | Make the simulator enforce published limits of the imitated channel; treat the first certified connection as its own project |
| No certified connection by the time the phase ends, so nothing is sellable to agencies' customers | High | High | Start the partner or intermediary process now (open question); real iCal gives pilots something usable meanwhile |
| A late or failed update causes a double booking and the property blames the product | Medium | High | Retry, "at risk" alerts, a visible log, on-demand refresh, option to hold back units |
| iCal is slow (sites read calendars only every few hours) and carries no prices, so double bookings still happen | High | Medium | Say so plainly in the product; recommend holding back a unit; position iCal as a stop-gap |
| The minimal calendar and bookings list are outgrown or contradicted by the Phase 2 PMS | Medium | Medium | Keep them to what the channel manager needs; design Phase 2 as an extension, not a replacement |
| Problem is assumed, not evidenced, for the pilot segment (some list on one channel only) | Medium | High | Ask Phase 0 pilot properties before milestone 3; interviews with ex-aggregator hotels |
| Guests abandon the booking page because they expect to chat first | Medium | Medium | Visible "chat on WhatsApp" option on every step; measure direct bookings completed without staff |
| A held room is never paid for and blocks a real sale | Medium | Medium | Short, configurable hold; release on expiry; staff can release by hand |
| Booking data leaks between properties | Low | High | Tenant separation is an acceptance condition of every milestone |
| Guest names and phone numbers from channels stored without a clear basis | Medium | Medium | Keep only what a booking needs; privacy notice on the booking page; retention decided before pilot |

---
*Status: DRAFT — requirements only. Implementation planning pending via /plan.*
