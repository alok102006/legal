# LegalOS - review-day pitch and demo script (28 Oct 2026)

Everything below was run on the product on the night of 27 Oct with the real AI and the live GST registry.
All the files named here are already loaded into the demo company, so they open instantly (no AI quota, no waiting).
Login: `ramesh@kulkarnitextiles.in` / `Kulkarni@2026` (or "open it without signing in" on the login page).

## 0. Before you leave home

1. `docker compose up -d` and open http://localhost:5173. Sign in with the demo login.
2. Check `/health/llm` shows no exhausted keys (4 keys, about 240 calls for the day).
3. Keep `docs/testdata/` open in a folder window: this is what you hand to a judge who says "try mine".
4. Laptop plugged in, browser zoom 100%, sidebar expanded, light theme.

## 1. The pitch (60 seconds, before you touch the screen)

"An Indian SME signs contracts it has not read, pays suppliers it has never checked, misses filings it did not know
about, and gets legal notices it does not understand. A lawyer costs 5,000 rupees an hour. 63 million SMEs cannot
afford one on retainer. LegalOS is the operating system they can afford: five workspaces, one calendar, and one rule -
every answer shows its evidence. A quote from the document, a section of the law, or a live registry response.
When it does not know, it says so. Let me show you on a document you choose."

Three lines to say about the engineering whenever there is a pause:
- "Every AI claim is verified against the source text before it is shown. If the quote cannot be found, we say so."
- "The GST check is the government registry, live. The compliance calendar is 28 rules with sources, not a list."
- "604 automated tests. Retrieval measured: the right passage is the top result for 32 of 33 questions."

## 2. The demo (10 minutes, in this order)

### Act 1 - Contracts (3 min): "Read it before you sign it"
Open **Contracts**. The upload stage is the first thing they see. Then open the panel (round button, top right) and
pick **Employment offer letter** (03). Say: "An offer letter a Bengaluru company sent a sales manager."

Point at the verdict rail, high risk, and read the top three drivers. Then click the **critical** finding:
- "Five-year post-employment non-compete" - the text scrolls and highlights clause. Say: "Section 27 of the Contract
  Act makes this unenforceable in India. It knows that. And it tells you what to ask for instead." Open *Suggested change*.
- Then click "Retention of original educational certificates" and "Unbalanced notice period" (6 months vs 30 days).
Open the **Ask** tab and ask: "Can I take a job with a competitor after I leave?" The answer quotes the clause.

If a judge wants another one: **SaaS subscription** (04) finds the 20% renewal increase, the 1-month liability cap for
the vendor vs unlimited for the customer, and Delaware arbitration. **Machinery finance** (05) finds 36% penal
interest, blank cheques and repossession without notice. (The Mumbai lease, 01, now gives 20 findings including the 36-month lock-in, one-sided termination and the repair burden; it works well too.)

What to say: "Six contract types, each with its own checklist. Long documents are cut at a clause boundary and the
screen says so. Photos of pages go through OCR."

### Act 2 - Vendors (1 min): "Check a supplier before you pay"
Open **Vendors**. Type `27AAACT2727Q1ZW` slowly - the cells turn green one by one. Press Enter.
"That is the GST registry, live, not our data: Tata Motors, Active, registered 2017." Then type `27AAACR5055K1Z8`
(one digit changed): the check digit fails before you even press Enter. "Typos and fake numbers never reach the registry."

### Act 3 - Notices (3 min): "A legal notice arrived"
Open **Notices**, open the panel, pick **GST show-cause notice** (07). Say: "This came this morning. The owner is panicking."
- Deadline strip: "16 days left. Reply by 13 November. Counted from the date on the notice, 14 October, plus the 30 days
  the notice itself states. Added to the calendar." Point at the green "found in the text" tick under the date.
- Step 1 "What this is": excess input tax credit, Rs 8.7 lakh including interest and penalty, section 73.
- Step 2 "What the law says" and "if you ignore it": an order is passed on the demand without hearing you.
- Step 3 "What to do now": the checklist. Tick one. "It persists."
- Step 4 "Your reply": click a yellow blank. "The draft uses the notice's own facts and leaves a blank for anything it
  does not know. It never invents a fact. And it cannot be marked final until a lawyer reviews it."

For a second notice, **MSME delayed payment** (09, 3 days left, critical) or **trademark cease and desist** (11, 1 day
left) show the urgency colours. **Income-tax 143(2)** (08) shows a notice with no money claimed but a hard 7-day window.

### Act 4 - Compliance (1 min): "Never miss a filing"
Open **Compliance**. "Every filing for this company for the next 12 months, built from its profile: private limited,
Gujarat, GST monthly, 50 to 199 employees." Point at the one overdue GSTR-3B and the late fee so far.
Open the panel ("Why these filings"), click Edit profile, switch **GST composition scheme** on. GSTR-1 and GSTR-3B
disappear, CMP-08 and GSTR-4 appear. "Rules, not a hard-coded list. 30 rules, each with its source, checked by a lint test." Switch it back.

