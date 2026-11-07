# Revenue Management System (RMS) — Functional Requirements

> **Document type:** Functional Requirements Specification
> **Scope:** Demand analysis, forecasting, pricing and restriction recommendations, competitor awareness, and revenue reporting for any hospitality property type
> **Positioning:** **Separate system** (Revenue pack add-on), also standalone for third-party PMSs. Rule-based pricing basics live in the PMS; the RMS adds forecasting, recommendations and strategy. Uses transparent statistical methods, not custom-trained machine-learning models, so owners can understand and trust it.
> **Priority key:** **M** must · **S** should · **C** could
> **Related:** [Portfolio architecture](hospitality-suite-portfolio-architecture.md) · [PMS](property-management-system-functional-requirements.md) · [Channel Manager](channel-manager-functional-requirements.md) · [AI Assistant Layer](ai-assistant-layer-functional-requirements.md)

---

## 1. Purpose

Help the property sell the right unit to the right guest at the right price through the right channel, with the owner understanding *why*. Serve two users: the small owner who wants "set it and check weekly" automation with guard rails, and the revenue manager who wants control over every rule and override.

### In scope
Data ingestion (historical and on-the-books), demand calendar, forecasting, pricing recommendations, restriction recommendations, rules and guard rails, competitor rate intelligence, channel cost awareness, group/long-stay evaluation, budgeting, reporting and alerts.

### Out of scope
Rate distribution (Channel Manager), booking (PMS), pricing of ancillary services (POS; C-level future).

---

## 2. Actors

| Role | Responsibilities |
|---|---|
| Owner-operator / GM | Sets strategy and limits, approves or auto-applies recommendations |
| Revenue manager | Configures rules, reviews forecasts, overrides, analyses performance |
| Reservations / sales | Evaluates group quotes and long-stay offers |
| Portfolio revenue director | Multi-property strategy and benchmarking |
| Systems: PMS/CRS (reservations, inventory, rates), Channel Manager (channel costs and performance), rate-shopping providers, event/holiday calendars, weather feeds (optional) |

---

## 3. Functional Requirements

### 3.1 Data Ingestion and Model Inputs

| ID | Requirement | Priority |
|---|---|---|
| FR-RMS-001 | The system shall ingest at least 2 years of historical reservations (dates, unit type, rate plan, channel, segment, price, lead time, cancellations, no-shows) and current on-the-books from the PMS/CRS, initially by bulk import and thereafter by events. | M |
| FR-RMS-002 | The system shall ingest inventory changes (OOO, seasonal closures) so capacity is correct per date. | M |
| FR-RMS-003 | The system shall support property-maintained event calendars (local events, holidays, school breaks, city-wide conventions) with expected impact level, and import public holiday calendars. | M |
| FR-RMS-004 | The system shall ingest competitor rates from a rate-shopping provider for a configurable competitor set and unit-type equivalence. | S |
| FR-RMS-005 | The system shall ingest channel cost data (commission, ad spend) from the Channel Manager to compute net revenue. | S |
| FR-RMS-006 | The system shall validate data quality (gaps, duplicates, impossible prices) and show a data-health score. | M |
| FR-RMS-007 | The system shall support properties with little history (new properties) by using seasonality templates by property type and region, and by weighting recent pace more heavily. | S |

### 3.2 Demand Calendar and Forecasting

| ID | Requirement | Priority |
|---|---|---|
| FR-RMS-010 | The system shall produce a daily demand forecast per unit type for a rolling horizon (default 365 days): expected occupancy, expected remaining pickup, expected ADR, with confidence ranges. | M |
| FR-RMS-011 | The forecast shall use explainable components: same-period-last-year baseline, day-of-week pattern, seasonality, booking pace vs. historical pace curves, event uplift, cancellation expectation. Each component's contribution shall be viewable. | M |
| FR-RMS-012 | The system shall show a demand calendar colour-coded by demand level with drill-down to the drivers for a date. | M |
| FR-RMS-013 | The system shall re-forecast at least daily and on significant pickup changes. | M |
| FR-RMS-014 | The system shall support forecasting at bed level (hostels), per pitch category (campsites), per time-slot (day-use) and per unit for whole-unit rentals (probability of being booked). | M |
| FR-RMS-015 | The system shall support forecast overrides by the user with notes and expiry, and track forecast accuracy by horizon. | S |
| FR-RMS-016 | The system shall identify unconstrained demand using denials/regrets and closed-out dates when data is available. | C |

### 3.3 Pricing Recommendations

| ID | Requirement | Priority |
|---|---|---|
| FR-RMS-020 | The system shall recommend a price per date, unit type and base rate plan using configurable strategies: demand-level price ladders, occupancy-threshold rules, pace-vs-target adjustments, competitor positioning (e.g., 5% below median), and minimum/maximum guard rails. | M |
| FR-RMS-021 | The system shall show for each recommendation the current price, recommended price, change, and the reasons in plain language. | M |
| FR-RMS-022 | The system shall support three operating modes per property: **manual** (recommend only), **approve** (batch approval daily), **auto-pilot** (apply within guard rails, notify of changes). | M |
| FR-RMS-023 | The system shall write approved prices to the PMS/CRS base rate plan; derived rates update automatically there. | M |
| FR-RMS-024 | The system shall support unit-type price differentials (premium over base type) maintained as fixed or percentage, with optional compression rules (reduce gap when base type sells out). | S |
| FR-RMS-025 | The system shall support length-of-stay pricing recommendations and weekly/monthly rate suggestions for aparthotels and rentals. | S |
| FR-RMS-026 | The system shall support last-minute and far-out pricing behaviours by lead-time band. | S |
| FR-RMS-027 | The system shall support price change frequency limits and minimum change amounts to avoid "price noise" visible to guests. | M |
| FR-RMS-028 | The system shall support channel-aware recommendations (net-of-commission targets) and recommend channel closures when net value is below a floor. | S |
| FR-RMS-029 | The system shall allow bulk acceptance/rejection of recommendations with filters (date range, unit type, change size). | M |
| FR-RMS-030 | The system shall record every applied price with its source (user, rule, auto-pilot) and reason, for later analysis. | M |

