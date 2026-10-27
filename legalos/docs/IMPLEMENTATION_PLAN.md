# LegalOS — Implementation Plan

Written 22 Oct 2026. Review: **Wed 28 Oct 2026**. Product work continues after.

> Principle: every task must serve **both** the review and the product. Review-only work stays cheap. Product-only work is deferred.
> Principle: nothing in the UI or docs claims something the code doesn't do. Failures are shown as failures.

---

## 0. Starting point (audited 22 Oct)

| Finding | Consequence |
|---|---|
| The configured Gemini key is **invalid (401)** — it was also the one committed in `.env.example` | Every LLM call in the running app fails today; silent fallbacks hide it (risk 0, canned replies) |
| No real auth; role comes from a header; no organisation scoping | Cannot be used by more than one company |
| Five workspaces are silos (no shared company/entity) | The "OS" story isn't true yet |
| Contract analysis = clause-by-clause in batches of 8, 4 risk types, LLM does the scoring | Loses cross-clause context, thin Indian-law coverage, non-deterministic scores |
| Scanned PDFs fail (no OCR); page numbers are lost; no citations | Common Indian SME documents don't work |
| Compliance rules hard-coded, unversioned, generated for the whole FY, tied to a user; re-init deletes all tasks | Wrong for new/odd entities; destroys user data |
| Vendor "trust score" is an unvalidated heuristic; mock is the default | Not credible as-is |
| Notice failure → "other / medium" + canned reply; no deadlines/amounts extracted | Dangerous for real notices |
| Knowledge risk radar reads first 6,000 chars only | Wrong for long policies |
| AppShell shows hard-coded fake telemetry | Credibility risk at review |
| Docs describe features that don't exist | Misleading |
| PyMuPDF is AGPL | Blocker for a hosted product |
| Migrations are manual; logging is `print()`; 17 thin tests | Not shippable |

---

## 1. Target product

**Primary user:** a typical Indian SME (10–200 staff, Pvt Ltd / LLP / partnership / proprietorship) — owner or finance/admin person, no in-house lawyer.
**Secondary user:** their CA / accountant (multi-company mode comes after the review).

**One idea that ties it together — the Organisation.** Every record (contract, vendor, notice, task, document, chat) belongs to an **Organisation** with a real profile: legal name, entity type, GSTIN, state, industry, size, MSME (Udyam) category, registrations (GST / PF / ESI / PT / Shops & Establishment). The profile drives **what applies** to them.

**Cross-links that make it an OS (not five tools):**
- Contract party → Vendor record (by GSTIN / name) → shows the vendor's checks and MSME status next to the contract.
- Contract dates (term end, renewal notice window, payment due) → Compliance/Tasks calendar.
- Notice → matched contract/vendor → deadline becomes a task automatically.
- Everything uploaded → Documents (searchable, cited Q&A).
- Home page = one "needs attention" feed across all five, computed from real data.

---

## 2. Architecture changes

### A. Gemini layer (`core/llm`) — "make free Gemini better"
1. **Model config via env** (no hard-coded model); a fallback chain (e.g. flash → flash-lite) on quota errors. Pin model IDs after listing what a valid key can access.
2. **Structured output**: Pydantic schemas passed as `response_schema`; low temperature; schema-validated results; one automatic repair retry.
3. **Typed errors** (`LLMUnavailable`, `LLMQuota`, `LLMInvalidOutput`) — never swallow them into "safe" defaults. Pipelines mark jobs `failed` / `needs_retry`.
4. **Retry with exponential backoff + jitter, concurrency limit, per-minute throttle** so free-tier rate limits don't break uploads.
5. **Content-hash cache** (same doc + prompt version + model → reuse) and **usage log** (calls, tokens, latency).
6. **Long context**: contracts are well inside the context window → analyse the **whole document in one call** (plus clause-level detail), instead of isolated 8-clause batches.
7. **Native PDF/vision input** for scanned documents (OCR via Gemini) — scanned contracts are common in India.
8. **Quote-and-verify**: every finding must carry a verbatim `quote` + `page`; we check the quote exists in the parsed text (fuzzy). Unverifiable findings are dropped or flagged "unverified". This is the main anti-hallucination control.
9. **Deterministic where possible**: LLM reads and extracts; a **rule engine** applies Indian-law checks and computes the risk score, with an explainable breakdown.
10. **Prompt versioning**; changes gated by the eval set (§5).
11. A **fake provider** for tests/offline dev, so everything is testable without a key.

