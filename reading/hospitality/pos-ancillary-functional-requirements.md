# POS Lite & Ancillary Services — Functional Requirements

> **Document type:** Functional Requirements Specification
> **Scope:** Lightweight point of sale for small outlets (breakfast room, bar, shop, reception sales), bookable services (spa, activities, transfers, equipment), gift vouchers, and the interface contract to full third-party restaurant POS systems
> **Positioning:** **Ancillary pack add-on** on the shared platform. Not a full restaurant POS — properties with table service, kitchen display or complex menus integrate a specialised POS via the interface in §3.8.
> **Priority key:** **M** must · **S** should · **C** could
> **Related:** [Portfolio architecture](hospitality-suite-portfolio-architecture.md) · [PMS §6.17](property-management-system-functional-requirements.md) · [Payments](payments-functional-requirements.md) · [Booking Engine](booking-engine-functional-requirements.md)

---

## 1. Purpose

Let small properties sell food, drinks, retail items and services without a second system, post everything to the guest folio or take direct payment, and let larger properties connect their restaurant POS with the same folio and revenue reporting.

---

## 2. Actors

| Role | Responsibilities |
|---|---|
| Outlet staff / cashier | Takes orders, charges to room or payment, closes shift |
| Front desk | Sells items and services at reception |
| Spa / activity coordinator | Manages schedules and bookings |
| Outlet manager | Menus, prices, stock, reports |
| Guest | Orders via QR menu or portal, books services |
| Systems: PMS (folios, in-house list), Payments, Booking Engine / guest portal (pre-sale), external restaurant POS, kitchen printers |

---

## 3. Functional Requirements

### 3.1 Outlets, Menus and Items

| ID | Requirement | Priority |
|---|---|---|
| FR-POS-001 | The system shall define outlets (breakfast, bar, shop, reception, pool bar) with opening hours, revenue department and tax rules. | M |
| FR-POS-002 | The system shall maintain items with categories, prices, modifiers (size, extras), tax class, cost, and availability by outlet and time. | M |
| FR-POS-003 | The system shall support package-entitlement items (breakfast included) that post at zero price and consume the allowance tracked in the PMS. | M |
| FR-POS-004 | The system shall support happy-hour and member pricing by time or guest tag. | S |
| FR-POS-005 | The system shall support simple stock counts and low-stock alerts for retail items. | S |

### 3.2 Selling and Settlement

| ID | Requirement | Priority |
|---|---|---|
| FR-POS-010 | The system shall provide a tablet/phone-friendly order screen with item search, favourites, quantities and modifiers. | M |
| FR-POS-011 | The system shall settle to: room/unit folio (search in-house guests by unit or name, with credit limit check and optional guest signature), card via Payments, cash, voucher, or complimentary with reason. | M |
| FR-POS-012 | The system shall support split bills and partial settlement. | S |
| FR-POS-013 | The system shall print or email receipts and comply with fiscal receipt rules where required. | M |
| FR-POS-014 | The system shall support voids and refunds with permissions and reasons. | M |
| FR-POS-015 | The system shall support tips/service charge handling with tax rules. | S |
| FR-POS-016 | The system shall support open tabs for bars and close-out at shift end. | S |
| FR-POS-017 | The system shall support a QR-code self-order menu for guests with room-charge authentication (unit + last name) or pay-now. | S |
| FR-POS-018 | The system shall support offline order capture with later posting when connectivity returns. | C |

### 3.3 Breakfast and Meal Plans

| ID | Requirement | Priority |
|---|---|---|
| FR-POS-020 | The system shall display today's entitled guests per meal (from PMS meal plans) with check-off, counting covers and flagging non-entitled guests for charging. | M |
| FR-POS-021 | The system shall report meal-plan consumption vs. entitlement for cost control. | S |
| FR-POS-022 | The system shall support all-inclusive entitlements identified by wristband/credential scan. | C |

### 3.4 Bookable Services and Activities

| ID | Requirement | Priority |
|---|---|---|
| FR-POS-030 | The system shall define services with duration, capacity (per slot or per resource such as therapist, bike, kayak), price per person/unit, and schedule. | M |
| FR-POS-031 | The system shall allow staff and guests (portal/booking engine) to book services into slots with availability checks, confirmation and reminders via CRM. | M |
| FR-POS-032 | The system shall post service charges to the folio at booking, at service time or at completion, per configuration. | M |
| FR-POS-033 | The system shall support resource schedules (therapists, guides, vehicles) and their availability/breaks. | S |
| FR-POS-034 | The system shall support cancellation policies and no-show fees for services. | S |
| FR-POS-035 | The system shall support equipment rental with deposit, check-out/check-in condition and overdue tracking. | S |
| FR-POS-036 | The system shall support third-party supplier activities (tours by external operators) with commission tracking. | C |
| FR-POS-037 | The system shall support transfers/airport pickups with flight details and driver assignment. | C |

### 3.5 Gift Vouchers

| ID | Requirement | Priority |
|---|---|---|
| FR-POS-040 | The system shall sell monetary or experience vouchers online and at reception, with unique codes, expiry and terms. | S |
| FR-POS-041 | The system shall redeem vouchers against folios, bookings or POS sales, tracking balance and liability. | S |
| FR-POS-042 | The system shall report voucher liability and breakage. | S |

### 3.6 Reporting

| ID | Requirement | Priority |
|---|---|---|
| FR-POS-050 | The system shall report sales by outlet, item, category, hour, server, payment method, and per-guest ancillary spend, feeding PMS revenue reports and the end-of-day pack. | M |
| FR-POS-051 | The system shall report service utilisation (slots sold vs. available) and resource productivity. | S |

### 3.7 Administration

| ID | Requirement | Priority |
|---|---|---|
| FR-POS-060 | The system shall support roles (cashier, supervisor, outlet manager) with permissions for discounts, voids and refunds. | M |
| FR-POS-061 | The system shall support cash drawer open/close per user and outlet with variance reporting. | M |
| FR-POS-062 | The system shall log all transactions and changes. | M |

### 3.8 Interface Contract for External POS

| ID | Requirement | Priority |
|---|---|---|
| FR-POS-070 | The platform shall expose an API for external POS systems to: look up in-house guests by unit/name, post charges with department, tax and item detail, check credit limits, void same-day postings, and query package entitlements. | M |
| FR-POS-071 | The platform shall accept end-of-day sales summaries from external POS for consolidated revenue reporting. | S |
| FR-POS-072 | The platform shall support standard hospitality POS-to-PMS message formats where available. | S |

---

## 4. Key Business Rules

| ID | Rule |
|---|---|
| BR-POS-01 | Room charges are allowed only for checked-in guests with charge privileges and within credit limits; otherwise payment is required at the outlet. |
| BR-POS-02 | Package-entitled items post at zero to the guest but are recorded at value for revenue allocation. |
| BR-POS-03 | Vouchers are liabilities until redeemed or expired per local rules. |

---

## 5. AI Assistance (API-based, no model training)

| Area | Assistance |
|---|---|
| Menu content | Translate and describe menu items in guest languages, flag allergen statements for human review |
| Upsell | Suggest relevant services in pre-arrival messages based on stay type and past purchases (recommendation, sent through CRM) |
| Reports | Plain-language weekly summary of ancillary spend per guest and under-used service slots |
| Guest self-order | Answer menu questions (ingredients, vegetarian options) from the menu data only |

---

## 6. Open Questions

| # | Question |
|---|---|
| Q1 | Is POS Lite in the initial roadmap, or external POS integration only? |
| Q2 | Fiscal receipt requirements in target countries for outlets? |
