# What to test, and what to type: a first-time user's checklist

*Companion to USER_GUIDE_LAYMAN.md. Do these in order; each block is 5 to 10 minutes. "Pass" means what you see matches the "Expect" column. Note anything else as a bug.*

All test files are in `docs/testdata/` (contracts/, notices/, documents/). The demo company already has them loaded; re-uploading costs AI quota (about 2 calls per file, 20 calls per key per day), so prefer the pre-loaded copies and upload fresh files only when a test says so.

---

## 0. Before anything

| # | Do | Expect |
|---|---|---|
| 0.1 | Open http://localhost:5173 | Login page loads, no console errors |
| 0.2 | Click "or open it without signing in" | Lands on Home as Ramesh, Kulkarni Textiles |
| 0.3 | Settings (sidebar) > System | Database: Working. Document search: Working. AI analysis: Working with a model name. GST registry: Live (or "Offline checks only", note which) |
| 0.4 | Open http://localhost:8010/health/llm in a new tab | JSON shows keys and how many calls are left. If all exhausted, stop and add keys before testing uploads |
| 0.5 | Press Ctrl+\ twice | Sidebar collapses to icons and expands again |
| 0.6 | Toggle the theme button (top strip) | Dark mode, everything still readable, toggle back |

---

## 1. Home

| # | Do | Expect |
|---|---|---|
| 1.1 | Look at the four numbers on the right | They match what you later count in Compliance (overdue), Contracts (high risk) and Notices (open) |
| 1.2 | Click a row under "Needs your attention" | Goes to that exact contract / notice / filing |
| 1.3 | Click "Calendar" link in Next deadlines | Opens Compliance |
| 1.4 | Sign out, create a new account (any name, company "Test Pvt Ltd") | Onboarding wizard, 3 steps. Home then shows "Getting started" at 20% |
| 1.5 | In Getting started, click "Try a sample" next to Contract | A sample contract loads and opens. Progress bar moves |
| 1.6 | Sign back in as Ramesh | His data is intact, nothing from Test Pvt Ltd leaks in |

---

## 2. Contracts

### Pre-loaded (no AI cost)
| # | Do | Expect |
|---|---|---|
| 2.1 | Contracts > round button > open "Employment offer letter" (03) | Verdict rail says **High** risk. A **critical** finding: 5-year post-employment non-compete |
| 2.2 | Click that finding | Contract text scrolls and highlights clause 4.1. Explanation mentions section 27, Indian Contract Act. "Suggested change" opens |
| 2.3 | Click "Unbalanced notice period" | Highlights 6 months (employee) vs 30 days (employer) |
| 2.4 | Click "Retention of original educational certificates" | Highlights clause 11.2 |
| 2.5 | Filter by severity (chips above the list) | List narrows correctly |
| 2.6 | Key terms tab | Parties, CTC, notice periods, governing law filled in. Nothing invented (compare with the file) |
| 2.7 | Ask tab: `Can I take a job with a competitor after I leave?` | Answer quotes clause 4.1 and mentions the 5-year restriction |
| 2.8 | Ask tab: `What is my salary?` | Answer quotes the CTC figure from the letter |
| 2.9 | Ask tab: `Does this contract mention a pension?` | Should say it is not in the contract, not invent one |
| 2.10 | Open SaaS (04) | Finds 20% renewal increase, 1-month liability cap vs unlimited, Delaware arbitration, 7-day data export |
| 2.11 | Open Machinery finance (05) | 4 critical: 36% penal interest, blank cheques, repossession without notice, acceleration |
| 2.12 | Open NDA (02) | Flags that "Mutual" is one-sided, Rs 25 lakh per breach, unlimited indemnity, Singapore law |
| 2.13 | Open Distribution (06) | Rs 2 crore minimum, 30% shortfall penalty, no exit for 3 years, pan-India non-compete |
| 2.14 | Open Lease (01) | Known weak spot: only about 3 findings. Note what it misses from: 36-month lock-in, 15% escalation, 180-day deposit, 15-day landlord exit, all repairs on tenant |
| 2.15 | Three-dot menu > Delete on any contract, then cancel | Confirm dialog appears, cancel keeps it |

### Fresh upload (costs AI calls)
| # | Do | Expect |
|---|---|---|
| 2.16 | Upload `contracts/01_office_lease_mumbai.txt` again, "Which party are you?" = `Licensee` | Progress text: reading, finding clauses, checking Indian law, scoring. Finishes in 20 to 60 s |
| 2.17 | Upload a photo (take a phone picture of one printed page) | OCR path runs, text appears, at least one finding or an honest "nothing significant" |
| 2.18 | Upload a 40+ page PDF (any long agreement) | Warning banner "Long contract: only part of it was reviewed" and a visible "not reviewed below" line in the text |
| 2.19 | Upload a non-contract (a restaurant menu PDF) | Type "other", few or no findings, no crash |
| 2.20 | Upload an empty .txt file | Friendly error, not a stack trace |
| 2.21 | Upload a 25 MB file | Rejected with a clear size message |
| 2.22 | Upload the same file twice | Two separate entries, neither overwrites the other |
| 2.23 | After upload, go to Compliance | Any dates found (expiry, renewal) appear as reminders |

