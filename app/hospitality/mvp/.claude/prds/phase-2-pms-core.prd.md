# Phase 2 — PMS Core with Indonesian Compliance and Operations Mobile

Source: `reading/hospitality/indonesia-market-entry-strategy.md` §7 (Phase 2, months 6–12), with §4 (G1, G2, G8, G11, G14, G18), §5.1 (FR-ID-001 to 004, 009, 011), §5.6, §5.7 (FR-ID-072) and §6; `reading/hospitality/property-management-system-functional-requirements.md` §6.7, 6.8, 6.9, 6.11 to 6.13, 6.15 and 6.26; `reading/hospitality/housekeeping-maintenance-functional-requirements.md`.

## Problem

Owner-operators and front-desk staff at Indonesian budget hotels and villas can now take bookings in the product, but still run the stay itself on paper, spreadsheets and chat. They re-type passports into APOA, work out regional hotel tax by hand, keep guest bills and cash separately, and coordinate cleaning by message.

Left unsolved, properties risk missed foreign-guest reports and wrong tax, cash cannot be reconciled at the end of the day, rooms are not ready on time, and the product stays an add-on that is easy to drop rather than the system the property runs on.

## Evidence

- Foreign-guest reporting through APOA is a legal duty for accommodation providers, with a renewed enforcement push in 2025 (strategy §4 G1 and its sources).
- PBJT hotel tax is set regionally up to 10%, and some regions require online reporting (strategy §4 G2). **[verify per region]**
- Staff re-typing passports, manual tax returns, and cash and deposit handling are described in the strategy (G1, G2, G8, G18). This is desk research.
- Assumption — the size of this pain and operators' willingness to move their daily work into the product needs validation via interviews and observed use at the Phase 2 pilot properties.

## Users

- **Primary**: Front-desk staff and owner-operators at independent budget hotels and villas, often with one person covering several jobs. The need arises at every arrival, departure, payment and end of day.
- **Secondary**: Housekeepers and maintenance staff working from a phone, some with low digital literacy.
- **Not for**: Star hotels with full accounting and POS needs, chains needing central reservations, kos operators, and villa managers needing owner statements (Phase 3 and later).

## Hypothesis

We believe **one daily front-desk flow with correct tax, assisted APOA reporting and guest ID capture** will **replace paper and spreadsheets** for **budget hotels and villas**.
We'll know we're right when **5 pilot properties run every check-in and check-out in the product for 30 straight days, and at least 90% of foreign guests are logged as reported to APOA on time**.

## Success Metrics

Targets are proposed and should be reviewed after the first pilot month.

| Metric | Target | How measured |
|---|---|---|
| Pilot properties using the daily loop | 5 properties for 30 straight days | Share of stays with a recorded check-in and check-out |
| Foreign guests reported on time | At least 90% | Submission log against the deadline, once the deadline is verified |
| Days closed | At least 90% of operating days per pilot property | End-of-day records |
| Bills that balance at check-out | 100% settled or carrying a recorded balance | Guest bill records |
| Time to complete a foreign-guest check-in | TBD — needs a baseline via observation at pilot properties | Timed observation before and after |
| Housekeeping updates made on a phone | At least 80% of room status changes | Status history by device type |

## Scope

**MVP**

- **Front desk**: individual rooms, room assignment and moves, arrivals, in-house and departures, check-in and check-out, early and late handling, no-shows.
- **Guest bill**: room charges, extras, discounts and corrections with reasons, deposits, cash, transfer and existing payment methods, refunds, receipt, and a check-out that shows the balance.
- **Tax pack**: PBJT and service charge as separate lines, nett and ++ pricing, configurable region settings with starter values for Bali, Jakarta, Yogyakarta, Bandung and Surabaya, and a monthly tax summary export. Starter values must be verified before use.
- **Guest ID**: KTP/NIK for domestic guests; passport, visa type and permit for foreigners; a scan, review and correct flow using a simulated reader, replaceable by an approved provider. Staff always confirm the fields. Access is restricted, viewed records are logged, and retention follows the policy decided below.
- **APOA**: a worklist of foreign guests to check in to and out of APOA, the passport photo ready for APOA's manual check-in, a record of who submitted it and when, overdue alerts, and a register for immigration officers. Staff still submit in the official APOA system, which reads the passport itself and has no import or API (checked against the official guide, Nov 2026).
- **End of day**: daily close with checks, cash book, shift totals and a daily summary.
- **Operations mobile**: phone-friendly room status board, cleaning tasks from arrivals and departures, a big-button mode, and maintenance requests that can take a room off sale.
- **Access and language**: every feature has its own permission, every action that affects money or identity data is in the history, and all text is in Bahasa Indonesia first and English second.

