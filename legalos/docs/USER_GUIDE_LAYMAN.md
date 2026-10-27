# LegalOS, explained to a first-time user

*Written from the point of view of a normal business owner who has never used the product before. Nothing here needs you to know programming or law.*

---

## 1. The story in one page

Meet **Ramesh Kulkarni**. He runs Kulkarni Textiles, a mid-sized cloth business in Surat, Gujarat. He has about 80 employees, a GST number, and no lawyer on staff. A lawyer costs him 5,000 rupees an hour, so he only calls one when something has already gone wrong.

In a normal month Ramesh faces things like this:

1. A new customer sends him a 14-page **contract** and wants it signed by Friday. He reads the first page and signs.
2. A new **supplier** gives him a GST number on an invoice. He pays, hoping the number is real.
3. A brown envelope arrives from the GST department. It is a **legal notice**. It has a deadline somewhere inside, but he does not know where, or what happens if he misses it.
4. His accountant reminds him on the last day that a **filing** was due yesterday. There is a late fee.
5. An employee asks "how many leaves can I carry forward?" Ramesh knows it is written in the HR policy somewhere, but nobody can find the **document**.

LegalOS is one website that handles exactly those five problems. Each one is a **workspace**, which is just a tab on the left side of the screen:

| Problem | Workspace tab | One-line promise |
|---|---|---|
| Contract to sign | **Contracts** | Read it before you sign it |
| Supplier to pay | **Vendors** | Check a supplier before you pay |
| Legal notice arrived | **Notices** | Understand it and reply in time |
| Filing deadlines | **Compliance** | Never miss a filing |
| Company papers | **Documents** | Ask your own papers a question |

And one rule holds everything together: **every answer shows its evidence.** When the system flags a clause, it quotes the clause from your own file. When it gives a deadline, it shows where in the notice the date came from. When it does not know, it says "unknown" instead of guessing.

---

## 2. Getting in

1. Open `http://localhost:5173` in your browser (the product runs on your own machine during the demo).
2. You see a login page. Use the demo account:
   - Email: `ramesh@kulkarnitextiles.in`
   - Password: `Kulkarni@2026`
   - Or click **"or open it without signing in"** underneath the form. It drops you straight into Ramesh's company.
3. If you make a *new* account instead, the system first walks you through a three-step **onboarding**: company name, type of business, state, GSTIN (optional), number of employees, turnover, MSME status and which GST filing style you use. These answers drive the Compliance calendar later, so they matter.