---

## 3. Vendors

| # | Type | Expect |
|---|---|---|
| 3.1 | `27AAACT2727Q1ZW` slowly, one character at a time | Boxes turn green one by one. On Enter: Tata Motors Limited, Maharashtra, Active, registered 2017 |
| 3.2 | `27AAACR5055K1Z7` | Reliance Industries Limited, Active |
| 3.3 | `27AAACR5055K1Z8` | Last box turns red before Enter. Message about check digit / possible typo. Registry is **not** called |
| 3.4 | `24ABCDE1234F1Z5` | Check character wrong, flagged invalid |
| 3.5 | `27AAACT2727Q1Z` (14 chars) | "Too short" style message, Check button disabled |
| 3.6 | `AAACT2727Q` (a PAN only) | Recognised as PAN, structure check passes, says registry lookup needs a GSTIN |
| 3.7 | `UDYAM-MH-26-0012345` | Recognised as Udyam number, format valid |
| 3.8 | lower case `27aaact2727q1zw` | Auto-uppercased |
| 3.9 | `99AAACT2727Q1ZW` | State code 99 invalid |
| 3.10 | paste with spaces `27 AAACT 2727 Q1ZW` | Either cleaned or rejected clearly, not half-parsed |
| 3.11 | Save Tata Motors with name "Tata Motors Ltd" | Appears in Your suppliers. Open it: History of checks has one row |
| 3.12 | Check the same GSTIN again, then open the supplier | History has two rows with timestamps |
| 3.13 | Edit supplier > set MSME status = registered | Save re-runs checks; risk reasons update |
| 3.14 | Open a contract whose counterparty is a saved supplier | Supplier card shows on the contract and the contract shows under the supplier's linked records |
| 3.15 | Turn off the live registry (clear GST_API_PROVIDER in .env, restart backend) and check 3.1 again | Card says "Offline checks only" / "not checked", never shows a fake Active |
| 3.16 | Delete the supplier | Confirm dialog, then gone from list |

---

## 4. Notices

### Pre-loaded
| # | Do | Expect |
|---|---|---|
| 4.1 | Notices > round button > GST show-cause (07) | Deadline strip: received 14 Oct 2026, reply by 13 Nov 2026, days-left counter correct for today's date. Green "found in the text" tick |
| 4.2 | Step 1 | GST notice, Form DRC-01, section 73, Rs 8,71,250 total (tax 6,84,500 + interest 1,18,300 + penalty 68,450), personal hearing 24 Nov |
| 4.3 | Step 2 | Mentions section 73(8) option (pay tax + interest by deadline, no penalty) and "if you ignore it" (order passed without hearing) |
| 4.4 | Step 3: tick two checklist items, reload the page | Ticks persist; "2 of 5 done" |
| 4.5 | Step 4: click a yellow blank | Cursor jumps to it; fill in a value; blank disappears |
| 4.6 | Type "make it shorter" in the redraft box | A new version appears in the version dropdown; old version still selectable |
| 4.7 | Try to mark the reply final before lawyer review | Blocked, with a message |
| 4.8 | Mark "Reviewed by lawyer", then final | Step 4 shows "Reviewed by lawyer" and done tick |
| 4.9 | Compliance tab | "Reply to GST notice" reminder dated 13 Nov exists |
| 4.10 | Open MSME demand (09) | Rs 12,35,600, critical colour, mentions 45-day rule (s.15 MSMED), 75% deposit (s.19) |
| 4.11 | Open Trademark (11) | 1 day left, critical, Trade Marks Act s.29, no statutory reply window so deadline comes from the letter's "7 days" |
| 4.12 | Open Rent default (10) | Both dates reported: pay by 4 Nov and vacate by 30 Nov. Two bounced cheque numbers mentioned |
| 4.13 | Open Income tax 143(2) (08) | No amount claimed (should say so), 7-day window, s.144 and s.271(1)(b) consequences |
| 4.14 | Open Employee dispute (13) | Rs 3,17,553 breakdown, s.25F Industrial Disputes Act |
| 4.15 | Open Consumer (12) | Rs 85,000 + 1,00,000 + 10,000; Consumer Protection Act 2019 |
| 4.16 | Side panel sort | Most urgent (fewest days left) at the top |

