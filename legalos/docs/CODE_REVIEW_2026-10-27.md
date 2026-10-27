# LegalOS code review - 27 Oct 2026 (evening before Review 2)

Method: two independent reviewers read every file of the backend and frontend (no docs, no author notes), plus
objective checks: test suite, type-check, bundle, dependency audit, dead-code scan, and a live accuracy probe on a
contract with 11 planted issues. Every "confirmed" item below was reproduced, not just read.

## The verdict in one paragraph

The architecture is right for the core idea: an SME owner gets facts, evidence-backed findings (each quote verified
against the document), deterministic Indian-law rules with sources, a dated calendar, and honest failure states.
Tenancy is enforced everywhere and tested. The design-system and first-run UX are better than most student projects
and most demos. What drags it down: a handful of real correctness bugs (one crashes a normal path, *confirmed*), a
verification layer that is English-only in a product for Indian SMEs (*confirmed*), unsafe defaults for anything
beyond a laptop, ~25% dead v1 code, and the fact that AI accuracy has never been measured.

## Ratings (1-10, consolidated from both reviewers and my checks)

| Area | Score | Why |
|---|---|---|
| Serves the core idea | 8 | Grounding pipeline (segment -> quote -> verify -> rules -> score) is the product's moat. Keep investing there. |
| Correctness | 6 | Re-analysis crash (A1), merge/dedupe mis-attribution (A2/A3), session wipe on any network error (F1). |
| AI grounding / accuracy design | 7 | Strong design; undermined by Unicode-blind verification, a 12-char quote bar, silent "which party am I" failure, and no measurement. |
| Security / tenancy | 6 | Tenancy solid and tested. Demo mode is the default, uploads are unbounded in memory, paid lookups unthrottled, token in localStorage. |
| UX / product feel | 7 | Copy, empty states, citations, progress feel real. Vendor/Supplier wording, raw LLM errors, onboarding dead end, disabled buttons without reasons betray it. |
| Accessibility | 7 | Tokens, icon+label, focus rings, 44px targets present. No focus-on-route-change, `role="alert"` overused. |
| Maintainability | 6 | v2 code is clean and consistent; dead v1 code, no working lint, job runner copy-pasted 3x, list rows copy-pasted 5x. |
| Tests | 6 | 169 pass; good per-workspace API + tenancy + outage tests. But suite silently skips without a DB, migrations never run in tests, bugs below untested. |

## Measured AI accuracy (one probe, not a benchmark)

Service agreement with 11 planted problems, real Gemini: **10/11 found, all 10 quotes verified, 0 false positives**.
Missed: a Rs 10,000 liability cap on a Rs 18 lakh/yr contract. The AI folded it into "unlimited indemnity", the
facts pass reported `cap_present=true`, and the rule only fires on `cap_present is False`, so a trivial cap passes
as a cap. Also: 3 "missing protection" items are unverifiable by design, one of them ("no governing law") contradicted
the arbitration clause found two lines earlier.

That is encouraging but it is one document. There is still no labelled set and no number per prompt version.

## Confirmed bugs (reproduced)

| # | Where | What | Impact |
|---|---|---|---|
| A1 | `contract_intelligence/service.py` `sync_contract_reminders` | Deletes only *pending* calendar reminders, then inserts a new one with the same unique key. | **"Analyse again" fails with "Something went wrong" once the owner has ticked that contract's reminder.** Reproduced on the demo contract. |
| A4 | `engine/verify.py:25` | Normaliser strips every non-ASCII letter. | A Hindi/Gujarati quote normalises to `"15 - -"` and can never verify: vernacular notices always show "couldn't match", vernacular contract findings are excluded from the score silently. |
| A5 | `verify.py:16-17` | 12-char minimum + fuzzy 88. | `"the supplier"` verifies against any clause containing it. Verification proves existence, not support. |
| F1 | `frontend/lib/auth/session.tsx:97-101` | `catch { clear() }` on session restore. | Opening the app while the backend is still booting (or any blip) deletes the token and logs the user out. Likely during a demo. |

## High-value findings (read, not yet reproduced)

