# LegalOS → Compliance Command Center
## Complete Product Transformation Plan

> **Prepared for:** LegalOS Engineering & Product Team  
> **Scope:** Full productization — positioning, architecture, data model, roadmap, code agent instructions  
> **Date:** August 2026

---

## 1. PRODUCT REPOSITIONING

### New Positioning Statement

> **"LegalOS is India's Compliance Command Center for SMEs — so you never miss a deadline, never lose a document, and never let compliance chaos slow your business."**

Secondary: *"We replace your CA's reminder WhatsApp, your Excel tracker, and your filing panic — with one system that owns your compliance calendar, assigns tasks, chases evidence, and closes the loop."*

---

### Ideal Customer Profile (ICP)

| Dimension | Profile |
|-----------|---------|
| **Company size** | 10–200 employees |
| **Geography** | India (Tier 1 + Tier 2 cities) |
| **Entity type** | Private Limited, LLP, Partnership |
| **Annual revenue** | ₹1 Cr – ₹100 Cr |
| **Pain signal** | Uses a CA retainer but manages compliance tasks via WhatsApp + Excel |
| **Tech readiness** | Uses Tally / Zoho Books / basic cloud tools; not ready for enterprise GRC |
| **Buying trigger** | Penalty received, audit failed, compliance officer hired, new investor scrutiny |

---

### Top 3 Buyer Personas

#### Persona 1: The Founder / Business Owner (Primary Buyer)
- **Name archetype:** Rajesh Kumar, 38, MD of a Pune-based trading + manufacturing company
- **Role:** Decision-maker, approves tools, pays the bill
- **Pain points:**
  - Gets GST penalty notices and discovers them late
  - CA doesn't proactively tell him what's due — only responds
  - Has no visibility into what his team has filed vs. not filed
  - Terrified of income tax, MCA, and GST audits
  - Cannot delegate compliance with confidence — no tracking
- **What they buy:** Peace of mind + a single place to see "are we compliant today?"
- **Willingness to pay:** ₹3,000–8,000/month if it replaces CA panic calls

#### Persona 2: The In-House CA / Compliance Manager (Primary User)
- **Name archetype:** Anjali Sharma, 32, Company Secretary / Compliance Officer
- **Role:** Primary user, manages daily filings, owns task execution
- **Pain points:**
  - Tracks 30–50 deadlines across GST, TDS, ROC, PF, ESI in separate spreadsheets
  - Has to manually remind operational teams to collect invoices, TDS certificates, challans
  - Evidence collection for audits is chaotic — documents scattered in email and Drive
  - No automated reminder system — relies on personal calendar alerts
  - Cannot generate a clean compliance status report for management
- **What they buy:** Workflow reduction — stop chasing people, start tracking outcomes
- **Willingness to pay:** Would advocate internally if it saves 10+ hours/month

#### Persona 3: The External CA / Chartered Accountant (Channel Partner)
- **Name archetype:** Vikram Mehta, 45, CA managing 20–50 SME clients
- **Role:** Advisor, sometimes decision-influencer
- **Pain points:**
  - Each client has different deadlines, different docs, different urgency
  - Clients blame the CA when something is missed — even if the CA sent reminders
  - Cannot offer premium compliance management service — no tool to operationalize it
  - Spends time on low-value reminders instead of advisory
- **What they buy:** A white-label or multi-client dashboard to manage their client portfolio
- **Willingness to pay:** ₹1,500–3,000/client/month as a managed service uplift

---

### Why the Current Product Is Hard to Sell

| Problem | Root Cause |
|---------|-----------|
| **No retention hook** | After upload + AI analysis, the session is over. There's no reason to return tomorrow. |
| **No workflow state** | Tasks exist but have no owner, no reminder, no escalation, no proof. A task that's "pending" forever is useless. |
| **AI output ≠ action** | Extracting expiry dates and creating tasks is not the same as ensuring those tasks get closed. |
| **No accountability loop** | Nobody is responsible for any task. No concept of "assigned to", "overdue", "escalated". |
| **No deadline anxiety** | The product doesn't tell you what's on fire today. No urgency signal. |
| **Feels like a utility, not a system** | Users use it once for a specific document. There's no daily reason to open the app. |
| **Mock auth kills credibility** | When demoing to a real customer, the auth switcher looks like a prototype. |
| **No proof of closure** | Completing a task requires no evidence. A ticked checkbox is worthless in an audit. |

---

### The Narrow MVP Wedge to Sell First

**Sell "Compliance Operations Management" — specifically the GSTIN onboarding → calendar → reminder → closure loop.**

The wedge story: *"Enter your GSTIN. We create your full compliance calendar — every GST, TDS, MCA, PF/ESI deadline for the year. Assign each task to someone. They get automatic reminders. When they complete it, they upload proof. You have an audit-ready trail."*

This is the wedge because:
1. You already have GSTIN onboarding + calendar generation — it works
2. Every Indian SME has this pain — universal, no niche discovery needed
3. The loop (calendar → assign → remind → evidence → close) is the product moat
4. Every competitor (Excel, CA, WhatsApp) fails at the "close + proof" step

---

## 2. SELLABLE MVP DEFINITION

### What to KEEP (Already Exists, Directly Useful)

| Feature | Keep As-Is | Why |
|---------|-----------|-----|
| GSTIN-based calendar initialization | ✅ | The core onboarding hook — already works |
| AI extraction from compliance documents | ✅ | Creates tasks from certificates — powerful |
| Task CRUD (create/update/delete) | ✅ | Base layer for all operations |
| Vendor GSTIN verification | ✅ | Useful for vendor onboarding flow later |
| Document parser (PDF/DOCX/TXT) | ✅ | Core infra for all document workflows |
| RAG pipeline for contracts | ✅ (deprioritize for MVP) | Valuable but not core to compliance wedge |
| Legal Notice Center | ✅ (deprioritize for MVP) | Useful but secondary |

---

### What to REMOVE from MVP Scope

| Feature | Remove Reason |
|---------|--------------|
| Contract negotiation suggestions | Not compliance-critical. Distraction in sales story. |
| Legal notice reply drafting | Secondary workflow — not in compliance command center narrative |
| Knowledge Hub (RAG Q&A) | Planned feature, zero infrastructure ready |
| Local LLM provider (Ollama) | Development shortcut — not needed in MVP demo |
| Three-way mock auth role switcher | Embarrassing in demos. Replace with basic real auth. |

---

### What to DEPRIORITIZE (Build Later)

- Multi-entity / multi-org support
- Calendar export (Google Calendar / Outlook sync)
- White-label CA portal
- MCA API integration
- Tally / Zoho Books integration
- Court and regulatory API connectors
- Fine-tuned LLM

---

### What to ADD IMMEDIATELY (Builds the Wedge)

| Feature | Why It Unlocks Sales |
|---------|---------------------|
| **Task Assignment** | Gives accountability — "who owns this?" |
| **Reminder Engine** | Email reminders before due dates — first operational value |
| **Overdue Detection** | Real-time "what's on fire" signal — creates urgency |
| **Evidence Upload per Task** | Turns task completion into proof — audit-ready |
| **Task Closure Verification** | Cannot close a task without proof — enforces discipline |
| **Compliance Health Dashboard** | Single screen: % tasks done, # overdue, upcoming in 7/30 days |
| **Real Auth (JWT + email/password)** | Makes it a real product, not a prototype |
| **Org/Tenant Isolation** | Required for any multi-user or paid account |
| **Activity Log per Task** | Audit trail — "who did what when" |

---

### What Should Be Premium / Later Tier

- Escalation engine (auto-notify manager if task is overdue)
- AI-powered obligation extraction from contracts
- Multi-entity / subsidiary management
- White-label for CA firms
- Bulk CSV upload for obligation imports
- Public compliance badge / trust center
- MCA / GST portal live sync

---

## 3. FEATURE ARCHITECTURE

### Layer 1: Obligation Register

**Purpose:** Single authoritative list of all compliance obligations the organization must meet — statutory (auto-generated) and custom (manually added).

**Business Value:** Replaces the scattered spreadsheet, WhatsApp message, and CA email as the source of truth for "what do we have to do."

**User Flow:**
1. GSTIN onboarding → system creates statutory obligations automatically
2. Compliance officer can also add custom obligations (e.g., "Renew FSSAI license by March 31")
3. Each obligation has: name, category (GST/TDS/MCA/Labour/License), frequency (monthly/quarterly/annual/one-time), applicable entity, penalty description

**Backend Changes:**
- New `obligations` table replacing the flat task list
- Obligation ↔ Task relationship (1:N) — one obligation generates recurring task instances
- `ObligationService`: CRUD + auto-generation rules

**Frontend Changes:**
- New `/obligations` page listing all obligations by category
- Add/edit obligation modal
- Obligation detail page showing all task instances

**Data Model Changes:**
```sql
obligations (
  id UUID PK,
  org_id UUID FK,
  title VARCHAR,
  category ENUM(gst, tds, mca, pf_esi, income_tax, labour, license, custom),
  frequency ENUM(monthly, quarterly, annual, one_time),
  next_due_date DATE,
  penalty_description TEXT,
  is_active BOOLEAN,
  source ENUM(statutory, document_extracted, manual),
  created_at, updated_at
)
```

**Automation Logic:**
- GSTIN init → bulk insert statutory obligations based on entity type
- Document upload → AI extracts obligations → insert with source=`document_extracted`
- Nightly job: for recurring obligations, generate next `ComplianceTask` when due date is within `N` days

**Priority:** P0

---

### Layer 2: Compliance Calendar

**Purpose:** Time-based view of all compliance tasks — what's due this week, this month, this quarter.

**Business Value:** The core daily-use screen. Makes the product sticky — users open it every Monday morning.

**User Flow:**
1. User sees month-view calendar with task dots
2. Clicking a date shows tasks due
3. Color coding: green (done), amber (due soon), red (overdue)
4. Filter by category (GST / TDS / MCA) or assignee

**Backend Changes:**
- `GET /api/v1/compliance/calendar?month=2026-08&org_id=...` endpoint
- Returns tasks grouped by date + status
- Efficient date-range query with index on `due_date`

**Frontend Changes:**
- Replace current flat task list with a proper calendar component
- Month navigation, week strip view for quick access
- "Today" button
- Task count badges per day
- Quick-complete action from calendar cell