### Act 5 - Documents (1.5 min): "Ask your own papers"
Open **Documents**. In the scope picker choose **Safety**. Ask in Hinglish:
`accident report kitne ghante ke andar karna hai?`
The answer is in Hindi: "24 ghante ke bheetar", with a citation. Click the chip: the Hindi passage opens, "found word for word".
Then scope **Board** and ask: `Who is authorised to sign cheques and up to what amount?` - four verified citations.
Then: `summarise the leave policy` (scope HR). "Summaries, lookups and Hinglish, all grounded."

Asked across everything, the Hinglish accident question now answers from the safety manual (24 hours) and adds a note
that the insurance schedule has a 48-hour claim rule. Scoping to Safety still gives the cleanest answer on stage.

### Close (30 s)
"Every answer you saw carried its evidence. When the AI does not know, it says so. That is the difference between a
chatbot and something a business can rely on. Future work: a fine-tuned Indian legal model, and lawyer-verified rules
for every state."

## 3. If a judge hands you their own file

Contracts, Notices and Documents all accept PDF, Word, text and photos. A fresh file costs 2 AI calls (3 for a photo)
and takes 20 to 60 seconds. Say what happens while it runs: "reading, finding clauses, checking Indian law, scoring".
If the AI is rate-limited, the screen says so honestly; switch to a pre-loaded file and carry on.

## 4. Questions judges ask, and the answers

- **How do you stop hallucination?** Every finding must carry a verbatim quote. We search for that quote in the
  document before showing it; unverifiable ones are flagged. Retrieval is hybrid (keywords + embeddings + a reranker).
- **Is this legal advice?** No. Decision support. Rules show their source, replies need lawyer review, and we say so on screen.
- **Where is the data?** Local Postgres and Qdrant, per organisation. The AI provider sees only the document being analysed.
- **Accuracy numbers?** Retrieval hit@1 96% and hit@8 100% on a 33-question labelled set (tables, Hindi, exact codes, multi-document). 604 automated tests. Citation verification rate shown live as "confidence".
- **Business model?** Per-company subscription for SMEs; CA firms as the channel (one CA serves 50 to 200 SMEs).
- **What is not done?** Fine-tuned InLegalBERT, Professional Tax for all states, Hindi UI, MCA registry lookups.
- **Why not ChatGPT?** It cannot check the GST registry, cannot build a filing calendar from a profile, cannot verify
  its own quotes against your file, and does not push deadlines to a calendar your CA sees.

## 5. What was verified on 27 Oct night (so you can quote it)

| File | What the product found |
|---|---|
| 01 Mumbai lease | 20 findings: 36-month lock-in with full-term penalty (critical), landlord exit at will (critical), structural repairs on the licensee (critical), 180-day deposit refund |
| 02 NDA "mutual" | 14 findings, 3 critical: fixed penalty per breach, unlimited indemnity, assignment of our improvements |
| 03 Offer letter | 12 findings: 5-year non-compete (critical), certificate retention, unilateral amendments, 6-month vs 30-day notice |
| 04 SaaS | 19 findings: vendor termination + exit penalty, 1-month liability cap vs unlimited, 20% renewal increase |
| 05 Machinery finance | 18 findings, 5 critical: 36% penal interest, blank cheques, acceleration, repossession without notice |
| 06 Distribution | 15 findings: liability imbalance, shortfall penalty, unilateral price revisions, pan-India non-compete |
| 07 GST DRC-01 | typed as GST show-cause (DRC-01); Rs 8,71,250; three dates weighed (stated 13 Nov, 30-day period from 14 Oct, hearing 24 Nov) and the earliest chosen; 4/4 quotes verified; "Your CA" handles it; 5 actions |
| 08 Income tax 143(2) | income_tax_notice, 7 days, 3/3 quotes verified |
| 09 MSME demand | Rs 12,35,600, 3 days left, critical |
| 10 Rent default | Rs 2,55,000, reply by 4 Nov |
| 11 Trademark | 1 day left, critical |
| 12 Consumer | Rs 1,95,000, 17 days |
| 13 Labour | Rs 3,17,553, 1 day left, critical |
| 14-19 Documents | all indexed and reviewed; Hindi manual detected as Hindi; expiry dates picked up (insurance 9 Jan 2027, price list 31 Mar 2027) |
| Questions | casual leave 8 days (100%), PO approval limit (82%), Hindi 24-hour rule when scoped to Safety (82%), cheque signatories (100%, 4 citations), insurance expiry + 48h claim (91%), leave summary (100%) |
| Vendors | 27AAACR5055K1Z7 Reliance live Active; 27AAACT2727Q1ZW Tata Motors (confirm once on the portal) |