### 3.4 Restriction Recommendations

| ID | Requirement | Priority |
|---|---|---|
| FR-RMS-040 | The system shall recommend minimum-stay and closed-to-arrival restrictions for high-demand dates to protect multi-night stays, with expected revenue impact. | S |
| FR-RMS-041 | The system shall recommend removing restrictions when pace falls behind. | S |
| FR-RMS-042 | The system shall recommend overbooking levels per date from historical cancellation and no-show rates, within owner-set limits. | C |

### 3.5 Competitor Intelligence

| ID | Requirement | Priority |
|---|---|---|
| FR-RMS-050 | The system shall display own vs. competitor prices per date and unit-type equivalent, with rank and gap, and highlight competitor sell-outs. | S |
| FR-RMS-051 | The system shall alert on competitor moves beyond a threshold. | S |
| FR-RMS-052 | The system shall support multiple competitor sets (weekday/business, weekend/leisure). | C |

### 3.6 Group, Long-Stay and Quote Evaluation

| ID | Requirement | Priority |
|---|---|---|
| FR-RMS-060 | The system shall evaluate a group or long-stay request: displaced transient revenue, recommended minimum rate, and acceptance recommendation, using forecast and ancillary spend assumptions. | S |
| FR-RMS-061 | The system shall support what-if scenarios (change price, add restriction, close a channel) showing projected occupancy and revenue. | S |

### 3.7 Strategy, Budget and Targets

| ID | Requirement | Priority |
|---|---|---|
| FR-RMS-070 | The system shall allow entry of monthly budgets/targets for occupancy, ADR and revenue per unit type or segment, and track variance to forecast and actuals. | M |
| FR-RMS-071 | The system shall support strategy presets per property type (hostel: occupancy-first; boutique: rate-first; rental: minimise gaps) that set default rules. | S |
| FR-RMS-072 | The system shall support seasonal strategy calendars (e.g., shoulder season discounting). | S |

### 3.8 Reporting and Alerts

| ID | Requirement | Priority |
|---|---|---|
| FR-RMS-080 | The system shall report occupancy, ADR, RevPAR (per unit, bed, pitch or slot), pickup, pace vs. last year, lead time, cancellation rate, by channel, segment, unit type and period. | M |
| FR-RMS-081 | The system shall provide a daily digest (email/in-app) with key changes, dates needing attention and pending recommendations. | M |
| FR-RMS-082 | The system shall report the measured impact of applied recommendations (revenue vs. counterfactual baseline, clearly labelled as an estimate). | S |
| FR-RMS-083 | The system shall provide portfolio benchmarking for multi-property organisations. | S |
| FR-RMS-084 | The system shall export reports and data to CSV/Excel and BI tools. | M |

### 3.9 Administration

| ID | Requirement | Priority |
|---|---|---|
| FR-RMS-090 | The system shall support roles with permission to view, approve or configure, and portfolio scope. | M |
| FR-RMS-091 | The system shall log all configuration changes, approvals and auto-pilot actions. | M |
| FR-RMS-092 | The system shall integrate with third-party PMSs via adapters for standalone sale. | S |

---

## 4. Key Business Rules

| ID | Rule |
|---|---|
| BR-RMS-01 | No recommendation is applied outside the owner-set minimum and maximum price per unit type and season, in any mode. |
| BR-RMS-02 | Auto-pilot changes are reversible: the previous price and the reason for the change are kept and can be restored in one action. |
| BR-RMS-03 | Forecast components are additive or multiplicative in a documented, inspectable way; no black-box component is used for the price itself. |
| BR-RMS-04 | Dates with user overrides are respected until the override expires. |
| BR-RMS-05 | Recommendations respect existing confirmed group blocks and contracted allotments. |

---

## 5. AI Assistance (API-based, no model training)

The numbers come from the statistical engine; a hosted language model is used only to **explain, summarise and converse**.

| Area | Assistance |
|---|---|
| Explanations | Turn a recommendation's components into a short plain-language rationale ("Pace is 18% ahead of last year and a city event is on Friday; recommend +12%") |
| Daily digest | Narrative summary of what changed and what needs a decision, in the owner's language |
| Q&A | "Why is next Saturday priced higher than Friday?" answered from the forecast components and rules |
| Event discovery | Suggest candidate local events from public web sources for the user to confirm into the calendar (never auto-applied) |
| Group quotes | Draft the quote email with the recommended rate and conditions |
| Guard rails | Never let the model propose a price; it may only describe or question the engine's output |

---

## 6. Open Questions

| # | Question |
|---|---|
| Q1 | Which rate-shopping provider(s) for competitor data, and is competitor data in the first release? |
| Q2 | Minimum history to switch from template seasonality to property-specific curves? |
| Q3 | Is group displacement analysis needed for the initial target segment? |
