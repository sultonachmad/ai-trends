# AI Assistant Layer — Functional Requirements

> **Document type:** Functional Requirements Specification
> **Scope:** A cross-cutting capability that adds language, vision and document understanding to every app in the suite (PMS, Booking Engine, Channel Manager, CRM, RMS, Operations, POS, Payments) using **hosted foundation-model APIs**. No custom model training; no in-house ML pipelines.
> **Positioning:** Add-on, metered, with a monthly budget per property. Delivered as a platform service (AI Gateway) plus UI affordances inside each app.
> **Priority key:** **M** must · **S** should · **C** could
> **Related:** [Portfolio architecture §7](hospitality-suite-portfolio-architecture.md) · all system FRs (each has its own "AI Assistance" section)

---

## 1. Purpose and Constraints

Improve service speed and quality for properties that cannot hire more staff, at a cost a small owner can predict. The layer **assists** existing workflows; it does not replace the systems of record and never acts on money, inventory or guest commitments without a human, except in narrowly allow-listed cases the owner enables.

Constraints:

- Use third-party hosted models via API (text, vision, speech-to-text, translation, document OCR). Prefer provider-managed features (retrieval, caching, batch) over building infrastructure.
- No training or fine-tuning of models. Improvement happens through better retrieval, prompts, templates and feedback-driven rules.
- Vendor-neutral: the gateway abstracts the provider so models can be swapped as prices and quality change.

---

## 2. Actors

| Role | Interaction |
|---|---|
| Any staff user | Receives suggestions, drafts, summaries, answers; approves or edits |
| Guest | Receives AI-assisted (human-approved or allow-listed) replies; may use a guest-facing assistant in the portal |
| Owner / admin | Sets budget, enables/disables features, defines allow-lists and tone |
| Systems: AI Gateway, platform data APIs, document store, CRM inbox, Operations app, RMS, reporting |

---

## 3. Functional Requirements

### 3.1 AI Gateway (platform service)

| ID | Requirement | Priority |
|---|---|---|
| FR-AI-001 | The gateway shall provide a single internal API for: text generation, classification, extraction to schema, summarisation, translation, speech-to-text, image/document understanding, and embedding-based retrieval, routed to configured external providers. | M |
| FR-AI-002 | The gateway shall support at least two providers with per-task model selection (small/cheap for classification and routing; larger for drafting and reasoning) configurable without code changes. | M |
| FR-AI-003 | The gateway shall enforce a **monthly budget per property** (and optional per feature), warn at 80%, and degrade gracefully at 100% (suggestions off, transactional functions unaffected). | M |
| FR-AI-004 | The gateway shall cache responses for identical grounded requests (e.g., FAQ answers, translations) with configurable TTL. | M |
| FR-AI-005 | The gateway shall support batch/off-peak processing for non-urgent jobs (nightly summaries, review theme analysis) at lower cost. | S |
| FR-AI-006 | The gateway shall log every request: feature, user, inputs reference (not raw PII where avoidable), model, tokens, cost, latency, output reference, and user feedback. | M |
| FR-AI-007 | The gateway shall redact or minimise personal data sent to providers according to a per-feature data policy, and support providers/regions that meet the tenant's data-residency requirement. | M |
| FR-AI-008 | The gateway shall apply output checks: profanity/safety filters, prompt-injection mitigation for content coming from guests or the web, and schema validation for structured outputs. | M |
| FR-AI-009 | The gateway shall expose a usage and cost dashboard per property and feature. | M |

### 3.2 Grounding and Knowledge

| ID | Requirement | Priority |
|---|---|---|
| FR-AI-010 | The layer shall maintain a per-property knowledge base built from: property content, policies, rate plan terms, digital guide, house rules, FAQ, unit facts, local information, and uploaded documents (manuals, contracts), indexed for retrieval. | M |
| FR-AI-011 | Every guest-facing answer shall be generated only from retrieved property knowledge and the specific reservation context; when the knowledge base has no answer, the layer shall say so and hand over to a human. | M |
| FR-AI-012 | The layer shall show the sources used for each answer or draft to the staff user. | S |
| FR-AI-013 | Owners shall be able to edit the knowledge base in plain language (e.g., "Pool closes at 20:00 from November") with versioning. | M |
| FR-AI-014 | The layer shall flag knowledge gaps (questions that could not be answered) for the owner to fill. | S |