**Backend**
- A2/A3: rule<->AI merge by *category* attaches the wrong rule/severity/legal note to an AI finding, and suppresses "missing protections" whenever any finding exists in the category. Fix: merge only on similar title.
- A6: if the org name doesn't fuzzy-match a party, no one is "our client" and MSME/role rules silently never run. Needs a warning + a "which party are you?" control.
- A7: notice deadline always counts from `received_date`, which defaults to *today* if not supplied: a notice uploaded 10 days late gets a deadline 10 days too late. Add a "from notice date / from receipt" anchor and never default silently.
- A8: dismissing a finding doesn't change the score.
- B1: `demo_mode` defaults to `True` with no production guard: any request without a token becomes the demo owner. Must default to `False` and refuse to start in prod when on.
- B2: `await file.read()` before the size check: memory DoS. Read in chunks.
- B3: live registry lookups (when enabled) are unauthenticated in demo mode, unthrottled, uncached.
- C1: all LLM calls share the default thread pool and block in it with sleeps; a burst of uploads stalls `/health`, chat and Q&A. Dedicated executor or real queue.
- C2: `thinking_budget` is never set, so Gemini "thinks" on pure extraction; RPM=10 means 3 sample loads then waiting. Set budget 0 on facts/OCR/review and pre-warm the cache before the demo.
- C3: whole-PDF OCR in one structured call truncates past ~30 pages. Batch by page.
- `local_provider.py` still returns a fabricated `risk_score: 0` when Ollama is down - the one place that violates "no safe defaults".
- Rule `r_uncapped_liability` fires on NDAs/employment contracts where caps aren't customary: noise.
- Knowledge-hub search is English-only twice (Postgres `'english'` config + MiniLM English embeddings).
- Dead v1 code: 4 prompt files, `rag_pipeline.py`, `chunker.py`, `retrieval_service.py`, `ai_io_schemas.py`, `gstin_mock.py`, `get_current_user`, 3 stub repositories, 7 legacy tables + 3 unused Qdrant collections created at every startup, and 3 test files that exercise dead code (one hits the network). 23 `print()` calls remain in core/.
- Tests: `pytest.skip` of the whole API suite when Postgres is absent (CI can be green with nothing run); migrations never executed in tests; A1-A7 untested.

**Frontend**
- `?new=1` quick actions / Ctrl+K do nothing when you're already on that page (state read once in `useState`), and `replaceState({})` corrupts router history.
- Home "Mark as already filed" can open a "0 items" confirm and submit an empty request before tasks load.
- Any failed query collapses into "You're all caught up" / stat tiles showing `0`: in a compliance product that's the worst failure mode. No ErrorBoundary anywhere: one null field white-screens the app.
- Received-date picker fires a PATCH + toast on every keystroke; supplier quick-check hits the API on every keystroke of the *name*.
- Failed "Ask" loses the question; "Lawyer approved" is self-attestable from draft; notice checklist ticks are lost on reload.
- Vendor vs Supplier vocabulary split across nav/dialogs; raw LLM errors ("RESOURCE_EXHAUSTED", "ask your administrator about the Gemini key") shown to owners.
- Onboarding reused as "Edit profile" is a dead end (no nav, no cancel, "Finish setup" copy).
- `npm run lint` cannot run (no config, no eslint dep); `tsconfig` hides unused locals; dead legacy Tailwind palette and CSS.
- 10 npm advisories, all in `axios` (upgrade to >= 1.19.1).
- Always-mounted palette + bell poll every list from every page while anything processes.
- Duplicated: list row x5, link-button x5, menu item x5, `useInvalidate` x4, 404/back block x4, cmdk heading class x6.

## What is genuinely good (keep)

Two-pass facts->risks with segment markers; verbatim-quote-or-drop; deterministic score and rules with sources
flagged "to verify"; typed LLM errors + retry/fallback + on-disk cache; placeholder-based reply letters; "nothing
relevant -> no LLM call" Q&A; compliance rules as data with correct standard dates; org-scoped everything with tests;
honest `/health`; light/dark tokens, icon+label severity, friendly error mapping, progress steps, first-run panels.

## Plan

### Tonight (demo safety, ~3 hours, in this order)
1. A1 reminder upsert (also un-break the demo contract). F1 session restore only clears on 401/403. ErrorBoundary.
2. A2/A3 merge by similar title; re-check the sample contract's findings by eye.
3. A4 Unicode-aware normaliser + A5 stricter quote bar (>=40 chars or exact match for short quotes).
4. `thinking_budget=0` on extraction passes; pre-run the three samples so the cache serves the demo.
5. `?new=1` via `useSearchParams`; catch-up confirm gated on loaded tasks; error states instead of "all caught up"; friendly `error_kind` copy; Vendor->Supplier rename; `VITE_API_URL` check.
6. Bump axios. Notices: require received date (no silent default).

### Before calling it a product (ordered)
1. `demo_mode=False` default + prod guard; chunked upload limits; per-org rate limits + 24h registry cache; httpOnly session cookie + server logout.
2. Real job queue with dedicated executors; SSE for processing status instead of per-list polling.
3. Language: Unicode verification, multilingual embeddings + `simple` tsvector, "which party are you" step, deadline anchor field, score recompute on dismiss.
4. Delete v1 code/tables/collections; extract `run_job`, `ListRow`, `ButtonLink`, `DetailShell`, shared `useInvalidate`; working ESLint; migration-drift test; CI fails (not skips) without a DB.
5. Evaluation harness: ~20 labelled Indian contracts/notices scored per `PROMPT_VERSION`/`RULES_VERSION`. The versioning exists; the measurement doesn't.
6. Real Settings (profile, password, team invites, export/delete), in-shell profile editing, persisted notice checklist, focus-on-route-change, `role="alert"` only for errors.
