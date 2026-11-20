# Phase 0 Wedge — WhatsApp Inbox, Payment Links, Transfer-Proof Verification (Free Tier)

Source: `reading/hospitality/indonesia-market-entry-strategy.md` §7 (Phase 0, months 0–3), with §3.1, §4 (G6, G7, G8), §5.2 (FR-ID-020 to 022) and §5.4 (FR-ID-040).

## Problem

Independent villas and guesthouses in Bali, Yogyakarta and Bandung take most direct bookings as WhatsApp chats and get paid by QRIS, virtual account or manual bank transfer with a screenshot ("bukti transfer"). Today staff answer from personal phones, retype requests into spreadsheets, and check each screenshot by hand against the bank app. Replies are slow, deposits are missed or faked, and nobody can see which enquiry has been paid.

Left unsolved, the property loses direct bookings to slower replies and unpaid holds, and we have no trusted first product to land before Channel Manager (Phase 1) and PMS Core (Phase 2).

## Evidence

- Assumption — needs validation via 10–15 operator interviews and a pilot with 5 properties in Bali and Yogyakarta. No direct user evidence exists yet; the only source is the strategy document.
- Strategy doc §4 G6: "most direct bookings for villas and guesthouses arrive as chat; staff type them into spreadsheets" (unsourced observation).
- Strategy doc §4 G7: "guests pay by bank transfer and send a screenshot; staff verify manually against bank mutations" (unsourced observation).
- Strategy doc §1: independents hold roughly 63% of Indonesia's hotel property market (Mordor Intelligence via Industry.co.id, 2025).

## Users

- **Primary**: the owner-operator or front-desk staff member of an independent villa or guesthouse (1–30 units) in Bali, Yogyakarta or Bandung, who answers guest chats and collects deposits personally. The need is triggered every time a guest asks "available?" or sends a transfer screenshot.
- **Secondary**: a villa manager handling several owners' properties from one login.
- **Guest** (indirect): receives replies and a payment link in WhatsApp, pays, and may upload a transfer proof. Has no account.
- **Not for**: star-rated hotels with an existing PMS, kos-kosan owners (Phase 3), chains needing cross-property reporting (Phase 4), and properties with no WhatsApp-based enquiries.

## Hypothesis

We believe **a shared WhatsApp inbox with payment links and one-click transfer-proof approval, free to start** will **cut reply time and stop missed or unverified deposits** for **owner-operators of independent villas and guesthouses**.
We'll know we're right when **a pilot property sends at least 5 payment links a week from the inbox and settles at least 70% of them inside the product within 4 weeks of onboarding**.

*Drafted from the strategy doc — the targets are proposals, not validated numbers.*

## Success Metrics

| Metric | Target | How measured |
|---|---|---|
| Time from sign-up to first payment link sent | Under 1 day ("land in a day", §3.1) | Timestamps: tenant created → first link created |
| Payment links sent per active property per week | ≥ 5 | Count of links created, per property |
| Share of links settled in-product (gateway payment or approved proof) | ≥ 70% | Links paid ÷ links sent |
| Median time from proof upload to staff decision | Under 10 minutes in working hours | Proof uploaded → approved/rejected timestamps |
| Median first-reply time to a new guest chat | Under 15 minutes between 08:00 and 21:00 local time (provisional — revise after 2 weeks of pilot data) | Inbound message → first outbound message |
| Pilot properties still active in week 4 | At least 60% (3 of 5 pilot properties) (provisional — revise after the pilot) | Properties with ≥ 1 link or reply in week 4 |

## Scope

**MVP** — everything below works end to end with **simulated** WhatsApp and payment providers, so it runs with no external accounts or keys; real providers replace the simulators later without changing behaviour.

1. **Property onboarding.** An operator signs up, names the property and is ready to use the inbox. The property lands on the Free plan automatically.
2. **Shared inbox.** Staff see all guest conversations for their property, newest first, with unread state; open a thread; read the history; reply. Inbound guest messages appear without a manual refresh step being required to find them. Staff can mark a conversation resolved.
3. **Payment links.** From a conversation (or standalone), staff create a link for an IDR amount with a description and expiry, optionally as a down payment (DP) of a stated total. The link is sent into the thread. The guest opens a public page showing the property, amount and expiry, and can pay by QRIS or virtual account (simulated). Staff see each link's state: pending, paid, expired, cancelled.
4. **Transfer-proof verification.** A guest who paid by manual transfer uploads a screenshot on the public payment page, or staff upload one received in chat. Staff see the image next to the expected amount and approve or reject with a reason. Approval marks the link paid; rejection tells the guest. The same screenshot submitted twice is flagged. When a guest paid by transfer without any link, staff record the payment themselves and attach the screenshot. A proof above Rp 5.000.000 needs a second staff member's approval; the property owner may approve alone. Screenshots are deleted 90 days after the decision.
5. **Free tier.** Every property is on a Free plan with one limit: 30 payment links per month. Usage against the limit is visible to the operator, and the product refuses a new link with a clear message when the limit is reached.
6. **Tenant separation.** Staff of one property never see another property's conversations, links, proofs or guests.
7. **Configurable business values.** The numbers below are starting values, not fixed rules. Each can be changed later without a code change, and the product uses the new value from then on:

   | Value | Starting value | Set per |
   |---|---|---|
   | Free plan payment links per month | 30 | plan |
   | Second-approver threshold for transfer proofs | Rp 5.000.000 | property |
   | Screenshot retention | 90 days | property |
   | Payment link default expiry | TBD at planning | property |
   | First-reply-time target | 15 minutes | property |
   | Working hours used for the reply-time measure | 08:00–21:00 local | property |
   | Week-4 retention target | 60% of pilot properties | platform |

