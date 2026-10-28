# LegalOS - Progress and handover

Last updated: 27 Oct 2026 (day before the review). Branch: `overhaul/product-foundation` (nothing is committed yet).
Plan for the review: `docs/REVIEW2_PLAN.md`. Long-term plan: `docs/IMPLEMENTATION_PLAN.md`.

## State: all five workspaces are rebuilt, work with the real Gemini API, and share one organisation

27 Oct evening: Contracts, Notices, Vendors and Compliance got full-height workspace UIs of their own and general-purpose backends:
- **Contracts, "reading room":** contract text centre with flagged clauses highlighted, verdict rail (score, findings with suggested change, key terms, ask). Type-specific checks (lease, NDA, employment, service, franchise...), long contracts cut at a clause boundary with a visible "not reviewed below" line, photo uploads via OCR.
- **Notices, "response desk":** deadline strip (received -> today -> reply-by), 4-step guide (what this is, what the law says, what to do now, your reply). 15 notice types; deadlines are stated+verified, statutory (cited) or unknown, never invented. The `LEGAL_NOTES` in `engine/rules.py` should be skimmed by a lawyer.
- **Vendors, "check desk":** GSTIN/PAN/Udyam validated as you type, verification card (identity, registry, verdict, linked records), check history. Live GST lookup via `GST_API_PROVIDER` / `GST_API_KEY` / `GST_API_BASE_URL` / `GST_API_SECRET` / `GST_API_KEY_HEADER` in `.env`.
- **Compliance, "year planner":** 12-month strip, next-up hero, overdue with late fees so far, editable company profile on the right that regenerates the calendar. New rules: CMP-08, GSTR-4, Karnataka PT (being verified).
179 backend tests pass; tsc and vite build clean; all four screens checked in the browser.

28 Oct overnight (branch `himanshu-version-legalos`): production hardening of every pipeline for general Indian SME use.
- **Documents:** parsers for PDF / scanned PDF (page-wise OCR) / DOCX with tables / XLSX / CSV / images / text; heading-path chunking (`4. > 4.2`), table rows with headers, header/footer removal; exact-token search (SKUs, GSTR-3B, amounts, dates, clause numbers), sub-question reranking, document routing by profile similarity, Hinglish glossary; structured answers (direct line + bullets + "not covered" + "sources disagree"); map-reduce review of long documents; keyword-searchable before vectors exist. Eval `python -m app.workspaces.knowledge_hub.eval.run_eval`: 33 questions, hit@1 96%, hit@8 100% (was 72% / 87% on the same set).
- **Contracts:** 29 contract types with per-type checklists and the usual SME side (`engine/contract_types.py`); client side inferred when the organisation is not a party (fixes reviews from the wrong side); 24 cited Indian-law rules that only fire on located clause text (`engine/rules.py`, `engine/evidence.py`); recall sweep when a review is thin; two-part review for long contracts; calibrated score with full breakdown; multi-photo upload; Hindi segmenter.
- **Notices:** 45 notice types with meaning, consequence chain, documents, who handles it (`engine/catalog.py`); deadline engine taking the earliest of stated / statutory / hearing dates with Indian date formats and Hindi months (`engine/dates.py`); Hindi, Marathi, Gujarati notices with quote verification; per-type reply structure or an action plan where a reply is wrong; deterministic lawyer brief; multi-photo and WhatsApp-paste inputs.
- **Platform:** LLM timeouts, output sizing, JSON repair, persisted daily-quota memory, per-key rate gates, bounded cache; job runner (`shared/jobs.py`); safe uploads (magic bytes, size, content-hash dedupe); identifiers for GSTIN/PAN/TAN/Udyam/CIN/LLPIN/IFSC/IEC/FSSAI/ESIC/PF; registry lookups cached 24 h; compliance dates audited with a lint test; `/health` with latencies and request ids; `scripts/backup.ps1`.
- UI wired to all new fields (deadline basis, hearing dates, action plans, lawyer brief, score breakdown, legal references, new identifier kinds, system health). 604 backend tests pass.
- Known: the image lacks `pypdf` (declared in pyproject); code uses pypdfium2 instead. Rebuild the image to install it.

| Workspace | What it does now | Verified |
|---|---|---|
| **Contracts** | Upload (PDF/DOCX/TXT, scans via AI OCR) -> plain-English summary, key terms, findings with verbatim quote + page, 8 Indian-law checks (MSME 45-day, foreign law, no liability cap, auto-renewal, one-sided termination, stamp duty...), deterministic risk score, ask-the-contract chat, supplier card, contract dates -> calendar reminders | Real Gemini on a yarn-supply agreement: found the Rs 2 lakh shortfall charge, unlimited indemnity, one-sided termination, price changes, 48-hour quality window, 24% interest, Mumbai jurisdiction |
| **Vendors** | Instant GSTIN checks (checksum, PAN, business type vs name, state, Udyam), saved suppliers, risk with reasons, linked to contracts, honest "not checked" when no live registry | Tests; sample registry records are labelled "demo data" |
| **Compliance** | Calendar from the company profile (YAML rules with source + penalty), idempotent sync, catch-up for past filings, custom reminders, "how this is built" | Tests incl. a concurrency race |
| **Notices** | Upload/paste -> type, issuer, amount, **verified deadline**, urgency (rules), law note, reply draft with highlighted blanks, versions, lawyer-review gate, deadline added to the calendar | Real Gemini on a cheque-bounce notice |
| **Documents** | ChatGPT-style chat over the company's papers: collections, conversations with follow-ups, streamed answers with numbered citation chips that open the exact passage (quote highlighted, "found word for word"), confidence from verified quotes. Pipeline: structure-aware chunking (sections, table rows with header, Hindi), multilingual embeddings + **cross-encoder reranker**, Postgres keyword (english + simple) + Qdrant vectors fused by RRF over planner-generated query variants (Hinglish/Hindi -> English), neighbour passages for context, paged OCR for scans, AI review with suggested questions, expiry date -> calendar, automatic resume after a restart | Real Gemini end-to-end in the browser; retrieval eval `hit@6 = 16/16, hit@1 = 13/16` (`python -m app.workspaces.knowledge_hub.eval.run_eval`); 174 backend tests |