**Data Model Changes:**
- Tasks table gets `due_date` indexed column (already exists, needs index)
- Add `is_overdue` computed field or materialized query

**Automation Logic:**
- Nightly APScheduler job: mark tasks past due_date with `status=overdue` if not completed

**Priority:** P0

---

### Layer 3: Document Expiry / Renewal Tracking

**Purpose:** Track all compliance certificates, licenses, and registrations by their expiry dates and auto-trigger renewal workflows.

**Business Value:** This is a direct revenue event. License expiry = business risk. Customers pay to never miss this.

**User Flow:**
1. User uploads FSSAI, GST Registration, Trade License, PF Registration, ISO certificate etc.
2. AI extracts: document type, issuing authority, issue date, expiry date, identifier number
3. System creates an obligation with frequency=`annual` and due date = `expiry_date - 60 days`
4. 60/30/15/7 day reminders fire automatically
5. User sees "Expiring Soon" widget on dashboard

**Backend Changes:**
- Enhance `ComplianceDocumentAnalysis` to store `expiry_date` prominently
- `DocumentExpiryService`: query documents by expiry_date ranges
- Link analysis → obligation → tasks (currently missing)

**Frontend Changes:**
- "Expiry Tracker" section on dashboard (separate from task calendar)
- Red/amber/green expiry indicators
- "Renew" CTA button that opens a renewal workflow

**Data Model Changes:**
```sql
compliance_documents (
  id UUID PK,
  org_id UUID FK,
  document_id UUID FK → core.documents,
  analysis_id UUID FK → compliance_document_analyses,
  document_type VARCHAR,
  identifier_number VARCHAR,
  issuing_authority VARCHAR,
  issue_date DATE,
  expiry_date DATE,
  renewal_status ENUM(valid, expiring_soon, expired, renewal_initiated),
  linked_obligation_id UUID FK → obligations,
  created_at, updated_at
)
```

**Automation Logic:**
- After AI analysis: if `expiry_date` extracted → create/update `compliance_document` record
- Nightly job: for each document where `expiry_date - today <= 60 days` AND `renewal_status != renewal_initiated` → create renewal task → send reminder

**Priority:** P0

---

### Layer 4: Task Ownership

**Purpose:** Every compliance task has exactly one assigned owner who is accountable for completing it.

**Business Value:** Removes the "everyone's problem = nobody's problem" failure mode. The single most important operational feature.

**User Flow:**
1. Task created (auto or manual) → system prompts for assignee or uses default org owner
2. Assignee receives email notification: "You have been assigned: GSTR-1 Filing — due Oct 11"
3. Task list shows each user their own tasks
4. Admin sees all tasks with assignees and status

**Backend Changes:**
- `task_assignments` table or `assigned_to_user_id` FK on compliance_tasks
- `GET /api/v1/compliance/tasks?assigned_to=me` filter
- `PATCH /api/v1/compliance/tasks/{id}/assign` endpoint

**Frontend Changes:**
- User avatar / name pill on each task card
- "Assign to" dropdown on task detail page
- My Tasks vs. All Tasks toggle
- "Unassigned" tasks highlighted in red

**Data Model Changes:**
```sql
ALTER TABLE compliance_center.compliance_tasks
  ADD COLUMN assigned_to_user_id UUID REFERENCES core.users(id),
  ADD COLUMN assigned_at TIMESTAMP,
  ADD COLUMN assigned_by_user_id UUID REFERENCES core.users(id);
```

**Automation Logic:**
- On assignment → send email to assignee
- If task is 3 days overdue and assigned → escalate to org owner

**Priority:** P0

---

### Layer 5: Reminder Engine

**Purpose:** Automated, time-based email reminders sent to task owners before deadlines.

**Business Value:** This is the #1 feature customers will describe as "why I pay for this." It removes the CA's manual WhatsApp reminders.

**User Flow:**
1. System sends reminders at: 30 days, 15 days, 7 days, 3 days, 1 day before due date
2. Reminder email: task name, due date, one-click link to mark complete or upload proof
3. User clicks link → goes to task detail page
4. If no action → escalation fires

**Backend Changes:**
- `reminders` table tracking what was sent and when
- APScheduler daily job: query tasks due in 1/3/7/15/30 days → check reminder history → send if not sent
- Email service: SendGrid / SMTP integration (new `shared/notifications/email_service.py`)
- Reminder job: `backend/app/workers/reminder_worker.py`

**Frontend Changes:**
- Reminder settings page: configure N-day intervals per org
- Notification center: inbox of all reminders sent/pending
- Email templates: HTML email with task summary + deep link

**Data Model Changes:**
```sql
reminders (
  id UUID PK,
  task_id UUID FK → compliance_tasks,
  user_id UUID FK → core.users,
  reminder_type ENUM(email, in_app),
  days_before_due INT,
  sent_at TIMESTAMP,
  status ENUM(sent, failed, skipped)
)
```

**Automation Logic:**
- Nightly APScheduler: `SELECT tasks WHERE due_date = today + N AND status != completed`
- For each → check `reminders` table (avoid duplicates) → send email → log to reminders
- Idempotent: if job fails and re-runs, duplicate check prevents double-send

**Priority:** P0

---

### Layer 6: Escalation Engine

**Purpose:** When a task owner has not acted after repeated reminders, escalate to the org owner or manager.

**Business Value:** Closes the accountability gap. Makes the product self-enforcing. Customers love that it removes the awkward "did you file yet?" conversation.

**User Flow:**
1. Task is 3 days overdue + owner has been reminded → system emails org owner
2. Escalation email: "Action Required: GSTR-1 Filing for [Company] is 3 days overdue. Assigned to: Anjali Sharma."
3. Org owner can reassign the task or mark it urgent
4. Escalation is logged in activity log

**Backend Changes:**
- `escalations` table
- Escalation job checks: `tasks WHERE status=overdue AND last_reminder_sent > 3 days AND no escalation sent`
- `POST /api/v1/compliance/tasks/{id}/escalate` (manual trigger)

**Frontend Changes:**
- Escalation badge on task cards
- Admin dashboard: "Escalated Tasks" section
- Escalation history on task detail page

**Data Model Changes:**
```sql
escalations (
  id UUID PK,
  task_id UUID FK,
  escalated_from_user_id UUID FK,
  escalated_to_user_id UUID FK,
  reason TEXT,
  escalated_at TIMESTAMP,
  resolved_at TIMESTAMP,
  resolved_by UUID FK
)
```

**Automation Logic:**
- Daily job: find overdue tasks with >= 2 unacknowledged reminders → insert escalation → notify org owner
- On task completion after escalation → mark escalation resolved

**Priority:** P1

---

### Layer 7: Evidence Vault

**Purpose:** Each compliance task requires proof of completion — a challan, filing acknowledgment, certificate, receipt.

**Business Value:** This is the feature that makes audits survivable. Without proof, closure means nothing. With proof, every task has a document behind it.

**User Flow:**
1. User marks task as "completed"
2. System prompts: "Upload proof of completion (challan, acknowledgment, screenshot)"
3. User uploads file → stored in org-scoped evidence folder
4. Task moves to `closed` state (not just `completed`) only after proof
5. Proof visible on task detail page and downloadable

**Backend Changes:**
- `evidence_documents` table
- `POST /api/v1/compliance/tasks/{id}/evidence` — upload + link
- `GET /api/v1/compliance/tasks/{id}/evidence` — list evidence for task
- File storage: upgrade to S3/MinIO with org-scoped prefix

**Frontend Changes:**
- Proof upload UI on task completion modal
- Evidence thumbnail / file list on task detail
- "Download all evidence" for a period (for CA export)
- Evidence vault page: all uploaded proofs in one place

**Data Model Changes:**
```sql
evidence_documents (
  id UUID PK,
  task_id UUID FK → compliance_tasks,
  org_id UUID FK,
  document_id UUID FK → core.documents,
  storage_path VARCHAR,
  uploaded_by UUID FK → core.users,
  uploaded_at TIMESTAMP,
  file_type VARCHAR,
  notes TEXT
)
```

**Automation Logic:**
- On evidence upload → auto-move task to `pending_review` status
- Reviewer approves → task moves to `closed`
- If reviewer is same as owner → auto-close (small org mode)

**Priority:** P0

---

### Layer 8: Closure Verification

**Purpose:** Formalize task completion with a two-step process: completion + proof = closure.

**Business Value:** Distinguishes between "I said I filed it" and "I can prove I filed it." Audit-grade compliance requires the latter.

**User Flow:**
1. Owner marks task `completed` + uploads evidence
2. If reviewer role configured: reviewer notified → reviews evidence → marks `approved` → task moves to `closed`
3. If single-user mode: upload proof → task auto-closes
4. Closed tasks are immutable (cannot be edited)

**Backend Changes:**
- Task status state machine: `pending → in_progress → completed → pending_review → closed | reopened`
- `POST /api/v1/compliance/tasks/{id}/verify` — reviewer action
- State transitions enforced in service layer

**Frontend Changes:**
- Task status badge with clear state labels
- "Request review" button (sends to reviewer)
- Reviewer inbox: tasks awaiting verification
- "Close task" button only visible to reviewer or admin

**Data Model Changes:**
```sql
ALTER TABLE compliance_center.compliance_tasks
  ADD COLUMN status ENUM('pending','in_progress','completed','pending_review','closed','reopened','overdue'),
  ADD COLUMN closed_at TIMESTAMP,
  ADD COLUMN closed_by UUID FK,
  ADD COLUMN verification_notes TEXT;
```

**Automation Logic:**
- On status=`closed`: lock task, generate closure record in activity log
- On status=`reopened`: notify assignee + log reason

**Priority:** P1

---

### Layer 9: Audit Trail

**Purpose:** Immutable, timestamped log of every action on every task — who created it, who was assigned, what changed, who uploaded proof, who closed it.

**Business Value:** The one thing regulators, auditors, and investors want to see. Makes every compliance action defensible.

**User Flow:**
1. Every task action is logged automatically (no user action required)
2. Task detail page shows activity timeline: "Aug 1: Created. Aug 2: Assigned to Anjali. Aug 5: Reminder sent. Aug 10: Evidence uploaded. Aug 10: Closed by Vikram."
3. Org admin can export full audit trail for a period as PDF/CSV