**What the screen looks like.** There is a warm-coloured frame. On the left is a sidebar with seven entries: Home, Contracts, Vendors, Notices, Compliance, Documents, Settings. The middle is a white "sheet" where the actual work happens. At the top right of the sheet there is usually a **round button**: it opens a side panel with your history, your saved items, or your profile, depending on which workspace you are in. Press `Ctrl+\` to collapse the sidebar into icons if you want more room.

---

## 3. Home: "where does my company stand?"

Home greets you by first name and shows four numbers on the right: overdue filings, filings due in 7 days, high-risk contracts, open notices. Below that, **"Needs your attention"** lists the six most urgent things across every workspace, colour-coded (peach = critical, amber = high, lavender = medium). Click any row and it takes you to the thing itself.

If you are brand new, a **Getting started** checklist appears with five steps and a "Try a sample" button next to most of them. That button loads a pre-made example so you can see a workspace working before you upload anything of your own.

Lower down is a day-by-day **activity log** ("Yesterday 4:12 pm: Reviewed contract X"). Think of it as the diary of what the system did for you.

---

## 4. Contracts: "Read it before you sign it"

### What it is for
You upload a contract. The system reads it, finds every clause that could hurt you, quotes the clause, explains why it is a problem under Indian law, and suggests what to ask for instead.

### How you use it
1. Click **Contracts**. The first thing you see is the upload area with the headline "Read it before you sign it."
2. Drop in a PDF, Word file, text file, or even a photo of a page (photos are read with OCR). There is one optional box: **"Which party are you?"** Type "Buyer" or "Tenant" or your company name. Leave it blank and it assumes you are Kulkarni Textiles.
3. Wait 20 to 60 seconds. The screen says what it is doing: reading, finding clauses, checking Indian law, scoring.
4. The **reading room** opens. The contract text is in the middle with risky clauses highlighted. On the right is the **verdict rail** with four tabs:
   - **Findings**: the list of problems, each with a severity (critical / high / medium / low), a word-for-word quote, the page number, why it matters, and a **Suggested change**. Click a finding and the contract scrolls to that clause and highlights it. There is a "Not in this contract" section too, for protections that *should* be there but are missing (for example, no cap on your liability).
   - **Score**: an overall risk level with the top drivers.
   - **Key terms**: parties, dates, money, notice periods, governing law, pulled out in a table.
   - **Ask**: a chat box. Ask "Can I leave early?" and the answer quotes the relevant clause.
5. Dates found in the contract (renewal, expiry, notice windows) are pushed to the Compliance calendar automatically.

### Things a normal user should notice
- The system knows **what kind** of contract it is (lease, NDA, employment, supply, service, distribution, franchise, loan, software licence, partnership) and runs a different checklist for each.
- If the contract is very long, it reviews the first part up to a clause boundary and shows a line saying **"not reviewed below"**. It does not pretend to have read the whole thing.
- A long press on the round button at top right opens **Your contracts**, the history list, with a coloured dot per contract showing risk.

### Pre-loaded examples in the demo company
| File | What you will see |
|---|---|
| Employment offer letter (03) | 5-year non-compete flagged **critical** (unenforceable in India under section 27 of the Contract Act), 6-month vs 30-day notice imbalance, retention of original certificates, Rs 3 lakh training bond |
| "Mutual" NDA (02) | Titled mutual but one-sided, Rs 25 lakh fixed penalty per breach, unlimited indemnity, 7-year term, Singapore law |
| SaaS subscription (04) | 20% automatic price rise on renewal, vendor liability capped at 1 month's fees vs yours unlimited, 7-day data export window, Delaware arbitration |
| Machinery finance (05) | 36% penal interest, five blank signed cheques, repossession without notice, one missed EMI is default |
| Distribution agreement (06) | Rs 2 crore minimum purchase with 30% shortfall penalty, you cannot exit for 3 years, "exclusive" territory that is not exclusive |
| Mumbai office lease (01) | 36-month lock-in, 15% yearly escalation, deposit refund after 180 days with no interest (this one found fewer issues; avoid it on stage) |

---

## 5. Vendors: "Check a supplier before you pay"

### What it is for
Before you pay a new supplier, you type their GST number (GSTIN), PAN or Udyam number and the system tells you if it is real.

### How you use it
1. Click **Vendors**. One big box in the middle: "GSTIN, PAN or Udyam number".
2. Start typing. The number is checked **as you type**: the 15 boxes turn green one by one as each part passes (state code, PAN inside it, entity code, the letter Z, the check digit). A typo turns a box red **before** you press Enter.
3. Press Enter or click Check. If a live GST registry connection is configured, you get a **verification card**: legal name, trade name, status (Active / Cancelled), registration date, state, business type. If there is no live connection, the screen says "Offline checks only" honestly rather than pretending.
4. Click **Save** and the supplier goes into **Your suppliers** (the round button at top right). Each saved supplier has a page with a risk verdict, reasons, linked contracts, and a **History of checks** with timestamps.

### Numbers to try
| Type this | Expect |
|---|---|
| `27AAACT2727Q1ZW` | Valid. Tata Motors Limited, Maharashtra, Active, registered 2017 (live registry) |
| `27AAACR5055K1Z7` | Valid. Reliance Industries Limited, Maharashtra, Active |
| `27AAACR5055K1Z8` | Last digit changed. **Check digit fails** on the spot, never sent to the registry. "Possible typo, re-verify." |
| `24ABCDE1234F1Z5` | Looks like a Gujarat number but the check character is wrong. Should say invalid / not found |

---

## 6. Notices: "A legal notice arrived"

### What it is for
A scary letter arrives: from the GST department, income tax, a supplier's lawyer, a landlord, a trademark owner, an ex-employee, a consumer. You upload it. The system tells you what it is, when you must reply, what the law says, what to do today, and writes the first draft of your reply.

### How you use it
1. Click **Notices**. Upload the letter (PDF, photo, Word) or paste the text.
2. The first thing at the top is the **deadline strip**: received date, today, reply-by date, and days left. Under the reply-by date there is a small tick saying either **"found in the text"** (the date or the "30 days" wording was in the notice itself), **"statutory"** (the law sets this window; the section is cited), or **"unknown"** (the system refused to guess). The deadline is also added to the Compliance calendar.
3. Below that are four numbered steps:
   - **Step 1, What this is.** Type of notice, who sent it, what they want, how much money, in plain words.
   - **Step 2, What the law says.** The relevant Act and section, and "if you ignore it" consequences.
   - **Step 3, What to do now.** A checklist (gather invoices, reconcile returns, call your CA). Tick items; they stay ticked.
   - **Step 4, Your reply.** A draft letter that uses only facts from the notice. Anything it does not know is a **yellow blank** you click and fill in. You can type an instruction like "make it firmer" to redraft. Drafts are versioned. A **lawyer review gate** means it cannot be marked "final" until someone marks it as reviewed by a lawyer.
4. The round button at top right opens **Your notices**: every open notice sorted by urgency.

### Fifteen kinds of notice it recognises
Cheque bounce, legal payment demand, GST notice, income-tax notice, labour/PF/ESI notice, MSME delayed payment, consumer complaint, trademark/copyright cease-and-desist, employment dispute, rent/eviction, court summons, defamation, contract breach, other regulatory, other.

### Pre-loaded examples
| File | What you will see |
|---|---|
| GST show-cause DRC-01 (07) | Rs 8,71,250 demand, section 73, reply by 13 Nov 2026 (16 days), "found in the text" tick, option to pay tax+interest and avoid penalty |
| Income tax 143(2) (08) | No money claimed, but a hard 7-day window, documents list |
| MSME delayed payment (09) | Rs 12,35,600, 3 days left, **critical** |
| Rent default and eviction (10) | Rs 2,55,000 arrears, reply by 4 Nov, vacate by 30 Nov (two dates, both shown) |
| Trademark cease and desist (11) | 1 day left, **critical** |
| Consumer complaint (12) | Rs 1,95,000 claimed, 17 days |
| Employee termination dispute (13) | Rs 3,17,553 claimed, 1 day left, **critical** |

---

## 7. Compliance: "Never miss a filing"

### What it is for
A 12-month calendar of every government filing your company must do, built automatically from your company profile. Not a generic list: a private limited company in Gujarat with monthly GST and 50 to 199 employees gets a different calendar than a sole proprietor in Karnataka with quarterly GST.

### How you use it
1. Click **Compliance**. If you have not filled your profile it says "Tell us about your company first."
2. Otherwise you see a **12-month strip** across the top. Click a month to see what is due that month, grouped by week.
3. A **Next up** box shows the single nearest deadline. An **Overdue** box (red) lists missed filings with the **late fee so far**, calculated per day.
4. Each filing shows: title (for example "GSTR-3B, summary return"), due date, the **source** (which Act or rule it comes from), and "If missed: ..." with the penalty. A few say *"being verified"* in italics, meaning the team has not yet confirmed the date against the latest notification. That is deliberate honesty.
5. Tick the checkbox to **mark as filed**. If you are new and many past filings show overdue, there is a "Mark as already filed" catch-up button to clear them in one go.
6. **Add your own reminder** for things the system does not track yet, such as an FSSAI licence renewal or a board meeting.
7. The round button at top right opens **Why these filings**: your profile facts with switches. Flip **GST composition scheme** on and watch GSTR-1 and GSTR-3B disappear while CMP-08 and GSTR-4 appear. Flip it back.

### What is covered (28 rules)
GSTR-1 (monthly and quarterly), GSTR-3B (monthly and QRMP), PMT-06, GSTR-9, GSTR-9C, CMP-08, GSTR-4, TDS payment and return, EPF, ESI, Professional Tax (Karnataka only for now), advance tax, tax audit, income-tax returns (three variants), AGM, AOC-4, MGT-7, DPT-3, MSME Form 1, DIR-3 KYC, LLP Form 8 and 11, DPDP Act readiness.

### What it openly says it does not cover yet
Professional Tax in other states, Shops and Establishment renewal, Labour Welfare Fund, ADT-1, One Person Company filings, licences like FSSAI and fire (upload the certificate in Documents and its expiry lands here), TCS returns and e-invoicing.

---

## 8. Documents: "Ask your own papers"

### What it is for
A ChatGPT-style chat, but it only answers from the documents your company uploaded, and every sentence has a numbered citation you can click to see the exact passage.

### How you use it
1. Click **Documents**. In the middle: "What do you want to know?" and a chat box. The round button at top right opens the **Library**: your documents grouped into **collections** (HR, Finance, Safety, Board, and so on) and your past chats.
2. **Add a document** (button in the Library). Pick or create a collection. The file is read, split into passages, indexed, and summarised. Scans and Hindi documents work. If the document has an expiry date (an insurance policy, a price list) it is detected and sent to the Compliance calendar.
3. Pick a **scope** from the small dropdown next to the chat box: "All documents" or one collection. Keeping the scope narrow gives sharper answers.
4. Ask in English, Hindi, or Hinglish. The answer streams in with **[1] [2]** chips. Click a chip: a panel opens showing the passage with the quoted words highlighted and a green tick "found word for word", or an amber question mark if the quote could not be matched. A **Confidence %** at the bottom of each answer is the share of quotes that were verified.
5. Ask follow-ups in the same chat. Rename or delete chats from the Library.

### Three kinds of question it understands
- **Lookup**: "How many casual leaves do I get?" (searches and quotes)
- **Overview**: "Summarise the leave policy" or "What documents do I have?" (answers from the document profiles)
- **Chit-chat**: "Hi, what can you do?" (answered with no AI call)

### Pre-loaded documents and good questions
| Document | Collection | Ask |
|---|---|---|
| Leave and attendance policy (14) | HR | How many days of earned leave can I carry forward? What happens on my 4th late mark in a month? |
| Supplier onboarding SOP (15) | Finance | Who must approve a purchase order of Rs 12 lakh? What is the payment term for an MSME vendor? |
| Factory safety manual, in Hindi (16) | Safety | `accident report kitne ghante ke andar karna hai?` (answer: 24 ghante) Fire drill kitni baar hoti hai? |
| Price list FY 2026-27 (17) | Sales | What is the price and MOQ of the 6205-2RS bearing? Until when is this price list valid? |
| Board resolution on bank authority (18) | Board | Who is authorised to sign cheques and up to what amount? Can one director alone sign a Rs 8 lakh payment? |
| Insurance policy schedule (19) | Finance | When does the policy expire? Within how many hours must a loss be reported? Is earthquake fire covered? |

---

## 9. Settings

Opens as a pop-up with three sections. **Company** shows the profile. **System** shows four traffic lights: Database, Document search, AI analysis (with the model name), and GST registry lookups ("Live" or "Offline checks only"). **Account** shows who is signed in. If something in a demo is not working, this is the first place to look.

---

## 10. The one thing to remember

LegalOS is **not a lawyer** and says so on screen. It is decision support. Every finding carries a quote, every deadline carries a source, every reply needs a lawyer's tick before it is final. What it saves you is the first two hours of reading, searching and panicking, so that the one hour you do buy from a lawyer is spent on the real question.