**Out of scope**

- Group bookings and shared group bills — large separate workflow, strategy G12.
- Company accounts and city ledger — not needed by the first segment.
- POS, restaurant tax and outlets — separate product.
- Leases and kos, owner statements — Phase 3.
- Tapping-box devices and direct filing to regional tax portals — formats vary and need verification per region.
- Automated APOA submission — no known public integration path (strategy Q3).
- Real OCR provider — needs approval for identity data under the PDP Law.
- Offline mode — Phase 5, for low-connectivity islands.
- Native mobile app — the phone web experience is tested first.
- WhatsApp task updates for staff — considered after the phone flow is proven.
- Reseller commissions and sales tools — direct sales and reseller recruitment are business activities outside this product scope.

## Delivery Milestones

<!-- Business outcomes, not engineering tasks. /plan turns each into a plan. -->
<!-- Status: pending | in-progress | complete -->

| # | Milestone | Outcome | Status | Plan |
|---|---|---|---|---|
| 1 | Rooms and front desk | Staff assign real rooms and check guests in and out from today's arrivals and departures | complete | `.claude/plans/phase-2-m1-rooms-front-desk.plan.md` |
| 2 | Guest bill | Staff see every charge and payment on one bill, settle it at check-out and give a receipt | complete | `.claude/plans/phase-2-m2-guest-bill.plan.md` |
| 3 | Tax pack | Bills show correct PBJT and service charge for the property's region, in nett or ++ pricing | complete | `.claude/plans/phase-2-m3-tax-pack.plan.md` |
| 4 | Guest ID | Staff capture and confirm KTP or passport details at check-in, with restricted access | complete | `.claude/plans/phase-2-m4-guest-id.plan.md` |
| 5 | APOA reporting | Staff submit foreign guests from prepared data and can see what is reported or overdue | complete | `.claude/plans/phase-2-m5-apoa.plan.md` |
| 6 | End of day | An operator closes the day and sees cash, shift totals and what still needs attention | complete | `.claude/plans/phase-2-m6-end-of-day.plan.md` |
| 7 | Housekeeping on phone | Housekeepers see their rooms and update status from a phone, and the front desk sees it at once | complete | `.claude/plans/phase-2-m7-housekeeping.plan.md` |
| 8 | Maintenance and tax export | Staff report repairs that can block a room, and an owner exports the monthly tax summary | complete | `.claude/plans/phase-2-m8-maintenance-tax-export.plan.md` |

## Open Questions

- [ ] What are the current PBJT rates, exemptions and return formats for each starter region? Verify against official regional sources before the pilot.
- [ ] What is the exact APOA reporting deadline, and which fields and export formats does it accept? Verify with Imigrasi.
- [ ] Which OCR provider and region are approved for identity data under the PDP Law?
- [ ] How long may ID images be kept, or should only extracted fields be stored? Proposed default: delete images after check-out unless the law requires longer retention. Needs legal review.
- [ ] Which 4 cities are the direct-sales focus? The strategy names 4 cities for sales and 5 tax regions.
- [ ] Should prices already published on channels change when a property switches between nett and ++ pricing?
- [ ] Which 5 properties will join the pilot, and can a baseline be observed before they start?

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Wrong tax rate or calculation on guest bills | Medium | High | Rates are configuration, verified before use, with changes logged and past bills unchanged |
| Identity data leaked or kept too long | Medium | High | Restricted access, logged views, data stays in-country, retention policy with legal review |
| Simulated OCR mistaken for a working real reader | Medium | Medium | Clearly labelled in the product; staff confirm every field |
| APOA changes its fields or process | Medium | Medium | Field mapping is adjustable; staff submit in the official system |
| Staff mark a guest as reported without submitting | Medium | High | Named record with time, and the product states that submission happens in APOA |
| Daily close blocks a busy front desk | Medium | High | Clear list of what is blocking, with a permitted override that is logged |
| Bills and existing Phase 0 and 1 payments disagree | Medium | High | Existing bookings and payments carried onto bills, with balances reconciled and tested |
| Scope grows toward the full 155 must-have list | High | High | Only the daily loop is in scope; other requests go to later phases |
| Low-literacy staff do not adopt the phone flow | Medium | Medium | Big-button mode, Bahasa first, observed at pilot properties |

---
*Status: DRAFT — requirements only. Implementation planning pending via /plan.*