**Backend Changes:**
- `activity_logs` table (append-only, never updated)
- `ActivityLogService`: `log_event(org_id, entity_type, entity_id, user_id, action, metadata)`
- Call `log_event()` from every service action (task create, assign, complete, evidence upload, close, escalate)

**Frontend Changes:**
- Activity timeline component on task detail page
- Org-level activity log page with filters
- "Export audit trail" button (CSV / PDF)

**Data Model Changes:**
```sql
activity_logs (
  id UUID PK,
  org_id UUID FK,
  entity_type VARCHAR (e.g., "compliance_task", "obligation"),
  entity_id UUID,
  user_id UUID FK,
  action VARCHAR (e.g., "task.created", "task.assigned", "evidence.uploaded"),
  metadata JSONB,
  created_at TIMESTAMP -- NEVER NULL, indexed
)
```

**Automation Logic:**
- Middleware / service hook: every state change triggers `log_event()`
- Log is write-only — no delete, no update endpoints

**Priority:** P1

---

### Layer 10: Dashboard / Risk Reporting

**Purpose:** Single-screen overview of compliance health — today's fires, upcoming deadlines, overdue tasks, completion rate.

**Business Value:** The "control room" feel that makes the product feel premium. Founder/owner's primary view.

**User Flow:**
1. Default landing page after login
2. Shows: compliance score (% tasks closed on time), tasks due today/this week, overdue count, expiring documents, recent activity
3. Category breakdown: GST health / TDS health / MCA health / Labour health
4. CTA buttons: "View overdue", "Assign unassigned tasks", "Upload pending evidence"

**Backend Changes:**
- `GET /api/v1/dashboard/summary` endpoint
- Aggregates: task counts by status, overdue count, expiry alerts, category-wise health %
- Efficient: single optimized query with GROUP BY

**Frontend Changes:**
- Dashboard page as default route (`/dashboard`)
- Metric cards: Compliance Score, Overdue Tasks, Due This Week, Expiring Soon
- Category health grid (GST / TDS / MCA / PF-ESI / Other)
- Recent activity feed
- "What needs your attention now" priority list

**Data Model Changes:**
- No new tables — calculated from existing task + document data
- Consider materialized view for performance at scale

**Automation Logic:**
- Dashboard data is real-time (on-demand query, not cached for MVP)
- Weekly compliance digest email: sent every Monday morning

**Priority:** P0

---

## 4. GAP ANALYSIS VS CURRENT SYSTEM

| Current Capability | Current Limitation | Why It Hurts Sales | Fix Required |
|-------------------|-------------------|-------------------|-------------|
| GSTIN-based task generation | Generates static flat task list with no owner, no reminder, no escalation | "This is just a calendar I could build in Excel in 30 minutes" | Add task ownership, reminders, escalation engine |
| Compliance task CRUD | Tasks can be manually created/updated/deleted but have no state machine | A task marked "done" has no proof, no closure verification, no trail | Implement status state machine + evidence upload |
| Document analysis (AI extraction) | AI extracts expiry dates + creates tasks, but document → obligation → task link is broken | "The AI found the expiry date but didn't actually do anything about it" | Link analysis → obligation → task → reminders |
| Role system | Purely mocked (header-based switcher) | Cannot demo to real customers without explaining "this is fake auth" | Implement real JWT auth + org model |
| No multi-tenancy | User IDs are hardcoded seeds | One demo wipes another's data | Add org model with tenant isolation |
| File storage (local disk) | Files stored in `/uploads/` on container disk | Files lost on container restart. Cannot use in cloud/production | Migrate to S3-compatible (MinIO for dev, S3 for prod) |
| Background tasks (FastAPI BackgroundTasks) | In-process — if server restarts, in-flight jobs are lost | Analysis tasks can silently fail with no retry | Migrate to Celery + Redis for reliability |
| No notification system | Zero email/SMS/WhatsApp delivery | Product cannot operationally remind anyone | Build email service (SendGrid) first |
| No audit trail | Activity is not logged | Compliance without audit trail is worthless to regulators/auditors | Implement append-only activity_logs |
| No dashboard | No home screen — users land on contract list | No daily engagement hook, no "what's urgent" signal | Build compliance health dashboard as default route |
| Contract Intelligence | Full RAG pipeline, clause risk scoring, negotiation suggestions | Good feature but wrong wedge — distracts from compliance story | Keep but deprioritize in sales narrative for MVP |
| Vendor GSTIN verification | Verifies + logs audit trail | Single-lookup utility — not sticky | Embed into vendor onboarding workflow, not standalone |

---

## 5. AUTOMATION BLUEPRINT

### Flow 1: GSTIN Onboarding → Compliance Calendar

**Trigger:** User submits GSTIN on onboarding screen

**System Actions:**
1. Lookup GSTIN via Sandbox.co.in API → extract company_name, entity type (ctb)
2. Create `Organization` record (or update existing)
3. Resolve entity type → obligation rules set (GST, TDS, MCA, PF/ESI based on ctb)
4. Bulk insert `Obligation` records (statutory)
5. For each obligation: create first `ComplianceTask` instance for current FY
6. For recurring obligations: schedule next task generation via `RecurringSchedule`
7. Send welcome email to org owner: "Your compliance calendar is ready"

**Human Actions Still Required:** None — fully automated

**Failure Cases:**
- GSTIN lookup fails (API down) → fall back to manual entity type selection → queue re-fetch when API available
- Duplicate GSTIN → check by gstin field → return existing org record

**Fallback Behavior:** Mock mode enabled → use pre-defined GSTIN fixture → system functional without live API

---

### Flow 2: Document Upload → Extract Obligations → Create/Update Tasks

**Trigger:** User uploads compliance certificate (FSSAI, Trade License, GST Registration, PF Registration)

**System Actions:**
1. Save file → insert `core.documents` record
2. Background job: parse document → call Gemini with `COMPLIANCE_DOCUMENT_ANALYSIS_SYSTEM` prompt
3. Extract: `authority`, `document_type`, `identifier_number`, `issue_date`, `expiry_date`, `action_items[]`
4. Insert `ComplianceDocumentAnalysis` record
5. If `expiry_date` extracted → create/update `ComplianceDocument` with `expiry_date`
6. Find matching `Obligation` (by document_type) or create new one
7. Create `ComplianceTask`: "Renew [document_type] before [expiry_date - 45 days]"
8. Link task to obligation and source document
9. Notify org owner: "Document uploaded. Renewal task created for [date]."

**Human Actions Still Required:** Upload the document (still manual)

**Failure Cases:**
- AI extraction fails or returns partial data → mark analysis status=`warning` → notify user to review manually
- Expiry date not found in document → task created without date → flagged for manual date entry
- Duplicate document (same identifier_number) → warn user, ask to confirm replacement

**Fallback Behavior:** Analysis falls back to display raw extracted text with a note: "Manual review required"

---

### Flow 3: Upcoming Due Date → Send Reminders

**Trigger:** APScheduler job runs daily at 08:00 IST

**System Actions:**
1. Query all `ComplianceTask` WHERE `status NOT IN ('closed', 'cancelled')` AND `due_date IN (today+1, today+3, today+7, today+15, today+30)`
2. For each task: check `reminders` table — has this reminder interval already been sent?
3. If not sent: build email body (task name, due date, assignee, link to task)
4. Send via `EmailService.send()` (SendGrid)
5. Insert `Reminder` record: `(task_id, user_id, days_before_due, sent_at, status=sent)`
6. If send fails: insert `Reminder` with `status=failed` → retry next day

**Human Actions Still Required:** User must act on the task (file, pay, upload)

**Failure Cases:**
- Email delivery failure → log + retry once
- Task already completed before reminder fires → check status before send → skip if closed

**Fallback Behavior:** Log reminder as `skipped` with reason — never silently lose a reminder

---

### Flow 4: No Owner Action → Escalate

**Trigger:** APScheduler job runs daily at 09:00 IST

**System Actions:**
1. Query `ComplianceTask` WHERE `status=overdue` AND `assigned_to IS NOT NULL`
2. Check `escalations` table — has escalation already been sent for this task?
3. Check `reminders` — has at least 2 reminders been sent?
4. If conditions met: insert `Escalation` record
5. Send escalation email to org owner / manager: task name, assignee name, days overdue
6. In-app notification to org owner

**Human Actions Still Required:** Org owner must investigate + reassign or override

**Failure Cases:**
- No org owner configured → escalate to all admin users
- Escalation sent but task still open after 7 more days → re-escalate (max 3x)

**Fallback Behavior:** After 3 escalations with no action → task flagged as `critical` in dashboard

---

### Flow 5: Task Completion → Request Proof

**Trigger:** User clicks "Mark Complete" on a task

**System Actions:**
1. Validate: task status must be `pending` or `in_progress`
2. Show "Upload Proof" modal (blocking — cannot close without action)
3. If file uploaded: store in evidence vault → change status to `pending_review`
4. If user clicks "Skip Proof": status changes to `completed_no_evidence` (highlighted in amber — not fully closed)
5. Notify reviewer (if configured): "Task ready for review: [task name]"
6. Log action in `activity_logs`

**Human Actions Still Required:** User must upload actual proof file

**Failure Cases:**
- File too large → reject with error message
- Wrong file type → accept only PDF/DOCX/IMG
- User abandons modal → task stays in previous state

**Fallback Behavior:** `completed_no_evidence` state is visible and tracked — cannot be used as audit evidence

---

### Flow 6: Proof Uploaded → Validate and Close

**Trigger:** Evidence file uploaded AND reviewer assigned

**System Actions:**
1. Notify reviewer via email + in-app: "Evidence uploaded for [task] — please verify"
2. Reviewer opens task → sees uploaded proof
3. Reviewer clicks "Approve & Close" → task status = `closed`, closed_at = now()
4. Reviewer clicks "Reject" → task status = `pending`, comment added, assignee notified
5. In single-user mode (no reviewer): evidence upload auto-closes task
6. Log closure in `activity_logs`

**Human Actions Still Required:** Reviewer must visually verify the document

**Failure Cases:**
- Reviewer account not configured → auto-close on upload
- Reviewer rejects without comment → validation error (comment required)

**Fallback Behavior:** Tasks with evidence but no reviewer are flagged as `auto_closed` — auditable but noted

