# Housekeeping & Maintenance Operations — Functional Requirements

> **Document type:** Functional Requirements Specification
> **Scope:** Mobile-first operations application for cleaning, inspection, linen/supplies, lost & found, maintenance work orders, preventive maintenance, vendor and turnover scheduling for on-site and dispersed properties
> **Positioning:** **Separate mobile app on the shared platform** (Operations pack add-on). The PMS Core keeps unit status and basic task generation; this app adds scheduling, mobile execution, inspections, maintenance and analytics. Also usable standalone with a third-party PMS via unit-status integration.
> **Priority key:** **M** must · **S** should · **C** could
> **Related:** [Portfolio architecture](hospitality-suite-portfolio-architecture.md) · [PMS §6.9–6.10](property-management-system-functional-requirements.md) · [AI Assistant Layer](ai-assistant-layer-functional-requirements.md)

---

## 1. Purpose

Get every unit ready on time, at the right quality, with the least staff time, and keep assets working. The users are often multilingual, mobile-only, and sometimes external cleaners or contractors who are not property employees.

### In scope
Task generation and scheduling; mobile task execution; inspections and checklists; unit status; linen and supplies; minibar; lost & found; maintenance requests and work orders; preventive maintenance; assets; vendors and dispersed turnovers; staff productivity; owner recharges.

### Out of scope
Payroll and HR scheduling (external); procurement (external); guest-facing requests UI (Guest portal) — requests arrive here as tasks.

---

## 2. Actors

| Role | Responsibilities |
|---|---|
| Housekeeper / room attendant | Executes assigned tasks, reports issues |
| Housekeeping supervisor / executive housekeeper | Plans the day, assigns, inspects, manages supplies |
| Maintenance technician / engineer | Resolves work orders, logs parts and time |
| Chief engineer / facilities manager | Preventive schedules, assets, vendors |
| External cleaner / vendor | Receives jobs for dispersed units, confirms completion with photos |
| Front desk / manager | Sees readiness, raises requests, prioritises |
| Property owner (rentals) | Sees cleaning and maintenance charges |
| Systems: PMS (arrivals/departures/stay-overs, unit status, folios), CRM/guest portal (requests), lock system (vendor access codes), IoT sensors (optional) |

---

## 3. Functional Requirements

### 3.1 Unit Status and Board

| ID | Requirement | Priority |
|---|---|---|
| FR-OPS-001 | The system shall display a live board of all units with front-office status (vacant/occupied/due-out/arrival), housekeeping status (dirty/in-progress/clean/inspected), OOO/OOS, assigned attendant, ETA of arrival, VIP flag and special instructions. | M |
| FR-OPS-002 | The system shall sync unit status bidirectionally with the PMS within seconds. | M |
| FR-OPS-003 | The system shall support bed-level status inside shared rooms and component-unit status for villas with several bedrooms. | M |
| FR-OPS-004 | The system shall support status changes by phone call/IVR or SMS keyword for properties without smartphones (e.g., dial unit number + status code). | C |
| FR-OPS-005 | The system shall show priority order (early arrivals, VIPs, due-ins with no clean unit available) and recommend what to clean next. | S |

### 3.2 Task Generation and Scheduling

| ID | Requirement | Priority |
|---|---|---|
| FR-OPS-010 | The system shall generate tasks automatically from PMS data: departure clean, stay-over service, turndown, linen change by frequency, deep clean by schedule, inspection, pre-arrival check, and guest-requested services. | M |
| FR-OPS-011 | The system shall support task templates per unit type with checklist items, standard minutes and required photos. | M |
| FR-OPS-012 | The system shall support configurable rules per property type: daily service (hotel), service every N days or on request (aparthotel, long stay), checkout-only cleaning (rentals), pitch inspection (campsite). | M |
| FR-OPS-013 | The system shall support assignment by section/floor/building, by attendant skills (e.g., trained for villas), by workload balancing using standard minutes, and manual drag-and-drop. | M |
| FR-OPS-014 | The system shall support team cleaning (two attendants on one task) and split shifts. | S |
| FR-OPS-015 | The system shall support staff availability input (shifts, absences) to size the day's capacity and flag shortfalls. | S |
| FR-OPS-016 | The system shall reprioritise automatically when the PMS changes (early arrival added, room move, extended stay). | M |
| FR-OPS-017 | The system shall support tasks for public areas and recurring non-unit tasks (lobby, pool, bins). | S |