### Fresh upload
| # | Do | Expect |
|---|---|---|
| 4.17 | Paste the text of `docs/demo/02_cheque_bounce_notice.txt` | Type cheque_bounce, deadline marked **statutory** (15 days, s.138 NI Act cited) |
| 4.18 | Paste a notice with the date removed | Deadline shows **unknown**, not a guessed date. Deadline strip explains why |
| 4.19 | Paste a notice that says "reply within 30 days" but has no date | Deadline unknown or "30 days from receipt, enter received date", not invented |
| 4.20 | Upload a photo of a printed notice | OCR runs, type detected |
| 4.21 | Paste plain gibberish ("asdf qwer") | Type "other", honest "could not understand", no crash |
| 4.22 | Paste a notice written in Hindi | Type detected, summary readable, deadline found if present |
| 4.23 | While analysis is running, navigate away and back | Progress continues; result appears |
| 4.24 | Delete a notice | Its calendar reminder also disappears from Compliance |

---

## 5. Compliance

| # | Do | Expect |
|---|---|---|
| 5.1 | Open Compliance | 12-month strip, Next up box, Overdue box with at least one GSTR-3B and a late fee amount |
| 5.2 | Late fee sanity: GSTR-3B is Rs 50/day (Rs 20/day nil return), capped. Compare shown amount with days overdue | Matches |
| 5.3 | Click each month | Filings grouped by week; months with nothing say "Nothing due in <month>" |
| 5.4 | Hover a filing's source | Full Act / rule reference shown |
| 5.5 | Find any italic "being verified" | Tooltip explains the date is not yet confirmed |
| 5.6 | Tick "Mark as filed" on one item, reload | Stays ticked. Undo works |
| 5.7 | Home | Overdue count dropped by one |
| 5.8 | "Mark as already filed" catch-up (if 2+ overdue) | Confirm dialog with count; all overdue cleared in one go |
| 5.9 | Add your own reminder: "Renew FSSAI licence", date next month | Appears in that month; can be deleted |
| 5.10 | Round button > Why these filings > Edit > switch **GST composition scheme** ON | GSTR-1 and GSTR-3B vanish; CMP-08 (quarterly) and GSTR-4 (annual) appear |
| 5.11 | Switch it back OFF | Original calendar returns; your "filed" ticks and custom reminders are still there (the sync must not delete user data) |
| 5.12 | Change state to Karnataka | Professional Tax (Karnataka) appears. Change to Maharashtra: it disappears and nothing else breaks |
| 5.13 | Change entity type to LLP | AOC-4 / MGT-7 / AGM go; LLP Form 8 and Form 11 appear |
| 5.14 | Change employees to under 10 | EPF / ESI rules disappear (ESI threshold 10, EPF 20) |
| 5.15 | Set GST filing to Quarterly (QRMP) | GSTR-1 quarterly and PMT-06 monthly appear instead of monthly GSTR-1 |
| 5.16 | Click Refresh (rebuild from profile) twice fast | No duplicate filings |
| 5.17 | Read the "not covered yet" list in the panel | Lists Professional Tax other states, Shops and Establishment, LWF, ADT-1, OPC, licences, TCS |

---

## 6. Documents