---

### Flow 7: Expiring License / Certificate → Auto-Open Renewal Workflow

**Trigger:** Nightly job finds document WHERE `expiry_date - today <= 60 days` AND `renewal_status != renewal_initiated`

**System Actions:**
1. Set `compliance_document.renewal_status = expiring_soon`
2. Create `ComplianceTask`: "Renew [document_type] — expires [expiry_date]"
3. Assign to default owner (org owner or compliance manager)
4. Schedule 45-day, 30-day, 15-day, 7-day reminders for this task
5. Send notification to org owner: "License expiry alert: [document name] expires in 60 days"
6. Dashboard widget: add to "Expiring Soon" section

**Human Actions Still Required:** Contact authority, prepare renewal documents, submit application, upload new certificate

**Failure Cases:**
- Document already renewed (new cert uploaded) → detect duplicate identifier → mark old as `renewed`
- `expiry_date` was extracted incorrectly → allow manual edit + reprocess

**Fallback Behavior:** If renewal task already exists for same obligation → update due date instead of creating duplicate

---

## 6. DATA MODEL UPGRADE

### New/Updated Entities

---

#### `core.organizations`
**Purpose:** Multi-tenant container. Every user, task, document belongs to an org.

| Field | Type | Notes |
|-------|------|-------|
| id | UUID PK | |
| name | VARCHAR | Legal company name |
| gstin | VARCHAR(15) | Primary GSTIN |
| entity_type | ENUM | private_limited, llp, partnership, sole_prop |
| onboarded_at | TIMESTAMP | When GSTIN init ran |
| plan | ENUM | free, starter, pro |
| plan_expires_at | TIMESTAMP | For paid plan enforcement |
| owner_user_id | UUID FK → users | |
| created_at, updated_at | TIMESTAMP | |

**Migration Notes:** Add `org_id` FK to users, documents, tasks, obligations. Use `DEFAULT <seed_org_uuid>` for existing data.

---

#### `core.users` (Updated)
**Purpose:** Real users with auth, belonging to an org.

**New Fields:**
```sql
ALTER TABLE core.users ADD COLUMN
  org_id UUID REFERENCES core.organizations(id),
  email VARCHAR UNIQUE NOT NULL,
  password_hash VARCHAR,  -- bcrypt
  is_active BOOLEAN DEFAULT TRUE,
  last_login_at TIMESTAMP,
  email_verified BOOLEAN DEFAULT FALSE;
```

**Migration Notes:** Seed users get a default org_id. Existing mock users need email assigned.

---

#### `compliance_center.obligations`
**Purpose:** The "what must we do" registry. Parent of recurring tasks.

| Field | Type | Notes |
|-------|------|-------|
| id | UUID PK | |
| org_id | UUID FK | |
| title | VARCHAR | "GSTR-1 Monthly Filing" |
| category | ENUM | gst, tds, mca, pf_esi, income_tax, labour, license, custom |
| frequency | ENUM | monthly, quarterly, annual, one_time |
| month_of_year | INT | For annual: which month (1-12) |
| day_of_month | INT | e.g., 11 for GSTR-1 |
| description | TEXT | Regulatory context |
| penalty_description | TEXT | What happens if missed |
| is_active | BOOLEAN | |
| source | ENUM | statutory, document_extracted, manual |
| document_analysis_id | UUID FK | If extracted from document |
| applicable_entity_types | TEXT[] | ["private_limited", "llp"] |
| created_at, updated_at | TIMESTAMP | |

**Relations:** `obligations` 1:N → `compliance_tasks`

---

#### `compliance_center.compliance_tasks` (Updated)
**Purpose:** Individual task instances. Existing table enhanced.

**New/Updated Fields:**
```sql
ALTER TABLE compliance_center.compliance_tasks ADD COLUMN
  org_id UUID REFERENCES core.organizations(id),
  obligation_id UUID REFERENCES compliance_center.obligations(id),
  assigned_to_user_id UUID REFERENCES core.users(id),
  assigned_at TIMESTAMP,
  assigned_by_user_id UUID REFERENCES core.users(id),
  status VARCHAR DEFAULT 'pending',  -- Extend to state machine
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  closed_at TIMESTAMP,
  closed_by_user_id UUID REFERENCES core.users(id),
  verification_notes TEXT,
  priority ENUM DEFAULT 'medium',  -- low, medium, high, critical
  task_type ENUM DEFAULT 'statutory',  -- statutory, renewal, custom, escalated
  period_label VARCHAR;  -- "Aug 2026", "Q2 FY27"
```

**State Machine:**
```
pending → in_progress → completed → pending_review → closed
                     ↘ completed_no_evidence ↗
any state → overdue (set by nightly job)
closed → reopened → pending
```

---

#### `compliance_center.recurring_schedules`
**Purpose:** Controls when the next task instance is auto-generated for a recurring obligation.

| Field | Type | Notes |
|-------|------|-------|
| id | UUID PK | |
| obligation_id | UUID FK | |
| org_id | UUID FK | |
| frequency | ENUM | monthly, quarterly, annual |
| next_due_date | DATE | Next task generation date |
| last_generated_at | TIMESTAMP | |
| advance_days | INT DEFAULT 15 | Generate task N days before due |
| is_active | BOOLEAN | |

**Automation Logic:** Nightly job reads this table → generates tasks → updates `next_due_date`

---

#### `compliance_center.compliance_documents`
**Purpose:** Tracks physical documents (licenses, certificates) by expiry.

| Field | Type | Notes |
|-------|------|-------|
| id | UUID PK | |
| org_id | UUID FK | |
| document_id | UUID FK → core.documents | |
| analysis_id | UUID FK → compliance_document_analyses | |
| document_type | VARCHAR | "FSSAI License" |
| identifier_number | VARCHAR | License/Reg number |
| issuing_authority | VARCHAR | |
| issue_date | DATE | |
| expiry_date | DATE | INDEXED — used for expiry queries |
| renewal_status | ENUM | valid, expiring_soon, expired, renewal_initiated, renewed |
| linked_obligation_id | UUID FK | Auto-generated obligation |
| notes | TEXT | |
| created_at, updated_at | TIMESTAMP | |

---

#### `compliance_center.evidence_documents`
**Purpose:** Proof files uploaded when closing a task.

| Field | Type | Notes |
|-------|------|-------|
| id | UUID PK | |
| task_id | UUID FK → compliance_tasks | |
| org_id | UUID FK | |
| document_id | UUID FK → core.documents | |
| storage_path | VARCHAR | S3 key or local path |
| uploaded_by | UUID FK → core.users | |
| uploaded_at | TIMESTAMP | |
| file_type | VARCHAR | pdf, docx, jpeg, png |
| notes | TEXT | Uploader's notes |
| is_primary | BOOLEAN | Primary proof document |

---

#### `compliance_center.reminders`
**Purpose:** Tracks all reminders sent or scheduled.

| Field | Type | Notes |
|-------|------|-------|
| id | UUID PK | |
| task_id | UUID FK | |
| user_id | UUID FK | Who was reminded |
| org_id | UUID FK | |
| channel | ENUM | email, in_app, whatsapp |
| days_before_due | INT | 30, 15, 7, 3, 1 |
| scheduled_for | DATE | When this reminder should send |
| sent_at | TIMESTAMP | Null if not yet sent |
| status | ENUM | pending, sent, failed, skipped |
| error_message | TEXT | If failed |

**Index:** `(task_id, days_before_due)` — for deduplication check

---

#### `compliance_center.escalations`
**Purpose:** Tracks when and why a task was escalated.

| Field | Type | Notes |
|-------|------|-------|
| id | UUID PK | |
| task_id | UUID FK | |
| org_id | UUID FK | |
| escalated_from_user_id | UUID FK | Task owner |
| escalated_to_user_id | UUID FK | Manager/owner |
| escalation_level | INT DEFAULT 1 | 1,2,3 — increases with each unresolved escalation |
| reason | TEXT | "Task overdue by 3 days" |
| escalated_at | TIMESTAMP | |
| resolved_at | TIMESTAMP | |
| resolved_by | UUID FK | |
| resolution_notes | TEXT | |

---

#### `core.activity_logs`
**Purpose:** Append-only audit trail of all significant actions.

| Field | Type | Notes |
|-------|------|-------|
| id | UUID PK | |
| org_id | UUID FK | INDEXED |
| entity_type | VARCHAR | "compliance_task", "obligation", "compliance_document" |
| entity_id | UUID | INDEXED |
| user_id | UUID FK | Who performed the action (null for system) |
| action | VARCHAR | "task.created", "task.assigned", "evidence.uploaded", "task.closed", "task.escalated" |
| metadata | JSONB | Old value, new value, extra context |
| ip_address | INET | For security audit |
| created_at | TIMESTAMP NOT NULL | INDEXED — append-only |

**Critical Rule:** No UPDATE, no DELETE. Write-once. Create a DB-level trigger to block updates.

---

#### `core.notifications`
**Purpose:** In-app notification inbox for each user.

| Field | Type | Notes |
|-------|------|-------|
| id | UUID PK | |
| org_id | UUID FK | |
| user_id | UUID FK | Recipient |
| title | VARCHAR | Short notification text |
| body | TEXT | Full message |
| type | ENUM | reminder, escalation, assignment, expiry_alert, system |
| related_entity_type | VARCHAR | |
| related_entity_id | UUID | Deep link target |
| is_read | BOOLEAN DEFAULT FALSE | |
| created_at | TIMESTAMP | |
| read_at | TIMESTAMP | |

---

## 7. API AND MODULE PLAN

### New Endpoints to Add

#### Organization & Auth
```
POST   /api/v1/auth/register          — Create org + owner user
POST   /api/v1/auth/login             — Return JWT
POST   /api/v1/auth/refresh           — Refresh JWT
GET    /api/v1/org/me                 — Current org details
PATCH  /api/v1/org/me                 — Update org settings
POST   /api/v1/org/members/invite     — Invite team member
GET    /api/v1/org/members            — List org members
```

#### Dashboard
```
GET    /api/v1/dashboard/summary      — Compliance health summary
GET    /api/v1/dashboard/calendar     — Calendar view data (month)
GET    /api/v1/dashboard/expiry-alerts— Expiring documents list
```