8. **Language.** Guest-facing pages open in Bahasa Indonesia and each guest can switch to English; staff screens are usable in both.

**Out of scope**

- Real WhatsApp Business API and real payment gateway connections — deferred until provider choice and accounts exist (strategy Q2); simulators stand in.
- AI reading of transfer screenshots (FR-ID-022 extraction, fake detection) — staff confirm manually in this phase; needs an approved AI provider and key.
- AI drafting of replies and "DM to booking" extraction (FR-ID-041) — Phase 3+ AI bundle.
- Instagram, TikTok, Google Business and OTA messages in the inbox — WhatsApp only.
- Reservations, availability, rates, folios, invoices and tax — PMS Core, Phase 2. A payment link is not tied to a booking record.
- Channel Manager and Booking Engine — Phase 1.
- Paid plans, billing and upgrade payment — limits only.
- Refunds, cash drawer, bank-statement import and settlement reconciliation (FR-ID-023) — later payments work.
- WhatsApp template approval workflow, campaigns and automated journeys.
- WhatsApp OTP (phone-number) sign-in — existing email sign-in is used for the pilot.
- Native mobile apps and offline use.

## Delivery Milestones
<!-- Business outcomes, not engineering tasks. /plan turns each into a plan. -->
<!-- Status: pending | in-progress | complete -->

| # | Milestone | Outcome | Status | Plan |
|---|---|---|---|---|
| 1 | Property workspace | An operator can sign up, create a property on the Free plan, and sign in to an empty workspace that only shows their own data | complete | `.claude/plans/phase-0-m1-property-workspace.plan.md` |
| 2 | WhatsApp inbox | Staff can see guest conversations, read threads and reply; a simulated guest can send messages in | complete | `.claude/plans/phase-0-m2-whatsapp-inbox.plan.md` |
| 3 | Payment links | Staff can create and send an IDR payment link; a guest can open it and pay by simulated QRIS or VA; staff see it turn paid or expire | pending | — |
| 4 | Transfer-proof verification | A guest or staff member can upload a transfer screenshot; staff approve or reject it and the link updates; duplicates are flagged | pending | — |
| 5 | Free-tier limit | Operators see payment links used this month against the plan limit and are stopped, with a clear message, when it is reached | pending | — |

## Decisions (answered by product owner, 2026-11-20)

| Topic | Decision |
|---|---|
| WhatsApp route | Direct WhatsApp Cloud API; each property brings its own number. Simulated in this MVP |
| Free plan limit | One limit only: 30 payment links per month. No limit on units or messages |
| Transfer paid outside any link | Staff handle it: staff record the payment and attach the screenshot the guest sent in chat. No separate guest upload page for this case |
| Second approver | A transfer proof above Rp 5.000.000 needs approval by a second staff member. The property owner may approve alone, so a one-person property is not blocked |
| Guest page language | Bahasa Indonesia by default; each guest can switch to English on the page |
| Payment gateway (after MVP) | Xendit first, as integrator only (not merchant-of-record): one sub-account per property, funds settle to the property's own bank account. Midtrans is the second option. Simulated in this MVP |
| Screenshot retention | 90 days after the decision, then the image is deleted; the payment record stays |
| Sign-in | Existing email sign-in is enough for the pilot. WhatsApp OTP sign-in is deferred |
| Consent wording at upload | Accepted as drafted, shown beside the upload button. ID: "Dengan mengunggah bukti transfer, Anda menyetujui {nama properti} menyimpan gambar ini untuk memverifikasi pembayaran Anda. Gambar dihapus setelah 90 hari." EN: "By uploading this transfer proof, you agree that {property name} stores the image to verify your payment. The image is deleted after 90 days." |
| Reply-time and retention targets | Provisional targets set (see Success Metrics); revise once pilot data exists |
| Configurability | Targets, limits and thresholds are configurable values with the agreed numbers as defaults (see Scope item 7); the product owner will update them later |

## Open Questions

- [ ] Xendit fees, sub-account onboarding steps and current terms — to be confirmed with the provider before signing (agreed by product owner). Does not block the MVP.
- [ ] Consent wording has not been reviewed by Indonesian legal counsel; the product owner accepted the draft as is. Revisit if counsel becomes available before public launch.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Problem is assumed, not evidenced; operators may be content with personal WhatsApp | Medium | High | Interview 10–15 operators and run a 5-property pilot before investing in real provider integrations |
| Simulated providers hide real constraints (WhatsApp 24-hour reply window, template rules, gateway callbacks and fees) | High | Medium | Make simulators follow the documented provider rules; revisit the PRD when providers are chosen |
| Staff approve a fake or reused transfer screenshot | Medium | High | Show expected amount beside the image, flag duplicates, record who approved; add AI checks and bank matching later |
| Tenant data leaks between properties | Low | High | Treat tenant separation as an acceptance condition of every milestone |
| Free tier attracts usage with no path to revenue | Medium | Medium | Limits enforced from day one; paid plans arrive with Phase 1 Channel Manager |
| Low willingness to change habits among low-digital-literacy staff | Medium | Medium | Bahasa-first screens, few steps per task, onboarding over WhatsApp by local agents (§7 channel) |
| Guest PII and financial screenshots stored without clear consent | Medium | High | Consent notice at upload; retention period decided before pilot (open question) |

---
*Status: DRAFT — requirements only. Implementation planning pending via /plan.*