### 3.3 Feature: Guest Communication (CRM)

| ID | Requirement | Priority |
|---|---|---|
| FR-AI-020 | Classify each inbound message by intent, urgency and sentiment; route and label in the inbox. | M |
| FR-AI-021 | Draft a reply in the guest's language grounded on reservation, policies and knowledge base; staff edits/approves. | M |
| FR-AI-022 | Auto-reply without human approval only for owner-allow-listed intents (e.g., Wi-Fi, check-in time, parking, directions) and only when the retrieved answer has high confidence; otherwise draft for approval. | M |
| FR-AI-023 | Translate conversations both ways with the original preserved. | M |
| FR-AI-024 | Summarise long threads and a guest's history before check-in or a call. | S |
| FR-AI-025 | Draft review responses in the property's tone; never auto-publish unless allow-listed (e.g., 5-star with no text). | M |
| FR-AI-026 | Produce weekly review and survey theme summaries with per-unit recurring issues. | S |
| FR-AI-027 | Draft campaign copy variants from a brief and suggest segments from past campaign results. | C |

### 3.4 Feature: Reservations and Front Desk (PMS, CRS, Booking Engine)

| ID | Requirement | Priority |
|---|---|---|
| FR-AI-030 | Extract booking requests from emails/chat (dates, guests, unit type, special needs) into a pre-filled availability search and draft quote. | M |
| FR-AI-031 | Extract rooming lists from attachments (spreadsheets, PDFs, images) into structured rows for group booking creation, with validation highlights. | S |
| FR-AI-032 | Read ID documents via vision/OCR into profile fields for staff verification (where legally permitted). | S |
| FR-AI-033 | Suggest unit assignment with reasons (preferences, VIP, accessibility, housekeeping readiness, gap minimisation) as a recommendation over the PMS rules. | S |
| FR-AI-034 | Produce a two-line guest brief at check-in (history, preferences, open issues). | S |
| FR-AI-035 | Provide a natural-language search box in the PMS ("arrivals tomorrow with balance due", "guests from Brazil last month") that translates to platform queries and saved reports. | M |
| FR-AI-036 | Booking engine assist: convert a free-text request into a search and explain policies in plain language; never state availability or price except from live platform data. | S |

### 3.5 Feature: Operations (Housekeeping & Maintenance)

| ID | Requirement | Priority |
|---|---|---|
| FR-AI-040 | Voice-to-task: transcribe a spoken note and create a categorised task or maintenance request with photo. | S |
| FR-AI-041 | Translate task instructions and guest preferences into each worker's language. | M |
| FR-AI-042 | Triage maintenance requests: category, priority and likely cause from text/photo and past work orders. | S |
| FR-AI-043 | Answer technician questions from uploaded equipment manuals. | C |
| FR-AI-044 | Weekly "fix list" per unit from inspection failures and review themes. | S |

### 3.6 Feature: Revenue and Distribution (RMS, Channel Manager)

| ID | Requirement | Priority |
|---|---|---|
| FR-AI-050 | Explain each RMS recommendation and forecast in plain language from its components; never generate a price. | M |
| FR-AI-051 | Daily narrative digest of pace, pickup and pending decisions. | S |
| FR-AI-052 | Suggest candidate local events from public sources for owner confirmation. | C |
| FR-AI-053 | Translate channel error payloads into cause and fix; suggest product mappings by similarity for confirmation. | S |
| FR-AI-054 | Generate channel-ready descriptions in required lengths/languages from platform content. | S |

### 3.7 Feature: Finance and Reporting