#### Obligations
```
GET    /api/v1/obligations            — List all obligations
POST   /api/v1/obligations            — Create custom obligation
PATCH  /api/v1/obligations/{id}       — Update obligation
DELETE /api/v1/obligations/{id}       — Delete (soft delete)
GET    /api/v1/obligations/{id}/tasks — All task instances for obligation
```

#### Tasks (Enhanced)
```
GET    /api/v1/compliance/tasks       — List with filters (status, assignee, category, period)
PATCH  /api/v1/compliance/tasks/{id}/assign   — Assign to user
PATCH  /api/v1/compliance/tasks/{id}/start    — Mark in_progress
PATCH  /api/v1/compliance/tasks/{id}/complete — Mark completed (triggers proof request)
PATCH  /api/v1/compliance/tasks/{id}/close    — Reviewer closes (requires evidence)
PATCH  /api/v1/compliance/tasks/{id}/reopen   — Reopen a closed task
POST   /api/v1/compliance/tasks/{id}/escalate — Manual escalate
POST   /api/v1/compliance/tasks/{id}/evidence — Upload proof
GET    /api/v1/compliance/tasks/{id}/evidence — List evidence
GET    /api/v1/compliance/tasks/{id}/activity — Activity log for task
```

#### Reminders
```
GET    /api/v1/reminders              — List sent reminders (org-scoped)
PATCH  /api/v1/reminders/settings     — Configure reminder intervals per org
POST   /api/v1/reminders/{task_id}/send-now — Manual reminder trigger
```

#### Documents / Expiry
```
GET    /api/v1/compliance/documents          — List tracked documents
GET    /api/v1/compliance/documents/expiring — Documents expiring in N days
PATCH  /api/v1/compliance/documents/{id}     — Update expiry date (manual correction)
```

#### Notifications
```
GET    /api/v1/notifications          — User's notification inbox
PATCH  /api/v1/notifications/{id}/read — Mark as read
POST   /api/v1/notifications/mark-all-read
```

#### Audit Trail
```
GET    /api/v1/audit/logs             — Org-scoped activity log (paginated)
GET    /api/v1/audit/logs/export      — CSV export
GET    /api/v1/audit/task/{id}        — Full activity for specific task
```

---

### Service Responsibilities

```
backend/app/
├── shared/
│   ├── auth/
│   │   ├── auth_service.py          ← REPLACE: JWT issue/verify (python-jose)
│   │   └── jwt_utils.py             ← NEW: encode/decode helpers
│   ├── notifications/
│   │   ├── email_service.py         ← NEW: SendGrid/SMTP wrapper
│   │   ├── notification_service.py  ← NEW: create in-app notifications
│   │   └── templates/               ← NEW: Jinja2 HTML email templates
│   ├── storage/
│   │   └── file_storage.py          ← UPGRADE: add S3/MinIO backend
│   └── jobs/
│       ├── scheduler.py             ← NEW: APScheduler setup
│       ├── reminder_job.py          ← NEW: daily reminder dispatch
│       ├── escalation_job.py        ← NEW: daily escalation check
│       ├── expiry_job.py            ← NEW: document expiry detection
│       └── task_generation_job.py   ← NEW: recurring task instance creation
├── workspaces/
│   ├── compliance_center/
│   │   ├── obligation_service.py    ← NEW: obligation CRUD + generation
│   │   ├── task_service.py          ← REFACTOR: state machine + evidence
│   │   ├── evidence_service.py      ← NEW: evidence upload + linking
│   │   ├── reminder_service.py      ← NEW: reminder creation + tracking
│   │   ├── escalation_service.py    ← NEW: escalation logic
│   │   ├── calendar_service.py      ← NEW: calendar view queries
│   │   └── document_expiry_service.py ← NEW: expiry tracking
│   └── dashboard/                   ← NEW workspace
│       ├── router.py
│       └── service.py               ← aggregate health queries
```

---

### Background Job Requirements

| Job | Trigger | Description |
|-----|---------|-------------|
| `reminder_job` | Daily 08:00 IST | Find tasks due in 1/3/7/15/30 days → send emails |
| `escalation_job` | Daily 09:00 IST | Find overdue + reminded tasks → escalate |
| `expiry_job` | Daily 07:00 IST | Find expiring documents → create renewal tasks |
| `task_generation_job` | Daily 06:00 IST | Generate next task instances for recurring schedules |
| `overdue_marking_job` | Daily 00:01 IST | Mark tasks past due_date as overdue |
| `weekly_digest_job` | Monday 09:00 IST | Send compliance digest email to org owners |

**Scheduler:** Use `APScheduler` with `AsyncScheduler` + PostgreSQL job store for persistence.  
**For production:** Migrate to Celery + Redis (more reliable, retryable, distributed).

---

### Synchronous vs. Async Split

| Operation | Sync/Async | Reason |
|-----------|-----------|--------|
| GSTIN lookup | Async (background) | External API latency — don't block HTTP |
| Document upload | Sync (save file) + Async (AI analysis) | Current pattern works, keep it |
| Task CRUD | Sync | Simple DB operations |
| Email sending | Async (background job) | Never block HTTP on email |
| Reminder dispatch | Background job | Scheduled, not request-driven |
| Dashboard summary | Sync | Must be fast — optimize query |
| Evidence upload | Sync (file save) + Async (virus scan, future) | |

---

### Notification Service Architecture

```python
# shared/notifications/notification_service.py

class NotificationService:
    async def send_task_assigned(task: ComplianceTask, assignee: User): ...
    async def send_reminder(task: ComplianceTask, user: User, days_before: int): ...
    async def send_escalation(task: ComplianceTask, escalated_to: User): ...
    async def send_expiry_alert(doc: ComplianceDocument, owner: User): ...
    async def send_task_closed(task: ComplianceTask, reviewer: User): ...
    
    # Internal: creates in_app notification + dispatches email if opted in
    async def _dispatch(user_id, title, body, type, entity_type, entity_id): ...
```

**Channel Priority:** In-app (always) → Email (if email_notifications=True) → WhatsApp (Phase 2)

---

### Rules Engine for Compliance Deadlines

```python
# workspaces/compliance_center/rules_engine.py

STATUTORY_RULES = [
    ObligationRule(
        id="gstr1_monthly",
        title="GST GSTR-1 Monthly Filing",
        category="gst",
        frequency="monthly",
        day_of_month=11,  # 11th of following month
        applicable_entity_types=["all"],
        penalty_description="₹50/day late fee under Section 47"
    ),
    ObligationRule(
        id="gstr3b_monthly",
        title="GST GSTR-3B Monthly Filing",
        category="gst",
        frequency="monthly",
        day_of_month=20,
        applicable_entity_types=["all"],
        penalty_description="₹50/day late fee + 18% interest on tax due"
    ),
    # ... TDS, MCA, PF, ESI, ITR rules
]

def get_rules_for_entity(entity_type: str) -> List[ObligationRule]:
    return [r for r in STATUTORY_RULES if "all" in r.applicable_entity_types
            or entity_type in r.applicable_entity_types]
```

---

## 8. FRONTEND PRODUCT FLOWS

### Left-Nav Structure (New)

```
LegalOS — Compliance Command Center

  [Dashboard]          ← Default landing (compliance health overview)
  
  ── COMPLIANCE ──
  [Compliance Calendar] ← Month/week view of all tasks
  [Task Center]         ← List view with filters, bulk actions
  [Obligations]         ← Obligation register (all obligations)
  [Document Vault]      ← All compliance documents + expiry tracker
  [Evidence Vault]      ← All uploaded proofs organized by period
  
  ── ALERTS ──
  [Notifications]  🔔 N  ← Inbox: reminders, escalations, assignments
  [Overdue Tasks]  🔴 N  ← Requires immediate attention

  ── INTELLIGENCE ──
  [Contract Review]     ← (deprioritized in nav but accessible)
  [Vendor Check]        ← GSTIN verification
  [Legal Notices]       ← (accessible but not primary nav)
  
  ── SETTINGS ──
  [Organization]        ← GSTIN, entity type, company profile
  [Team Members]        ← Invite/manage users, assign roles
  [Reminder Settings]   ← Configure N-day intervals
  [Audit Trail]         ← Full activity log + export
  
  ── ACCOUNT ──
  [Profile]
  [Logout]
```

---

### Dashboard Widgets (Default Landing)

```
┌─────────────────────────────────────────────────────────────┐
│  Good morning, Rajesh 👋  |  Company: Acme Pvt Ltd          │
│  Today: Aug 4, 2026       |  GSTIN: 27AAPCA1234B1ZV         │
└─────────────────────────────────────────────────────────────┘

┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ COMPLIANCE   │ │  OVERDUE     │ │  DUE THIS    │ │  EXPIRING    │
│   SCORE      │ │  TASKS       │ │    WEEK      │ │    SOON      │
│    78%       │ │     3        │ │     7        │ │     2        │
│ ●●●●●●●○○○  │ │  🔴 Urgent   │ │  📅 Upcoming │ │  ⚠️ 60 days  │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘

┌─────────────────────────┐  ┌────────────────────────────────────┐
│  CATEGORY HEALTH        │  │  WHAT NEEDS ATTENTION NOW          │
│  GST     ████████░ 85%  │  │  🔴 GSTR-1 Overdue — 3 days       │
│  TDS     ██████░░░ 67%  │  │  🔴 TDS Deposit Overdue — 1 day    │
│  MCA     █████████ 100% │  │  🟡 PF Deposit due in 2 days       │
│  PF/ESI  ███████░░ 75%  │  │  🟡 FSSAI License expires 60 days  │
│  Labour  ██████████100% │  │  → View all overdue (3)            │
└─────────────────────────┘  └────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  UPCOMING DEADLINES (Next 30 days)                         │
│  Aug 7   TDS Deposit (Jul)           Anjali   ⏳ Pending    │
│  Aug 11  GSTR-1 Filing (Jul)         Anjali   ⏳ Pending    │
│  Aug 15  PF & ESI Deposit (Jul)      Vikram   ✅ Done       │
│  Aug 20  GSTR-3B Filing (Jul)        Anjali   ⏳ Pending    │
└─────────────────────────────────────────────────────────────┘
```

---

### Task Center