### B. Organisation + auth
- `core.organizations` (promote the Knowledge Hub's `registered_companies`); `organization_id` on contracts, vendor checks, notices, compliance tasks/analyses, knowledge docs; membership table (user ↔ org ↔ role).
- Email + password login (JWT), sign-up → onboarding wizard (enter GSTIN → profile pre-filled → confirm). The `X-User-Role` header stays only as a clearly labelled **demo mode**.
- Every query scoped by `organization_id` from the token, never from the client.

### C. Jobs & state
- Replace "BackgroundTasks + silent except" with a small job model: `queued → running → succeeded | failed(reason) | needs_review`, stored, retryable, visible in the UI (progress + "Retry").
- Idempotent re-analysis (re-run with a new prompt version without duplicating rows).

### D. Retrieval (where retrieval is needed — cross-document Knowledge only)
- Page-aware, heading-aware chunking (track page per chunk).
- Hybrid: Postgres full-text (BM25-style) + vectors, merged with RRF; optional cross-encoder rerank behind a flag; decided by eval, not assumption.
- Compare MiniLM vs a multilingual / Gemini embedding on the eval set before switching.

### E. Parsing
- Replace PyMuPDF (AGPL) with permissively licensed parser; keep page markers; OCR fallback through Gemini; DOCX tables; basic Hindi/English mixed handling.

### F. Platform hygiene
- Migrations run on container start; structured logging; config validation at boot (fail loudly on a bad key); health endpoint that reports real dependency status (DB, Qdrant, Gemini key valid, Sandbox mode) — this feeds the UI status instead of fake badges.
- Real **audit log** table (who did what, when) — the UI claim becomes true.
- File validation (type sniffing, size), per-org storage paths.

---

## 3. Workspaces — target behaviour

### 3.1 Contracts
**User gets:** upload any contract (PDF / DOCX / scanned) → in under ~60 s: plain-English summary, **key facts** (parties, dates, term, value, payment terms, notice periods, governing law, jurisdiction/arbitration seat, renewal), **findings** each with severity, why-it-matters, **quote + page** (click to jump), and a **suggested counter-wording**. Ask-the-contract chat with cited answers. Compare-to-standard checklist for the contract type.

**Contract types supported first:** supply/purchase, service/consulting, distributor/dealer, lease/rent, employment/offer, NDA, loan/guarantee.

**Finding taxonomy (~15):** unlimited/one-sided liability & indemnity, termination imbalance, lock-in/exclusivity, non-compete (Contract Act s.27), penalties/liquidated damages (s.74), payment terms & late-payment, auto-renewal, unilateral amendment, IP ownership, confidentiality scope, jurisdiction/arbitration/seat, force majeure, assignment/subcontract, data protection (DPDP), stamp duty/execution formalities.

**India rule engine (each rule: source link + effective date + "verify" flag until reviewed):** e.g. MSMED Act s.15–16 (payment to micro/small suppliers ≤ 45 days, interest), Income-tax s.43B(h) impact, NI Act s.138 notice mechanics for cheque security, Contract Act s.27/s.73–74, Arbitration Act seat/appointment, state stamp duty prompt.

**Score:** deterministic, from verified findings × severity × (contract value / exposure if known); breakdown shown. Never an LLM-computed number.

### 3.2 Vendors
**User gets:** enter / pick GSTIN → instant **offline validation** (format, checksum, state code, PAN structure/entity type) + **live registry status** when a provider key is configured (clearly labelled "not connected" otherwise — no fake data). Upload vendor documents (GST cert, PAN, Udyam, cancelled cheque) → extraction + **cross-check** (name/PAN/GSTIN/bank consistency, expiry). MSME status (Udyam format validation) feeds the contract payment-term check. Risk shown as a **checklist with reasons**, not a mystery number. Linked contracts listed.

### 3.3 Compliance
**User gets:** after onboarding, a **forward-looking** calendar for *their* entity: GST (monthly/QRMP by turnover), TDS, PF/ESI (thresholds), PT by state, Shops & Establishment, Advance tax, ITR, MCA/LLP forms, DPDP readiness. Each item: what, who, form, due date, penalty, **source + effective date**, evidence upload, status, reminders. Past dates are not created as overdue — onboarding asks "already filed?".
**Rules live in versioned data files** (not in code), with applicability conditions (entity, turnover, headcount, state). Ability to add custom tasks without losing them on re-init.
**Document intake:** upload a notice/certificate → action items → tasks (deduplicated).
**Honest scope:** this is a reminder & organisation tool, not a filing tool; CA review recommended.

### 3.4 Legal Notices
**User gets:** upload/paste a notice → **structured extraction** (sender, advocate, date, type, statute cited, amounts claimed, demands, **deadline computed**) → urgency from rules (e.g. NI s.138 15-day window, GST show-cause response windows) + LLM → **checklist of documents to gather** → **reply draft** with clearly marked `[facts to confirm]` placeholders (never invented facts) → "Needs lawyer review" gate → deadline auto-added to the calendar → matched to related contract/vendor.

### 3.5 Documents (Knowledge Hub)
**User gets:** one vault for company papers; each doc auto-classified with a **full-document** risk/gap review (not 6k chars); ask-anything Q&A with **page-level citations** and "not in your documents" honesty; filters by type; statute reference snippets (curated public Acts) so answers can cite law, clearly separated from the company's own documents.

### 3.6 Home ("Today")
Real data only: overdue/due-soon tasks, notices awaiting reply with days left, contracts needing review / renewal windows, vendor alerts, document gaps. Health summary computed from the above, with the formula visible.

---

## 4. UX / UI

**Direction:** calm, trustworthy, **light-first** professional UI (dark theme available), plain language, big clear primary actions. Replace the neon/glass look. Built for non-lawyers and for phones.

**Principles**
1. **One primary action per screen**; progressive disclosure for detail.
2. **Plain English first, legal term second** ("You can be fined without a cap" → "Indemnity: unlimited liability").
3. **Always show what happened**: progress for long jobs, specific error + Retry, never a blank/zero fallback.
4. **Evidence everywhere**: click a finding → source text highlighted in a document viewer.
5. **Indian conventions**: ₹ with lakh/crore grouping, DD MMM YYYY, IST, GSTIN/PAN formatting & masking.
6. **Safe by default**: "AI-generated — review before relying" labels, lawyer-review gate on notices/replies, confirmations on destructive actions.

**Structure (IA):** Home · Contracts · Vendors · Notices · Compliance · Documents · Settings (Organisation, Team, Integrations, Data & privacy). Global search (⌘/Ctrl-K). Org switcher (for CAs later). Notifications bell.

**Accessibility (WCAG 2.1 AA):** contrast ≥ 4.5:1, full keyboard navigation, visible focus, ARIA labels/live regions for async status, reduced-motion respect, 44px touch targets, no colour-only meaning (icon + text on risk badges), screen-reader-friendly tables. **Responsive:** mobile-first; bottom nav on phones.

**Tech:** keep React + TS + Tailwind; add TanStack Query (data/polling/cache), Radix primitives (accessible dialogs/menus/tabs/tooltips), a toast lib, date/number formatting helpers, a PDF viewer with highlight (for citations), charts only where they add meaning. Design tokens in one file; light/dark tokens; component library in `design-system/` with a small `/styleguide` route for review.

**Core flows to nail:** sign-up → onboarding; upload → analysing (progress) → results → ask; GSTIN → vendor result → link to contract; notice → deadline → reply draft → mark sent; calendar → mark filed + attach evidence.

---

## 5. Quality & evaluation (what we show at the review)

- **Synthetic Indian-SME document set** (written by us, planted issues, ground truth labels): ~25 contracts across the 7 types incl. 3 scanned, ~10 notices, ~10 vendor doc sets, ~10 policies.
- **Metrics:** finding recall/precision per category; extraction field accuracy; quote-verification rate; retrieval hit@k; notice deadline accuracy; latency; Gemini calls/doc; failure-handling tests.
- **Test pyramid:** unit (rules, validators, scoring) · service tests with fake LLM · API tests · a few browser e2e flows · eval runs (needs a valid key) gated before prompt changes.
- **Definition of done per feature:** works end-to-end on the demo org · has empty/loading/error states · covered by tests · documented in README · no fake data.

---

## 6. Timeline

Today is **Thu 22 Oct**; review **Wed 28 Oct**.

### Tonight (autonomous, no valid Gemini key available)
Everything below is built and tested against the **fake LLM provider**; real-model tuning happens once a valid key is in place.
1. Branch + baseline tests in the container; this plan committed to the docs folder.
2. **Gemini layer (A):** config, typed errors, retries, structured-output helper, cache, fake provider, tests. Health check that reports "LLM key invalid" loudly.
3. **Failure semantics (C):** no more silent score-0 / canned replies in contracts, notices, knowledge; explicit failed state in API.
4. **Organisation model + migration (B)**, with a DB backup first.
5. **Contract engine v2 (3.1):** parsing with page tracking, schemas, rule engine, deterministic scoring, quote verification — with unit tests; synthetic contract set + labels for the eval.
6. Start the **design system** (tokens, shell, base components, styleguide route).
Anything not reached is carried to Friday; I'll report exactly what was and wasn't done.

### Fri 23 Oct — *needs valid Gemini key*
Wire contract engine to real Gemini; run eval, tune prompts and schemas; auth + onboarding; Contracts UI (upload → progress → findings → source viewer → chat).

### Sat 24 Oct
Compliance engine (versioned rules + applicability + onboarding "already filed?") and UI; Vendor v2 (validators, docs cross-check, MSME link) and UI.

### Sun 25 Oct
Notices v2 (extraction, deadlines, reply with placeholders, review gate) and UI; Documents v2 (full-doc review, page-cited Q&A); Home feed; cross-links.

### Mon 26 Oct
UX polish pass (accessibility audit, mobile, empty/error states), seeded demo org, e2e runs, final eval numbers, docs/README rewrite.

### Tue 27 Oct
Feature freeze at noon. Rehearsal, backup screen recording, slides (architecture, evaluation, India-specific rules, roadmap), known-issues list.

### Wed 28 Oct — Review.

**Cut line if time slips** (drop from the bottom): Home feed polish → statute snippets → Documents v2 depth → vendor doc cross-check → notice↔contract matching. Never cut: honest failure states, Contracts v2, onboarding, eval numbers.

### After the review (product track, ~8 weeks)
| Weeks | Focus |
|---|---|
| 1 | Harden auth (password reset, sessions, RBAC), audit log UI, rate limits, CI, error monitoring |
| 2 | Hosting (containerised deploy, backups, secrets), paid-tier / data-privacy decision for LLM, DPDP consent + retention |
| 3 | Notifications (email, then WhatsApp), calendar sync, reminders engine |
| 4 | Statute library (curated Acts with sources) + retrieval upgrade by eval (hybrid/rerank/embeddings) |
| 5 | CA multi-client mode, bulk onboarding, reports/exports |
| 6 | Live registry integrations, vendor monitoring |
| 7 | Hindi UI + document handling, usability tests with real SMEs/CAs |
| 8 | Pilot with 5–10 SMEs/CAs, pricing experiments, metrics |

---

## 7. Needs from Himanshu

1. **A valid Gemini API key** (from aistudio.google.com — keys normally start with `AIza`). The current one returns 401. Put it in `legalos/.env` as `GEMINI_API_KEY=...` (this file is git-ignored) and `docker compose up -d backend`. Revoke the old one.
2. *(Optional)* Sandbox.co.in credentials for live GSTIN data; without them the vendor workspace shows "not connected" for live registry checks instead of fake data.
3. Real (or realistic) sample documents you're allowed to use — optional; synthetic ones are being produced.
4. Any decision you want changed in §1–§4 (defaults chosen: light-first UI, English first, email+password auth, SME owner as primary user).

## 8. Risks

- **Free-tier limits & privacy** — rate limits shape the job queue; free-tier prompts may be used by Google to improve products (verify current terms) → synthetic/public documents only until a paid tier decision.
- **Legal accuracy** — outputs are decision support; Indian-law rules must be verified against primary sources before they are presented as fact; each carries a source and "verified by" marker.
- **Unauthorised practice of law** — position as information + review workflow; lawyer-review gate; clear disclaimers.
- **Scope** — mitigated by the cut line above.