Platform: sign-up/login, organisations and roles, onboarding wizard, audit log, typed AI errors (no silent "safe" defaults), real `/health`, light/dark UI, mobile layout.

Tests: `docker compose exec backend python -m pytest` (about 170 tests, separate test database). Frontend: `npx tsc --noEmit` and `vite build` are clean.

## Accounts and data

- **Demo company** (Kulkarni Textiles, Surat): sign in with `ramesh@kulkarnitextiles.in` / `Kulkarni@2026`, or "open it without signing in" on the login page. Its data is loaded by `scripts/load-demo.ps1`.
- **New sign-ups** start with an empty company and go through onboarding.
- `scripts/reset_data.py` (run with `docker compose exec -T backend python - < scripts/reset_data.py`) deletes every other organisation, wipes the demo company's data and recreates the demo login. Run `load-demo.ps1` afterwards.
- Documents chat understands three intents: lookup (search + quote), overview ("summarise the handbook", "what documents do I have": answered from the document profiles + opening text, still cited), conversation (greetings, "what can you do": answered without AI calls).
- Manual test material for every workspace: `docs/testdata/` (synthetic but realistic; README lists expected findings and questions).
- UI (28 Oct): modelled on a native desktop app. A warm frame with the sidebar sitting directly on it, the content in a white rounded sheet, an icon-only top strip (sidebar toggle, account, search, theme, notifications). The sidebar collapses to an icon rail with fading labels (Ctrl+\\). Settings opens as a modal with its own left nav. Fonts: Figtree (interface), Instrument Serif (hero lines and section titles), Newsreader (contract and notice body text), Geist Mono (identifiers). Inside every workspace the centre holds the one thing that matters (the upload stage, the document, the search, the chat, the planner); history, lists, the document library and the profile facts live in a right-hand panel opened by a round button at the top-right of the sheet (`src/ui/sidepanel.tsx`, state remembered per workspace). Demo sample chips are no longer shown in Vendors. Actions are ink-black; teal for data; peach and lavender tints for notices and tiles.

## How to run

```
docker compose up -d                 # db, qdrant, backend (migrations on start), frontend
.\scripts\load-demo.ps1              # loads the Ramesh Kulkarni demo story using the real AI (about 1 minute)
http://localhost:5173                # click "Try the demo"
http://localhost:8010/docs           # API (port comes from BACKEND_PORT in .env; 8000 is used by another project)
```

Demo files are in `docs/demo/` (contract, cheque-bounce notice, handbook, fire certificate).

## Deliberate limits (say these honestly in the review)

- **Not done / future work:** fine-tuned InLegalBERT classifier, live GST/MCA registry (needs paid API credentials), Professional Tax and other state-specific rules, Hindi UI.
- **Gemini free tier = 20 requests per model per day per Google project** (measured 27 Oct; resets ~12:30 IST). One question = 2 calls, one upload = 1 call. The backend now rotates across every key in `GEMINI_API_KEYS` (comma-separated, from other Google accounts/projects) and then across fallback models (`gemini-3.5-flash-lite`, `gemini-3.5-flash`, each with its own 20/day); `/health/llm` shows what is used up. **Before the demo: add 2-3 teammates' keys to `.env` and restart the backend.** Repeated sample flows are served from the on-disk AI cache and cost nothing.
- **Evaluation:** the RAGAS-style metrics (faithfulness = share of findings whose quote is verified; recall on planted issues) are still to be run on a labelled set (see `docs/REVIEW2_PLAN.md`, step G).
- **Legal content** (rules, notes, deadlines) is general information. Every rule shows its source; a few are flagged "being verified". A CA/lawyer should confirm before it is presented as fact.
- **Vendor registry:** without live API credentials only offline checks and clearly labelled sample records exist. Never presented as live.
- **Gemini free tier** may use prompts to improve Google products (check current terms): use synthetic/public documents only.

## Notable fixes made

Uploads overwrote same-named files; LLM failures showed as "risk 0 / canned reply"; fake telemetry badges; wrong LLP Form 11 and March-TDS dates; compliance sync deleted user tasks and raced on first load; AGPL PDF library; 22 GB Docker image (now 2.8 GB); dev server reloaded (killing running jobs) when tests were edited.

## Git

Nothing is committed. Review with `git status`, then commit on the branch when you are happy. The old Gemini key is still in git history (commit `ad78430`): it should be revoked (the new key is in the git-ignored `.env`).