- **Filters:** Status (All / Overdue / Due Today / Due This Week / Completed / Closed) | Category | Assignee | Period
- **Bulk Actions:** Assign selected, Send reminder, Mark complete
- **Sort:** By due date (default), by priority, by assignee
- **Task card:** Title, category badge, due date, assignee avatar, status pill, overdue badge (red)
- **Quick actions:** Assign, Mark complete, Upload evidence (inline on card)

---

### Obligation Detail Page

```
/obligations/{id}

  GSTR-1 Monthly Filing
  Category: GST | Frequency: Monthly | Status: Active
  Penalty: ₹50/day late fee under Section 47
  
  [Edit Obligation] [Deactivate] [Generate Next Task]
  
  TASK HISTORY
  ┌─────────────────────────────────────────────────────┐
  │ Period     │ Due Date │ Status   │ Assigned │ Proof │
  │ Jul 2026   │ Aug 11   │ ✅ Closed│ Anjali   │  📄   │
  │ Jun 2026   │ Jul 11   │ ✅ Closed│ Anjali   │  📄   │
  │ May 2026   │ Jun 11   │ 🔴 Over  │ Unassigned│  -   │
  └─────────────────────────────────────────────────────┘
```

---

### Renewal Workflow Page

```
/compliance/documents/{id}/renew

  FSSAI License Renewal
  License No: 10020011001234
  Issued: Mar 1, 2025 | Expires: Feb 28, 2027
  Status: EXPIRING SOON (178 days remaining)
  
  RENEWAL TASKS
  ✅ Identify renewal requirements
  ⏳ Prepare renewal application (Due: Sep 1)
  ⏳ Submit application to FSSAI portal (Due: Oct 1)
  ⏳ Upload new license certificate (Due: Nov 1)
  
  [Upload Renewed Certificate]  [Mark Renewal Submitted]
```

---

### Evidence Upload Flow

1. User clicks "Mark Complete" on task
2. Modal appears: **"Upload Proof of Completion"**
   - Drag-and-drop or file picker
   - File types: PDF, DOCX, JPG, PNG (max 10MB)
   - Optional notes field
3. On upload: preview thumbnail shown, "Confirm Upload" button
4. On confirm: file saved, task moves to `pending_review`
5. Reviewer notified (if configured)
6. Evidence shown on task detail with download icon

---

### Alerts / Notification Inbox

```
/notifications

UNREAD (3)
─────────
🔴 [ESCALATION] GSTR-1 Filing (Jul) is 3 days overdue
   Assigned to: Anjali Sharma | Aug 4, 08:00
   [View Task] [Reassign]

🟡 [REMINDER] TDS Deposit (Jul) due in 3 days
   Assigned to: Anjali Sharma | Aug 4, 08:01
   [View Task]

⚠️ [EXPIRY] FSSAI License expires in 60 days
   License No: 10020011001234 | Aug 4, 07:00
   [Start Renewal]

READ (12)
─────────
[...]
```

---

### Owner vs. Reviewer Views

| Feature | Business Owner | CA / Compliance Manager | Reviewer |
|---------|---------------|------------------------|----------|
| Dashboard | Full org overview | Task-focused view | Pending review queue |
| Task Center | All tasks, all users | My tasks + team tasks | Tasks pending review |
| Assign tasks | ✅ | ✅ (for their team) | ❌ |
| Close tasks | ✅ | ❌ (needs reviewer) | ✅ |
| View audit trail | ✅ Full | ✅ Own tasks | ✅ Tasks they verified |
| Upload evidence | ✅ | ✅ | ❌ |
| Invite members | ✅ | ❌ | ❌ |
| Configure reminders | ✅ | ❌ | ❌ |
| Export audit trail | ✅ | ✅ | ✅ |

---

## 9. IMPLEMENTATION ROADMAP

### Week 1 — Foundation & Auth
**Product Goal:** Make it a real multi-tenant application, not a prototype

**Schema Tasks:**
- Alembic migration: add `organizations` table
- Alembic migration: add `org_id` FK to users, documents, compliance_tasks
- Alembic migration: create `obligations` table
- Alembic migration: add auth fields to users (email, password_hash, is_active)

**Backend Tasks:**
- Replace mock auth with JWT (python-jose + passlib/bcrypt)
- `POST /auth/register` — create org + owner user
- `POST /auth/login` — return JWT
- `GET /auth/me` — current user from JWT
- `dependencies.py` — replace role-header with JWT decode
- Add `org_id` to all compliance service queries (tenant isolation)

**Frontend Tasks:**
- Login + Register page (email + password)
- JWT storage (httpOnly cookie or localStorage with refresh)
- Remove role-switcher dropdown
- Auth guard on all routes

**Demoable Outcome:** User can register, log in, and their tasks are isolated from other orgs

---

### Week 2 — Task Ownership & State Machine
**Product Goal:** Every task has an owner and a meaningful status

**Schema Tasks:**
- Alembic: add `assigned_to_user_id`, `assigned_at`, `assigned_by_user_id` to tasks
- Alembic: expand `status` ENUM to full state machine
- Alembic: create `evidence_documents` table
- Alembic: create `activity_logs` table

**Backend Tasks:**
- `task_service.py`: implement status state machine with validation
- `PATCH /tasks/{id}/assign` endpoint
- `PATCH /tasks/{id}/start`, `/complete`, `/close`, `/reopen`
- `POST /tasks/{id}/evidence` — file upload + link
- `ActivityLogService`: log every state transition
- `GET /tasks/{id}/activity` — return log

**Frontend Tasks:**
- Task detail page redesign: status badge, assignee pill, action buttons
- "Assign to" user selector dropdown
- "Mark Complete" button → evidence upload modal
- Evidence preview on task detail
- Activity timeline component

**Demoable Outcome:** Assign a task → upload proof → reviewer closes it → full audit trail visible

---

### Week 3 — Reminders, Notifications & Dashboard
**Product Goal:** The system proactively contacts users — not the other way around

**Schema Tasks:**
- Alembic: create `reminders` table
- Alembic: create `notifications` table
- Alembic: create `escalations` table

**Backend Tasks:**
- `shared/notifications/email_service.py` — SendGrid integration
- `shared/notifications/notification_service.py` — in-app + email dispatch
- `shared/jobs/scheduler.py` — APScheduler setup, register jobs
- `reminder_job.py` — daily reminder dispatch with deduplication
- `escalation_job.py` — daily overdue + escalation check
- `overdue_marking_job.py` — mark tasks past due_date
- `GET /notifications` + `PATCH /notifications/{id}/read`
- `GET /dashboard/summary` — aggregate health query

**Frontend Tasks:**
- Dashboard page (default route) with metric cards + category health
- Notification inbox page
- Notification bell icon in nav header with unread count
- "Overdue Tasks" section highlighted in red
- Weekly digest email template (HTML)

**Demoable Outcome:** Demo GSTR-1 task overdue → system sends escalation email → dashboard shows red

---

### Week 4 — Obligation Register & Calendar Polish
**Product Goal:** Complete the compliance operations loop

**Schema Tasks:**
- Alembic: create `obligations` table
- Alembic: create `recurring_schedules` table
- Alembic: create `compliance_documents` (expiry tracking)

**Backend Tasks:**
- `obligation_service.py` — CRUD + GSTIN-init now creates obligations, not raw tasks
- `rules_engine.py` — statutory obligation rules per entity type
- `task_generation_job.py` — generate recurring task instances
- `expiry_job.py` — detect expiring documents → create renewal tasks
- `GET /obligations` + `POST /obligations`
- `GET /compliance/documents/expiring`
- `GET /dashboard/calendar?month=YYYY-MM`

**Frontend Tasks:**
- Calendar view (month grid) with task dots
- Obligation list/detail pages
- "Expiring Soon" widget on dashboard
- Renewal workflow page
- Task center with full filter/sort/bulk capabilities

**Demoable Outcome:** Full live demo: GSTIN onboarding → calendar → reminder → evidence → closure → audit trail export

---

### Optional Week 5–6 — Polish & Sales-Readiness
**Product Goal:** First paying customer demo-ready

**Tasks:**
- Evidence vault page (all proofs organized by period/category)
- Audit trail export as CSV
- Org settings page (GSTIN, entity type, reminder intervals)
- Invite team members + role management
- Loading states, error states, empty states on all pages
- Mobile responsive layout
- Rate limiting on auth endpoints
- Input validation hardening
- Docker production config (non-dev Uvicorn workers)
- MinIO local S3 setup (replace disk storage)
- Email template branding (LegalOS logo)
- Basic onboarding tour / empty state for new orgs

---

## 10. HIGH-IMPACT CODEBASE CHANGES

### 1. Auth / RBAC — Replace Mock System

**Current:** X-User-Role header → MOCK_USERS dict → UserStub  
**Required:** Email/password login → bcrypt verify → JWT issue → JWT decode on every request

```python
# shared/auth/auth_service.py — REPLACE ENTIRELY

async def create_user(email, password, org_id, role) -> User: ...
async def authenticate(email, password) -> Optional[User]: ...
async def create_access_token(user_id, org_id, role) -> str: ...
async def decode_token(token) -> TokenPayload: ...

# dependencies.py — REPLACE get_current_user()
async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    payload = decode_token(token)
    return await user_repo.get_by_id(payload.user_id)
```

**Packages:** `python-jose[cryptography]`, `passlib[bcrypt]`  
**Impact:** Every endpoint currently takes `current_user` from DI — interface unchanged, just replace the resolver

---

### 2. Multi-Tenancy — Add org_id to All Queries

**Current:** Queries filter by `user_id` (fragile, not org-isolated)  
**Required:** Every query must filter by `org_id` from JWT

```python
# Every service call must pass org_id from current user
tasks = await task_repo.list_tasks(db, org_id=current_user.org_id)
# NOT: list_tasks(db, user_id=current_user.id)
```

**Migration:** Add `org_id` column to all tables. Use Alembic migration with DEFAULT = seed org UUID. Then backfill existing data.

---

### 3. Workflow State Modeling

**Current:** `status` is a loose string field with no validation  
**Required:** State machine with valid transitions enforced in service layer