| ID | Requirement | Priority |
|---|---|---|
| FR-AI-060 | Natural-language questions over reporting data producing tables/charts and saved reports, with the generated query visible to the user. | M |
| FR-AI-061 | Explain variances in trial balance and payment reconciliation; propose matches for confirmation. | S |
| FR-AI-062 | Draft dunning emails and chargeback narratives from records. | S |
| FR-AI-063 | Extract supplier invoices (for owner recharges) into structured lines. | C |

### 3.8 Feature: Help and Onboarding

| ID | Requirement | Priority |
|---|---|---|
| FR-AI-070 | In-app assistant grounded on product documentation and the property's configuration ("why can't I check in Room 5?"), answering with steps and links. | M |
| FR-AI-071 | Onboarding helper that maps imported spreadsheets (units, rates, future bookings) to platform fields for confirmation. | S |
| FR-AI-072 | "Explain this screen" for traditional users switching modes. | S |

### 3.9 Guest-Facing Assistant (portal / web chat)

| ID | Requirement | Priority |
|---|---|---|
| FR-AI-080 | Guests may ask questions in the portal or web chat; answers come only from the knowledge base and their own reservation; booking actions are links into the Booking Engine/portal, not performed by the assistant. | S |
| FR-AI-081 | Clear labelling that the assistant is automated, with a one-tap handover to a human and the expected response time. | M |
| FR-AI-082 | Guest conversations with the assistant are visible in the CRM inbox thread. | M |

### 3.10 Governance, Feedback and Quality

| ID | Requirement | Priority |
|---|---|---|
| FR-AI-090 | Every AI-generated text shown to staff shall be labelled as AI-drafted, with edit and "report problem" actions. | M |
| FR-AI-091 | The layer shall collect edit distance and thumbs-up/down per feature and surface quality metrics per property. | S |
| FR-AI-092 | Owners shall be able to enable/disable each feature, set tone/style guidelines, and define allow-lists for autonomous actions. | M |
| FR-AI-093 | The layer shall provide an evaluation set per feature (sample inputs with expected outputs) run on prompt or model changes before rollout. | S |
| FR-AI-094 | The layer shall retain AI logs per the retention policy and exclude them from guest data exports unless required. | M |
| FR-AI-095 | Autonomous actions (auto-replies, auto-published responses) shall be rate-limited and auditable, with a kill switch per property. | M |

---

## 4. Key Business Rules

| ID | Rule |
|---|---|
| BR-AI-01 | AI never creates, modifies or cancels reservations, changes prices or availability, moves money, or publishes externally without a human action, except within owner-defined allow-lists for low-risk replies. |
| BR-AI-02 | Guest-facing outputs must be grounded; "I don't know, a team member will reply" is the required fallback. |
| BR-AI-03 | Budget exhaustion disables suggestions, never transactional functions. |
| BR-AI-04 | Content originating from guests, the web or channels is treated as untrusted input and cannot change assistant instructions. |
| BR-AI-05 | Features processing identity documents or payment-related text run only through providers and regions approved for that data class. |

---

## 5. Cost Model Guidance (for the business owner)

| Lever | Practice |
|---|---|
| Model tiering | Small model for classification, routing, translation of short texts; large model only for drafting and complex summaries |
| Caching | FAQ answers, policy explanations and translations cached per property and language |
| Batching | Review analysis, weekly summaries and digests run as nightly batch jobs |
| Context control | Send only the retrieved facts needed, not whole histories; cap tokens per request |
| Budgeting | Per-property monthly cap with alerts; usage dashboard by feature; default caps by property size |
| Human-in-loop | Drafting instead of autonomous action avoids costly mistakes, which is the biggest hidden cost |

---

## 6. Open Questions

| # | Question |
|---|---|
| Q1 | Which providers and regions meet the data-residency needs of the launch markets? |
| Q2 | Which features are in the AI v1 bundle (recommended: inbox drafting, FAQ auto-reply, translation, review drafts, natural-language reports, help assistant)? |
| Q3 | Default monthly budget per property size tier? |