### 3.3 Mobile Execution

| ID | Requirement | Priority |
|---|---|---|
| FR-OPS-020 | The mobile app shall show the attendant's task list in priority order with unit, task type, checklist, special requests, guest preferences (e.g., extra pillows) and allergy/pet notes. | M |
| FR-OPS-021 | The attendant shall start, pause and complete tasks; time is recorded automatically. | M |
| FR-OPS-022 | The attendant shall report issues with photo, category and free text, which creates a maintenance request or supervisor alert. | M |
| FR-OPS-023 | The attendant shall report DND, refused service, sleep-out, extra occupants, or unit found vacant when expected occupied; discrepancies alert the front desk. | M |
| FR-OPS-024 | The app shall support multilingual UI with task instructions translated to the user's language. | M |
| FR-OPS-025 | The app shall work offline for the day's task list and sync when connectivity returns (remote properties, basements). | S |
| FR-OPS-026 | The app shall support minibar/consumables posting to the guest folio via the PMS. | S |
| FR-OPS-027 | The app shall support voice input for notes and issue reports. | C |
| FR-OPS-028 | The app shall support a simple "big button" mode (Start / Done / Problem) for staff uncomfortable with detailed interfaces. | S |
| FR-OPS-029 | The app shall support NFC/QR scan at the unit door to open the task and prove presence. | C |

### 3.4 Inspection and Quality

| ID | Requirement | Priority |
|---|---|---|
| FR-OPS-030 | The system shall support inspection checklists per unit type with pass/fail per item, photos, scoring and a required re-clean on failure. | M |
| FR-OPS-031 | The system shall support random or rule-based inspection sampling (e.g., 100% of VIP, 20% of stay-overs). | S |
| FR-OPS-032 | The system shall link guest complaints and review themes (from CRM) to inspection results per unit and attendant. | S |
| FR-OPS-033 | The system shall support guest-ready verification before the PMS allows check-in, per property setting (clean vs. inspected). | M |

### 3.5 Linen, Supplies and Lost & Found

| ID | Requirement | Priority |
|---|---|---|
| FR-OPS-040 | The system shall track par levels and counts of linen and amenities per store/floor/cart, with restock requests. | C |
| FR-OPS-041 | The system shall track linen sent to and returned from laundry (internal or external) with discrepancy reporting. | C |
| FR-OPS-042 | The system shall maintain a lost & found register with photo, location, finder, date, storage location, guest match, return shipping and disposal after retention. | S |

### 3.6 Maintenance Requests and Work Orders

| ID | Requirement | Priority |
|---|---|---|
| FR-OPS-050 | Any staff user, and guests via the portal, shall be able to raise a request with unit/location, category, priority, description and photos. | M |
| FR-OPS-051 | The system shall manage work orders with statuses (open, assigned, in progress, waiting parts, on hold, completed, verified), SLA targets by priority, and escalation when breached. | M |
| FR-OPS-052 | The system shall allow placing a unit OOO or OOS for a date range from the work order, synchronising with the PMS and alerting on affected reservations. | M |
| FR-OPS-053 | The technician's mobile view shall show assigned work orders with navigation, checklists, parts, time logging and completion photos. | M |
| FR-OPS-054 | The system shall support recurring issues detection (same category in same unit within N days). | S |
| FR-OPS-055 | The system shall support guest-impacting flags so front desk can communicate proactively. | S |
| FR-OPS-056 | The system shall support cost capture: labour time, parts, vendor invoices, and allocation to a unit, owner or guest (damage recharge via PMS folio). | S |

### 3.7 Preventive Maintenance and Assets