```python
VALID_TRANSITIONS = {
    "pending":          ["in_progress", "overdue"],
    "in_progress":      ["completed", "completed_no_evidence", "overdue"],
    "completed":        ["pending_review", "closed"],
    "completed_no_evidence": ["completed"],  # add proof to upgrade
    "pending_review":   ["closed", "pending"],  # approve or reject
    "overdue":          ["in_progress", "completed"],
    "closed":           ["reopened"],
    "reopened":         ["in_progress"],
}

def transition(task: ComplianceTask, to_status: str, actor: User):
    if to_status not in VALID_TRANSITIONS[task.status]:
        raise BadRequestException(f"Invalid transition: {task.status} → {to_status}")
    task.status = to_status
    log_event(task, actor, f"task.{to_status}")
```

---

### 4. Background Task Reliability

**Current:** `FastAPI BackgroundTasks` — in-process, no retry, lost on restart  
**For MVP:** `APScheduler` with PostgreSQL job store (persistence across restarts)  
**For production:** `Celery` + `Redis` (distributed, retryable, monitorable)

```python
# shared/jobs/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

scheduler = AsyncIOScheduler(
    jobstores={"default": SQLAlchemyJobStore(url=settings.database_url_sync)},
    timezone="Asia/Kolkata"
)

scheduler.add_job(send_reminders, "cron", hour=8, minute=0)
scheduler.add_job(check_escalations, "cron", hour=9, minute=0)
scheduler.add_job(mark_overdue_tasks, "cron", hour=0, minute=1)
```

---

### 5. Notification / Event Architecture

**Pattern:** Event-driven notification via internal event bus  
**MVP Implementation:** Direct service calls (simple + effective)  
**Future:** Use a message queue (Redis pub/sub or Kafka)

```python
# Every service action calls NotificationService directly
async def assign_task(task, assignee, actor, db):
    task.assigned_to_user_id = assignee.id
    log_event(task, actor, "task.assigned")
    await notification_service.send_task_assigned(task, assignee)  # non-blocking
    await db.commit()
```

---

### 6. File Storage Strategy

**Current:** Local disk under `uploads/` — data lost on container restart  
**MVP:** MinIO (S3-compatible, runs in Docker) — same API as S3  
**Production:** AWS S3 with org-scoped prefixes

```python
# shared/storage/file_storage.py — UPGRADE
class FileStorage:
    def __init__(self):
        self.client = boto3.client("s3", endpoint_url=settings.s3_endpoint)
    
    async def save_file(self, org_id, file_bytes, filename) -> str:
        key = f"{org_id}/compliance/{uuid4()}_{filename}"
        self.client.put_object(Bucket=settings.s3_bucket, Key=key, Body=file_bytes)
        return key
    
    async def get_presigned_url(self, key, expiry=3600) -> str:
        return self.client.generate_presigned_url("get_object", 
                   Params={"Bucket": settings.s3_bucket, "Key": key}, 
                   ExpiresIn=expiry)
```

Add MinIO to `docker-compose.yml`:
```yaml
minio:
  image: minio/minio:latest
  ports: ["9000:9000", "9001:9001"]
  environment:
    MINIO_ROOT_USER: minioadmin
    MINIO_ROOT_PASSWORD: minioadmin
  command: server /data --console-address ":9001"
```

---

### 7. Auditability

**Pattern:** Append-only `activity_logs` table. Every service method that changes state calls `log_event()`.

```python
# shared/audit/audit_service.py
async def log_event(
    db: AsyncSession,
    org_id: UUID,
    entity_type: str,
    entity_id: UUID,
    user_id: Optional[UUID],
    action: str,
    metadata: dict = {}
):
    log = ActivityLog(
        org_id=org_id, entity_type=entity_type, entity_id=entity_id,
        user_id=user_id, action=action, metadata=metadata
    )
    db.add(log)  # commit happens in the calling service
```

**DB-level protection:** Add a trigger to block UPDATE/DELETE on `activity_logs`.

---

### 8. Idempotency

**Reminders:** Check `reminders` table before sending — if `(task_id, days_before_due)` exists with `status=sent`, skip.  
**Task Generation:** Check `obligations + period_label` before creating — if task for that period exists, update instead of insert.  
**GSTIN Init:** Don't delete all tasks on re-init — detect existing and update only changed fields.  
**Evidence Upload:** Allow multiple evidence files per task — no duplication concern.

---

### 9. Production Readiness Checklist

| Item | Status | Action |
|------|--------|--------|
| Real auth | ❌ | Week 1 |
| Multi-tenancy | ❌ | Week 1 |
| S3 file storage | ❌ | Week 4 |
| APScheduler jobs | ❌ | Week 3 |
| Rate limiting | ❌ | Week 5 |
| Input validation | 🟡 Partial | Harden |
| Health check | ✅ | Keep |
| Error handling | ✅ | Extend |
| CORS config | ✅ | Tighten for prod |
| Audit logging | ❌ | Week 2 |
| Docker prod config | 🟡 Dev-only | Week 5 |
| DB connection pooling | ✅ asyncpg | Keep |

---

## 11. SALES READINESS

### One-Line Pitch

> **"LegalOS is your company's compliance autopilot — it tracks every deadline, chases your team, collects proof, and keeps a complete audit trail."**

---

### Homepage Hero Copy

**Headline:** Never Miss a Compliance Deadline Again.  
**Subheadline:** LegalOS gives Indian SMEs a complete compliance command center — automated reminders, task ownership, evidence collection, and a full audit trail. Replace your Excel + WhatsApp + CA panic with one system.  
**CTA:** "Start with your GSTIN →"

---

### 5 Bullet Value Proposition

1. ✅ **Complete compliance calendar in 60 seconds** — enter your GSTIN, get every GST, TDS, MCA, PF/ESI deadline auto-generated for your company type
2. ✅ **Never rely on your CA to remind you** — automatic email reminders 30/15/7/3/1 days before every deadline
3. ✅ **Proof of compliance, not just promises** — every task requires a filing receipt, challan, or screenshot before it can be marked complete
4. ✅ **No more "did you file?" conversations** — assign tasks to team members; overdue tasks escalate automatically to the owner
5. ✅ **Audit-ready in one click** — complete timestamped audit trail of every action, every document, every approval, exportable as PDF

---

### 3 Pricing Tier Suggestions

| Tier | Name | Price | For | Features |
|------|------|-------|-----|---------|
| **Starter** | Solo | ₹999/month | Sole proprietors, freelancers | 1 user, GSTIN calendar, email reminders, up to 50 tasks/month |
| **Growth** | Team | ₹2,999/month | SMEs with 2–15 users | 5 users, full task ownership, evidence vault, escalation, audit trail |
| **Business** | Command | ₹7,999/month | Growing companies with CA + reviewer workflows | Unlimited users, multi-entity, CA partner view, CSV export, priority support |

**Annual discount:** 2 months free (saves ₹6k–₹16k/year)  
**CA Partner Plan:** ₹1,500/client/month (multi-client dashboard)

---

### Demo Script for First Sales Call

**[0:00–1:00] Hook — show the pain**  
> "How do you currently track your GST, TDS, and MCA deadlines? Show me your setup."  
*(Let them describe their Excel/WhatsApp/CA situation)*

**[1:00–3:00] GSTIN onboarding — wow moment**  
> "Type your GSTIN here."  
*(GSTIN entered → calendar loads with 35 tasks across all categories)*  
> "That's your complete compliance calendar for the financial year. Every deadline, auto-generated based on your company type."

**[3:00–5:00] Task assignment + reminder**  
> "Let's assign the GSTR-1 to your CA. Done. She'll get an email 15, 7, and 3 days before it's due — automatically. No WhatsApp needed."

**[5:00–7:00] Evidence collection**  
> "When the CA files, she clicks 'Mark Complete' and uploads the filing acknowledgment. The task is now closed with proof. Look — here's the evidence attached to the task."

**[7:00–8:30] Dashboard + escalation**  
> "Here's your dashboard. You can see which categories are healthy and which ones are at risk. If the CA doesn't act and a deadline passes — you get this escalation email. You always know what's on fire."

**[8:30–10:00] Audit trail + close**  
> "And here's the audit trail — every action, timestamped. If you're ever audited, you export this and show: here's what we filed, when, who uploaded the proof. One click."  
> "This is what we're replacing: the panic, the WhatsApp reminders, the Excel tracker, and the penalty notices."

---

### Objections & Answers

| Objection | Answer |
|-----------|--------|
| "My CA handles all of this" | "Your CA handles the filing — but does your CA track whether it happened, remind your team, collect the proof, and show you an audit trail? That's what LegalOS does between you and your CA." |
| "I can do this in Excel" | "Excel doesn't email your team 15 days before a deadline, escalate to you when nothing happens, collect the actual proof file, and generate an audit trail. Excel is where compliance reminders go to die." |
| "This is too expensive" | "One GST late filing is ₹50/day. One missed MCA return is ₹100/day. One income tax demand notice is ₹5,000+. LegalOS pays for itself the moment it prevents one penalty." |
| "We already use Tally/Zoho" | "Tally tracks your accounts. Zoho tracks your customers. Neither of them tracks compliance deadlines, assigns tasks to your team, or collects filing proofs. They're not built for this." |
| "Is this data secure?" | "Your documents are stored with the same security as cloud storage (S3). Access is role-based. Every action is logged. We never share your data or filing details with anyone." |
| "What if we miss something anyway?" | "LegalOS doesn't just remind once — it escalates. If your team doesn't act after 3 reminders, you get an escalation email. If we fail at something, it's visible and logged — not silently missed." |

---

## 12. FINAL RECOMMENDATION

### The Single Best MVP to Build First

**Compliance Operations Loop:**  
GSTIN onboarding → calendar → task assignment → email reminders → evidence upload → task closure → audit trail

This is the smallest complete product you can ship and charge for. It connects every step from "we have a deadline" to "we have proof we met it." No feature in this loop is optional — each one enables the next.

---

### The One Feature That Will Most Increase Willingness to Pay

**Evidence upload with task closure verification.**

Here's why: customers can find calendar tools for free. Reminders are cheap. But *proof that compliance happened* — a system that says "you cannot mark this done without uploading the filing receipt" — is the feature that separates a compliance management product from a fancy to-do list.

The moment a customer shows a CA or auditor a task with the filing acknowledgment attached and a timestamped closure — they will never go back to Excel. That's your anchor moment.

---

### The Biggest Mistake to Avoid

**Keeping the mock auth and multi-module UI parity as the demo.**

