# Review on 28 Oct 2026 - execution plan

Goal: a working, accurate, good-looking product that tells the deck's story (Ramesh Kulkarni, textile owner in Surat,
five headaches -> five workspaces in one "operating system for a business's legal life"), and that is honest about what
is done and what is future work.

State at 27 Oct: Gemini key works (verified end to end). Done: auth + organisations, Contracts v2, Compliance v2, new UI.
Still on the old code/old design: Vendors, Notices, Documents.

## Demo story (10 minutes)

1. **Home** - Ramesh's company (Kulkarni Textiles, Surat, Gujarat): next deadlines, contracts needing attention.
2. **Contracts** - upload the supplier agreement: the Rs 2 lakh penalty clause is caught, with the exact quote and page,
   the MSME 45-day rule, and a suggested counter-clause. Ask the contract a question.
3. **Vendors** - a supplier GSTIN with a typo is rejected instantly; a cancelled registration is flagged before payment;
   the vendor is linked to its contract.
4. **Compliance** - the GST / TDS / PF-ESI / ROC calendar for his company type; mark a filing done.
5. **Notices** - upload a legal notice: type, urgency, deadline extracted, reply drafted for lawyer review; the deadline
   appears in the calendar.
6. **Documents** - ask "what notice period did we agree for employees?" and get a page-cited answer.
7. **Evaluation slide** - numbers from a labelled Indian-SME contract set (the start of the dataset our research gap asks for).

## Build order (each step is tested before the next)

| # | Work | Why |
|---|------|-----|
| A | Contracts polish: merge duplicate AI/rule findings, fix scoring, check on real contracts | Hero flow must be accurate |
| B | Demo identity: "Kulkarni Textiles, Surat", persona Ramesh Kulkarni | Matches the deck |
| C | Vendors v2: GSTIN/PAN checks, vendor records, trust checklist with reasons, contract links, honest registry status | Deck headache #2 |
| D | Notices v2: structured extraction, deadline rules, reply with placeholders, lawyer-review gate, calendar link | Deck headache #5 |
| E | Documents v2: page-aware ingestion, hybrid search (keyword + vector, rank-fused), cited Q&A | Deck headache #4 + promised hybrid RAG |
| F | Cross-links: contract renewal -> reminders, vendor <-> contract, notice deadline -> calendar, Home feed | "Operating system", not five tools |
| G | Evaluation: synthetic labelled contracts + runner + results table | Deck's evaluation promise |
| H | UI/QA pass: screenshots on desktop/mobile/dark, accessibility, demo data, docs | Polish |

## Honest scope statements for the review

- Done: all five workspaces on one platform with real AI; hybrid retrieval (keyword + vector with rank fusion);
  grounded answers with verified quotes; rules-as-data compliance; evaluation on our own labelled set.
- Simplified: evaluation uses RAGAS-style metrics from our harness (faithfulness = share of findings whose quote is
  verified in the document; recall on planted issues), not the `ragas` library.
- Future work: fine-tuned InLegalBERT (needs a larger labelled dataset and GPU), cross-encoder reranker, live MCA/GST
  registry lookups (need paid API credentials), Professional Tax and other state-specific rules.

## Risks

- Gemini free-tier rate limits (one analysis uses 2 calls; keep demo documents few and short).
- Legal rules are reminders and decision support, not legal advice; each shows its source and "confirm with your CA".
- Time: one day. If something slips, cut in this order: G (reduce to a small set), F extras, E reranking, D polish.
  Never cut A, C, the story, or honest labelling.