| ID | Requirement | Priority |
|---|---|---|
| FR-OPS-060 | The system shall maintain an asset register (HVAC, boilers, lifts, appliances, pool equipment, vehicles) with location, serial, supplier, warranty, manuals and compliance certificates. | S |
| FR-OPS-061 | The system shall schedule preventive tasks by interval, meter reading or season, generating work orders in advance. | S |
| FR-OPS-062 | The system shall track statutory inspections (fire, lifts, gas, legionella, electrical) with due dates and evidence. | S |
| FR-OPS-063 | The system shall accept IoT alerts (temperature, humidity, leak, door ajar, energy) to create work orders automatically. | C |

### 3.8 Vendors and Dispersed Turnovers (Rentals, Villas)

| ID | Requirement | Priority |
|---|---|---|
| FR-OPS-070 | The system shall schedule turnovers for geographically dispersed units from PMS check-outs/check-ins with time windows, assign to internal staff or external vendors, and optimise routes by distance and deadline. | S |
| FR-OPS-071 | External vendors shall receive jobs via a lightweight web/app link with the unit guide, checklist, photos required, and confirm completion; the system shall record payable fees per job. | S |
| FR-OPS-072 | The system shall issue temporary access codes to vendors through the lock integration for the job window. | S |
| FR-OPS-073 | The system shall support owner-facing cost statements for cleaning and maintenance per unit, feeding the PMS owner module. | S |
| FR-OPS-074 | The system shall support pre-arrival inspections for units unused for a long period (dust, water, pests). | S |

### 3.9 Reporting

| ID | Requirement | Priority |
|---|---|---|
| FR-OPS-080 | The system shall report productivity (tasks per attendant, minutes vs. standard, rooms per shift), readiness time vs. arrival time, inspection pass rate, DND/refused rates. | M |
| FR-OPS-081 | The system shall report maintenance volume by category, unit, SLA compliance, cost, repeat issues and asset downtime. | M |
| FR-OPS-082 | The system shall produce end-of-day housekeeping discrepancy and status reports for the PMS night audit pack. | M |
| FR-OPS-083 | The system shall export data to CSV/Excel and BI. | S |

### 3.10 Administration

| ID | Requirement | Priority |
|---|---|---|
| FR-OPS-090 | The system shall support roles (attendant, supervisor, technician, engineer, vendor, manager) and property scope, including vendor accounts with access only to their jobs. | M |
| FR-OPS-091 | The system shall support simple login for attendants (PIN or QR badge) in addition to standard accounts. | M |
| FR-OPS-092 | The system shall integrate with third-party PMSs for unit status and arrival/departure data. | S |
| FR-OPS-093 | The system shall log all status changes and task events with user, device and time. | M |

---

## 4. Key Business Rules

| ID | Rule |
|---|---|
| BR-OPS-01 | Only an inspected (or clean, per property setting) and vacant unit can be marked guest-ready; the PMS enforces check-in on this. |
| BR-OPS-02 | Completing a task with a failed mandatory checklist item is not allowed; the task stays open with the failure reason. |
| BR-OPS-03 | A unit placed OOO removes itself from availability in the PMS for the period; OOS does not. |
| BR-OPS-04 | Work orders with guest-impact and priority "urgent" escalate to the duty manager after the SLA time. |
| BR-OPS-05 | Vendor access codes expire at the end of the job window plus a configurable grace period. |

---

## 5. AI Assistance (API-based, no model training)

| Area | Assistance |
|---|---|
| Issue intake | Convert a photo plus a few spoken words into a categorised, prioritised maintenance request in the property's language |
| Translation | Translate task notes, guest preferences and supervisor instructions into each worker's language |
| Triage | Suggest likely cause and parts from the property's past work orders for the same category/unit |
| Scheduling help | Explain the day's plan ("why is Room 12 first?") and propose re-balancing when staff call in sick |
| Quality | Summarise inspection failures and review themes per unit into a weekly "fix list" |
| Manuals | Answer technician questions from uploaded equipment manuals (document retrieval) |

---

## 6. Open Questions

| # | Question |
|---|---|
| Q1 | Is offline mode required in the first release (depends on lodge/campsite share of target customers)? |
| Q2 | Are linen and supplies inventory needed by the initial segment, or deferred? |
| Q3 | Which lock vendors must support vendor time-boxed codes at launch? |