The current system looks like four separate utilities bolted together. The moment you demo it to a real customer with a role-switcher dropdown in the header, they see "prototype." They don't see a product they'd pay for.

The single worst thing you can do is show a customer a beautiful compliance calendar and then have them ask "how do I log in?" and you say "just pick owner/CA/reviewer from the dropdown."

Fix auth in Week 1. Nothing else is as important for sales credibility.

---

### How to Position Against "Just Use Excel + CA + Reminders"

Don't fight the comparison — use it:

> "Excel and your CA are great for the work — we make sure the work actually gets done, gets proven, and gets tracked. Excel doesn't escalate to you when your CA forgets. Your CA doesn't upload the proof to a searchable vault. LegalOS is the operational layer between you and your CA — not a replacement."

Position it as the **operating system for compliance operations**, not a replacement for the CA. The CA is the expert. LegalOS is the workflow that ensures their advice becomes verifiable, traceable action.

---

---

## BUILD ORDER FOR THE CODE AGENT

### Phase 0: Pre-work (Do Before Any Feature Work)

**Goal:** Stabilize the foundation without breaking anything.

1. **Verify the current system boots** — run `docker-compose up` and confirm all 4 endpoints work
2. **Audit existing migrations** — check Alembic `alembic_version` table, ensure all migrations are applied
3. **Create a `feature/productization` git branch** — never work on main during this transformation
4. **Add `org_id` placeholder to settings** — create a `SEED_ORG_ID` UUID in config for migration defaults
5. **Add MinIO to docker-compose.yml** — add service, do NOT modify existing services yet
6. **Dependency additions to pyproject.toml:**
   - `python-jose[cryptography]` — JWT
   - `passlib[bcrypt]` — password hashing
   - `apscheduler` — background scheduler
   - `sendgrid` or `aiosmtplib` — email
   - `boto3` — S3/MinIO client
   - `jinja2` — email templates

---

### Phase 1: Data Model Foundation (Week 1, Days 1–2)

**Touch these files/create these migrations — in this exact order:**

1. **Create `organizations` table** — Alembic migration `001_add_organizations.py`
   - Add `core.organizations` with all fields listed in Section 6
   - Insert one seed organization: `id=SEED_ORG_UUID, name="Seed Org", gstin="27AAPCA0000A1Z1"`

2. **Update `core.users` table** — Alembic migration `002_update_users_auth.py`
   - Add: `email`, `password_hash`, `org_id` (FK → organizations, DEFAULT SEED_ORG_UUID), `is_active`, `last_login_at`
   - Update seed users: assign email (owner@seed.com, ca@seed.com, reviewer@seed.com)

3. **Update `compliance_center.compliance_tasks`** — Alembic migration `003_update_tasks.py`
   - Add: `org_id`, `obligation_id` (nullable initially), `assigned_to_user_id`, `assigned_by_user_id`, `assigned_at`, `status` ENUM extension, `started_at`, `completed_at`, `closed_at`, `closed_by_user_id`, `priority`, `period_label`
   - Set DEFAULT org_id = SEED_ORG_UUID for existing rows

4. **Create `obligations` table** — Alembic migration `004_add_obligations.py`

5. **Create `evidence_documents` table** — Alembic migration `005_add_evidence_documents.py`

6. **Create `activity_logs` table** — Alembic migration `006_add_activity_logs.py`
   - Add DB trigger: `BEFORE UPDATE OR DELETE ON core.activity_logs → RAISE EXCEPTION 'Audit log is immutable'`

7. **Create `reminders` table** — Alembic migration `007_add_reminders.py`

8. **Create `escalations` table** — Alembic migration `008_add_escalations.py`

9. **Create `notifications` table** — Alembic migration `009_add_notifications.py`

10. **Create `compliance_documents` table** — Alembic migration `010_add_compliance_documents.py`

---

### Phase 2: Auth Replacement (Week 1, Days 3–4)

**Touch these files — in this order:**

1. `shared/auth/jwt_utils.py` — NEW: `create_access_token()`, `decode_token()`, `TokenPayload` dataclass
2. `shared/auth/auth_service.py` — REPLACE: remove mock users, implement `authenticate()`, `create_user()`
3. `shared/db/models.py` — UPDATE: add new fields to User model (email, password_hash, org_id FK)
4. `workspaces/auth/router.py` — NEW: `POST /auth/register`, `POST /auth/login`, `GET /auth/me`
5. `workspaces/auth/service.py` — NEW: registration + login logic
6. `workspaces/auth/schemas.py` — NEW: LoginRequest, RegisterRequest, TokenResponse
7. `dependencies.py` — REPLACE `get_current_user()`: decode JWT, look up real User from DB
8. `main.py` — Register auth router, remove mock user seeding (replace with seed org migration)

**DO NOT BREAK:** All existing workspace routers use `current_user: User = Depends(get_current_user)`. The interface must stay the same — only the implementation changes.

---

### Phase 3: Multi-Tenancy Guard (Week 1, Day 5)

1. Update every repository function in `compliance_center/repository.py` to filter by `org_id`
2. Update every service call to pass `current_user.org_id`
3. Test: verify that org A's tasks are not visible to org B user

---

### Phase 4: Task State Machine (Week 2, Days 1–2)

1. `workspaces/compliance_center/task_service.py` — REFACTOR: add `transition()` method with valid state map
2. `workspaces/compliance_center/router.py` — ADD endpoints: `/assign`, `/start`, `/complete`, `/close`, `/reopen`
3. `workspaces/compliance_center/schemas.py` — UPDATE: add new task fields to response schema
4. `shared/audit/audit_service.py` — NEW: `log_event()` function
5. Call `log_event()` from every state transition in task_service

---

### Phase 5: Evidence Upload (Week 2, Days 3–4)

1. `shared/storage/file_storage.py` — UPGRADE: add MinIO/S3 backend (keep local as fallback for dev)
2. `workspaces/compliance_center/evidence_service.py` — NEW: upload + link evidence
3. `workspaces/compliance_center/router.py` — ADD: `POST /tasks/{id}/evidence`, `GET /tasks/{id}/evidence`
4. `workspaces/compliance_center/models.py` — ADD: `EvidenceDocument` model class

---

### Phase 6: Notifications + Scheduler (Week 3)

1. `shared/notifications/email_service.py` — NEW: SendGrid wrapper
2. `shared/notifications/templates/` — NEW: Jinja2 HTML email templates (reminder, escalation, assignment)
3. `shared/notifications/notification_service.py` — NEW: in-app + email dispatch
4. `shared/jobs/scheduler.py` — NEW: APScheduler setup, registered in `main.py` lifespan
5. `shared/jobs/reminder_job.py` — NEW: query + send daily reminders
6. `shared/jobs/escalation_job.py` — NEW: query + escalate overdue tasks
7. `shared/jobs/overdue_marking_job.py` — NEW: mark overdue tasks
8. `workspaces/notifications/router.py` — NEW: notification inbox endpoints
9. `main.py` — start scheduler in lifespan

---

### Phase 7: Dashboard + Obligations (Week 4)

1. `workspaces/dashboard/service.py` — NEW: aggregate health queries
2. `workspaces/dashboard/router.py` — NEW: `GET /dashboard/summary`, `GET /dashboard/calendar`
3. `workspaces/compliance_center/obligation_service.py` — NEW: obligation CRUD
4. `workspaces/compliance_center/rules_engine.py` — NEW: statutory obligation rules
5. Refactor `initialize_statutory_tasks()` → now creates `Obligation` records + generates tasks from them
6. `shared/jobs/task_generation_job.py` — NEW: recurring task instance creation
7. `shared/jobs/expiry_job.py` — NEW: document expiry detection + renewal task creation

---

### Phase 8: Frontend Rebuild (Weeks 2–4, parallel to backend)

**Do not rebuild from scratch — extend existing components:**

1. **Week 2:** Auth pages (Login, Register), remove role-switcher, auth API client, JWT handling
2. **Week 2:** Task detail page redesign — state machine buttons, assignee, evidence upload modal
3. **Week 3:** Dashboard page (replace contract list as default route), notification inbox, bell icon
4. **Week 4:** Calendar view, obligation list/detail, expiry tracker, evidence vault

**File-touch order:**
```
src/lib/auth/AuthContext.tsx      ← REPLACE: use JWT from backend
src/api/auth.ts                   ← NEW: login/register/me API calls
src/pages/Login.tsx               ← NEW
src/pages/Register.tsx            ← NEW
src/App.tsx                       ← Update routes, add auth guard
src/design-system/layout/AppShell.tsx ← Update nav structure
src/pages/Dashboard.tsx           ← NEW (compliance health)
src/workspaces/compliance-center/pages/TaskCenter.tsx   ← REFACTOR
src/workspaces/compliance-center/pages/TaskDetail.tsx   ← NEW
src/workspaces/compliance-center/pages/Calendar.tsx     ← NEW
src/workspaces/compliance-center/pages/Obligations.tsx  ← NEW
src/workspaces/compliance-center/pages/EvidenceVault.tsx ← NEW
src/pages/Notifications.tsx       ← NEW
```

---

### How to Avoid Breaking the Current System

1. **Never modify existing migration files** — only add new ones
2. **Keep existing API endpoints working** — add new routes, don't replace old signatures
3. **Use `DEFAULT` values in all new columns** — existing rows must not break
4. **Test after each migration** — run `alembic upgrade head` + smoke test existing endpoints
5. **Keep mock mode** — `SANDBOX_CO_MODE=mock` must still work
6. **Feature flags in config** — `ENABLE_SCHEDULER=false` for dev, `true` for production
7. **Keep existing background task pattern** — only add APScheduler alongside it, don't remove yet
8. **Document your org_id** in `.env.example` as the single seed org UUID

---

### Testing Order

1. Auth: register → login → JWT → access protected endpoint
2. Multi-tenancy: org A user cannot see org B tasks
3. Task state machine: every valid + invalid transition
4. Evidence upload: file saves to MinIO, links to task, visible on task detail
5. Reminders: mock the clock → confirm reminder fires + deduplication works
6. Escalation: mark task overdue → confirm escalation email generated
7. Dashboard: verify counts match actual task/document state
8. Audit trail: perform actions → verify log is complete + immutable
9. GSTIN init: full flow creates obligations → tasks → reminder schedule