### Questions on the pre-loaded set (scope in brackets). Each costs 2 AI calls.
| # | Scope | Type | Expect |
|---|---|---|---|
| 6.1 | HR | `How many casual leaves do I get in a year?` | 8 days, citation chip opens the leave policy, green tick "found word for word", confidence near 100% |
| 6.2 | HR | `How many days of earned leave can I carry forward?` | 30 (45 for plant staff) |
| 6.3 | HR | `What happens if I am late for the fourth time in a month?` | Half-day CL deducted |
| 6.4 | HR | `Can plant staff work from home?` | No, with the WFH clause quoted |
| 6.5 | HR | `summarise the leave policy` | Overview answer: CL/SL/EL, WFH, maternity 26 weeks, paternity 5 days, still cited |
| 6.6 | Finance | `Who must approve a purchase order of Rs 12 lakh?` | GM Operations (Rs 5 lakh to Rs 25 lakh band) |
| 6.7 | Finance | `What is the payment term for an MSME vendor and what law says so?` | 30 days, never beyond 45, MSMED Act s.15 |
| 6.8 | Finance | `Which documents does a new supplier have to submit?` | PAN, GST certificate, Udyam, cancelled cheque, etc. |
| 6.9 | Safety | `accident report kitne ghante ke andar karna hai?` | Hindi answer "24 ghante ke bheetar", chip opens Hindi passage, verified |
| 6.10 | Safety | `दुर्घटना की रिपोर्ट कितने घंटे के भीतर देनी होती है?` | Same answer in Devanagari |
| 6.11 | Safety | `Within how many hours must an accident be reported?` (English) | 24 hours, plus 12-hour written notice to Inspector for serious accidents |
| 6.12 | Safety | `fire drill kitni baar hoti hai aur agli kab hai?` | Every 3 months; next by 14 Nov 2026 |
| 6.13 | Safety | `welding ke liye kaunsa PPE zaroori hai?` | Lists PPE for welding from the manual |
| 6.14 | Sales | `What is the price and MOQ of the 6205-2RS bearing?` | Rs 96 per piece, MOQ 100 (SIP-BRG-101) |
| 6.15 | Sales | `What discount do I get on an invoice of Rs 6 lakh?` | 5% (from Rs 5 lakh), plus whether lubricants are included |
| 6.16 | Sales | `Until when is this price list valid?` | 31 March 2027 |
| 6.17 | Board | `Who is authorised to sign cheques and up to what amount?` | Patel and Shah; single up to Rs 5 lakh; joint up to Rs 50 lakh; 4 citations |
| 6.18 | Board | `Can one director alone sign a Rs 8 lakh payment?` | No, joint signature needed above Rs 5 lakh |
| 6.19 | Board | `Can the directors take a loan under this resolution?` | No, borrowing excluded (s.179(3)) |
| 6.20 | Finance | `When does the insurance policy expire?` | 9 Jan 2027, no auto-renewal. Also check Compliance shows this expiry |
| 6.21 | Finance | `Within how many hours must a loss be reported to the insurer?` | 48 hours; claim documents within 15 days |
| 6.22 | Finance | `Is fire caused by an earthquake covered?` | No, earthquake excluded |
| 6.23 | All | `accident report kitne ghante ke andar karna hai?` | May return both 24 h (safety manual) and 48 h (insurance). Acceptable if both cited; a bug if it merges them into one number |
| 6.24 | All | `What documents do I have?` | Lists all six with one line each |
| 6.25 | All | `What is the CEO's salary?` | "Not found in your documents", no invented number |
| 6.26 | All | `hi` / `what can you do?` | Instant friendly reply, no citations, no AI quota used |
| 6.27 | All | `Compare the notice period in the HR policy with the offer letter` | Offer letter is in Contracts, not Documents: should answer only from the HR policy and say the other is not available here |

### Behaviour tests
| # | Do | Expect |
|---|---|---|
| 6.28 | Click a citation chip | Bottom sheet "Where this comes from", highlighted quote, green tick |
| 6.29 | Find an answer with an amber question mark | Confidence below 100 and the chip says quote could not be matched |
| 6.30 | Click Stop while an answer streams | Stops cleanly, partial answer kept |
| 6.31 | Ask a follow-up `and for plant staff?` after 6.2 | Uses chat context, answers 45 days |
| 6.32 | Rename a chat, delete a chat | Documents remain |
| 6.33 | Add a new document into a new collection "Legal" | Processing steps show; green dot when ready; summary and suggested questions appear |
| 6.34 | Upload a scanned PDF | Paged OCR; searchable afterwards |
| 6.35 | Restart the backend while a document is processing | It resumes and finishes (automatic resume) |
| 6.36 | Delete a document | Its expiry reminder disappears from Compliance; its chunks no longer appear in answers |

---

## 7. Cross-workspace and robustness

| # | Do | Expect |
|---|---|---|
| 7.1 | Ctrl+K (command palette) type "GST" | Jumps to matching notice / filing / page |
| 7.2 | Notifications bell | Lists the same urgent items as Home |
| 7.3 | Resize to phone width | Side panels become sheets; nothing overflows |
| 7.4 | Exhaust the AI quota (or set a wrong key) and upload a contract | Screen says the AI is rate-limited / unavailable in plain words. Never a "risk 0" or blank summary |
| 7.5 | Stop the Qdrant container, ask a Documents question | Settings > System shows Document search Down; chat gives a clear error |
| 7.6 | Open any item URL from another company's account | 404 / not found, not the other company's data |
| 7.7 | Audit: Settings > Account or activity log | Every upload, delete, mark-filed appears with time |
| 7.8 | Run the backend tests | `docker compose exec backend python -m pytest` reports about 179 passed |
| 7.9 | Run the retrieval eval | `docker compose exec backend python -m app.workspaces.knowledge_hub.eval.run_eval` reports hit@6 = 16/16 |

---

## 8. Known weak spots to probe (from the team's own notes)

- Lease contract (01) under-finds. Try it and list what it missed.
- GST notice (07) uses s.73; for FY 2024-25 the correct section is s.74A. Does the system mention this?
- Income-tax 143(2) (08) may be time-barred. Does the system raise the service window?
- Professional Tax exists only for Karnataka. Gujarat (the demo company's state) gets none.
- Vendor registry depends on paid API keys. Without them, confirm nothing is shown as "live".
- Gemini free tier: 20 calls per model per key per day. Plan the number of fresh uploads accordingly.
- The old Gemini key is still in git history (commit ad78430) and should be revoked.
