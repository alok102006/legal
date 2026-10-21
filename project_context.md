# LegalOS — Complete Project Context & AI Technical Reference

> **Authoritative Context Document for AI Assistants (ChatGPT, Claude, Gemini, Copilot, Cursor)**  
> *Use this document to understand the complete codebase architecture, business domain, full technology stack, database schemas, AI/RAG pipelines, external statutory APIs, and engineering conventions of LegalOS.*

---

## 1. Executive Summary & Domain Overview

### What is LegalOS?
**LegalOS** is a production-grade, multi-workspace AI operating system built specifically for **Indian Small and Medium Enterprises (SMEs)**, corporate legal teams, and Chartered Accountants (CAs). It unifies contract analysis, statutory compliance monitoring, legal notice drafting, vendor fraud screening, and enterprise document risk auditing into a single platform.

### Core Problems Solved
1. **High Legal Retainer Costs**: Indian SMEs spend thousands of dollars retaining law firms for standard contract reviews, redlining, and replying to boilerplate legal notices. LegalOS automates clause-level risk scoring and generates legally structured redlines in seconds.
2. **Severe Statutory Penalties**: Missing mandatory Indian filing deadlines (GST GSTR-1/3B, TDS quarterly returns, MCA AOC-4/MGT-7, PF & ESI, Advance Tax) triggers compounding daily fines, director disqualifications, and frozen bank accounts. LegalOS dynamically generates filing calendars customized by business entity type (Pvt Ltd, LLP, Partnership, Sole Proprietorship).
3. **Vendor Fraud & Input Tax Credit (ITC) Loss**: Transacting with unregistered or cancelled GSTIN vendors causes forfeiture of Input Tax Credit under Indian GST law. LegalOS verifies GSTINs in real time via official government gateway APIs (Sandbox.co.in), computes trust scores, and flags fraud risks.
4. **Fragmented Corporate Knowledge & Compliance Gaps**: Companies struggle to track internal policies, board resolutions, and registration certificates against statutory obligations. LegalOS features a **Knowledge Hub** with strict Ground-Truth RAG Q&A and an **AI Document Risk Radar**.

---

## 2. System Architecture

```
                               ┌─────────────────────────────────────────┐
                               │           REACT 18 + VITE FRONTEND      │
                               │   Tailwind CSS v3.4 · Lucide React      │
                               │   Role Switcher (Owner, CA, Reviewer)   │
                               └────────────────────┬────────────────────┘
                                                    │ HTTP / REST (Axios)
                                                    │ Injected: 'X-User-Role'
                                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 FASTAPI ASGI BACKEND (Uvicorn)                                 │
│                                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                  WORKSPACE REST ROUTERS                                   │  │
│  │   /api/v1/contracts   │   /api/v1/notices   │   /api/v1/compliance                            │  │
│  │   /api/v1/vendors     │   /api/v1/knowledge │   /health                                       │  │
│  └─────────────────────────────────────────────┬─────────────────────────────────────────────┘  │
│                                                │                                                │
│         ┌──────────────────────────────────────┴──────────────────────────────────────┐          │
│         ▼                                                                             ▼          │
│  ┌──────────────────────────┐                                                ┌───────────────┐  │
│  │   BACKGROUND TASKS       │                                                │ DEPENDENCIES  │  │
│  │   (FastAPI               │                                                │ get_db_session│  │
│  │    BackgroundTasks)      │                                                │ get_current_  │  │
│  │   Async doc processing   │                                                │    user       │  │
│  └──────────┬───────────────┘                                                └───────┬───────┘  │
│             │                                                                        │          │
│  ┌──────────▼────────────────────────────────────────────────────────────────────────▼───────┐  │
│  │                                     SERVICE LAYER                                         │  │
│  │   Business logic, risk scoring algorithms, statutory schedules, grounding prompts        │  │
│  └──────────┬──────────────────────────┬─────────────────────────────┬───────────────────────┘  │
│             │                          │                             │                          │
│             ▼                          ▼                             ▼                          │
│  ┌─────────────────────┐   ┌───────────────────────────┐   ┌─────────────────────────────────┐  │
│  │   AI / RAG ENGINE   │   │  THIRD-PARTY API CLIENT   │   │    POSTGRESQL ORM (ASYNC)       │  │
│  │ • PyMuPDF / docx    │   │ • Sandbox.co.in Client    │   │ • SQLAlchemy 2.0 (asyncpg)      │  │
│  │ • Text Chunker      │   │ • OAuth / JWT token cache │   │ • Schema isolation per module   │  │
│  │ • MiniLM Embedder   │   │ • Live GSTIN profiling    │   │ • UUID Mixins & Cascade deletes │  │
│  │ • Qdrant Client     │   │ • Auto-retry on 401       │   │ • Alembic Migrations            │  │
│  │ • Gemini LLM Client │   └─────────────┬─────────────┘   └────────────────┬────────────────┘  │
│  └──────────┬──────────┘                 │                                  │                   │
└─────────────┼────────────────────────────┼──────────────────────────────────┼───────────────────┘
              │                            │                                  │
              ▼                            ▼                                  ▼
   ┌──────────────────────┐   ┌─────────────────────────┐        ┌─────────────────────────┐
   │    QDRANT VECTOR DB  │   │  Sandbox.co.in API      │        │    POSTGRESQL DATABASE  │
   │  Collections (384-d):│   │  (Official GSTIN / Tax  │        │  Schemas:               │
   │  • contract_clauses  │   │   Registry Endpoint)    │        │  • core                 │
   │  • legal_notices     │   └─────────────────────────┘        │  • contract_intelligence│
   │  • knowledge_base    │                                      │  • legal_notice_center  │
   └──────────────────────┘                                      │  • compliance_center    │
                                                                 │  • vendor_intelligence  │
                                                                 │  • knowledge_hub        │
                                                                 └─────────────────────────┘
```

---

## 3. Technology Stack & Key Libraries

### Backend Stack
- **Language & Runtime**: Python 3.10+ / 3.11+, ASGI with Uvicorn.
- **Framework**: FastAPI (`^0.110.0`), Pydantic v2 (`^2.6.4`), Pydantic-Settings (`^2.2.1`).
- **Database & ORM**: PostgreSQL 15, SQLAlchemy 2.0 (`^2.0.28`) with `asyncpg` (`^0.29.0`) driver, Alembic (`^1.13.1`) for migrations.
- **Document Parsing**: PyMuPDF / `fitz` (`^1.23.26`) for rapid PDF text extraction, `python-docx` (`^1.1.0`) for Word documents.
- **Package Management**: Poetry (`pyproject.toml`, `poetry.lock`).

### AI, RAG & Vector Store Stack
- **Vector Database**: Qdrant (`qdrant-client ^1.8.0`) running on port `6333` (Docker: `6335:6333`).
- **Embedding Model**: `sentence-transformers` (`^2.5.1`) running `all-MiniLM-L6-v2` locally as an in-memory singleton. Outputs 384-dimensional dense vectors with Cosine distance metric.
- **LLM Orchestration**: Google Gemini API via `google-genai` (Gemini 2.5 Flash / Gemini 1.5 Flash).
  - Synchronous `generate()` and non-blocking `generate_async()` (offloaded to thread pools via `asyncio.get_event_loop().run_in_executor`).
  - Strict JSON output mode (`json_mode=True`) with fallback parsers and markdown-fence stripping.
  - Pluggable provider architecture with a local Ollama fallback option.
- **RAG Chunker**: Custom paragraph-based sliding chunker with overlap (`chunk_by_paragraph_with_overlap`, default `max_chars=800`, `overlap_chars=150`).
- **Hybrid Retrieval**: Vector semantic search + fallback keyword-overlap paragraph ranking (`extract_best_matching_paragraphs`) over stored text.

### Frontend Stack
- **Framework**: React 18 (`^18.2.0`), TypeScript (`^5.2.2`), Vite 5 (`^5.1.6`).
- **Styling**: Tailwind CSS (`^3.4.1`), PostCSS, Autoprefixer, custom glassmorphism design system.
- **Routing**: `react-router-dom` (`^6.22.3`).
- **HTTP Client**: Axios (`^1.6.8`) with request interceptor for `X-User-Role`.
- **Icons**: Lucide React (`^0.363.0`).

### Infrastructure & Deployment
- **Docker Compose**: Multi-container setup orchestrating `db` (Postgres 15), `qdrant`, `backend` (FastAPI), and `frontend` (Vite dev server).
- **File Storage**: Local persistent file volume under `storage/` and `uploads/`.

---

## 4. Repository & Codebase Directory Structure

```
LegalOs/
├── PROJECT_OVERVIEW_FOR_CHATGPT.md   # Resume & high-level interview overview
├── project_context.md                # This file (Complete context for AI assistants)
└── legalos/
    ├── .env                          # Environment secrets
    ├── .env.example                  # Example environment config
    ├── docker-compose.yml            # Multi-service container orchestration
    ├── architecture.md               # In-depth architectural documentation
    ├── backend/
    │   ├── Dockerfile
    │   ├── alembic.ini               # Database migration configuration
    │   ├── pyproject.toml            # Poetry dependencies & project metadata
    │   ├── storage/                  # Persistent document storage
    │   │   └── knowledge_hub/        # Organization document storage partitioned by company_id
    │   ├── uploads/                  # Temporary file upload directory
    │   └── app/
    │       ├── config.py             # Pydantic Settings singleton (env loading)
    │       ├── dependencies.py       # FastAPI DI (get_db_session, get_current_user)
    │       ├── main.py               # App entrypoint, lifespan, CORS, router mounting
    │       ├── migrations/           # Alembic migration scripts (001 to 006)
    │       │   └── versions/
    │       │       ├── 001_baseline.py
    │       │       ├── 002_vendor_and_notice.py
    │       │       ├── e722b756ed97_add_compliance_center.py
    │       │       ├── 004_add_knowledge_hub.py
    │       │       ├── 005_enhance_company_documents.py
    │       │       └── 006_add_risk_analysis.py
    │       ├── core/
    │       │   ├── embeddings/
    │       │   │   └── embedder.py   # SentenceTransformer singleton (all-MiniLM-L6-v2)
    │       │   ├── vectorstore/
    │       │   │   ├── qdrant_client.py # Qdrant client connection provider
    │       │   │   └── collections.py   # Idempotent collection initialization
    │       │   ├── llm/
    │       │   │   ├── llm_client.py # generate() and generate_async() dispatchers
    │       │   │   ├── providers/
    │       │   │   │   ├── gemini_provider.py # Google Gemini API integration
    │       │   │   │   └── local_provider.py  # Local/Ollama integration
    │       │   │   └── prompts/
    │       │   │       └── contract_intel_prompts.py # Prompts for risk scoring & redlines
    │       │   └── rag/
    │       │       ├── document_parser.py # PDF (PyMuPDF), DOCX, CSV, XLSX, TXT parsers
    │       │       ├── chunker.py         # Overlap-aware paragraph text splitter
    │       │       └── rag_pipeline.py    # Ingest, embed, and query pipeline
    │       ├── shared/
    │       │   ├── auth/
    │       │   │   └── auth_service.py # Role-based UserStub (owner, ca, reviewer)
    │       │   ├── db/
    │       │   │   ├── base.py       # SQLAlchemy DeclarativeBase
    │       │   │   ├── mixins.py     # UUIDPrimaryKeyMixin, TimestampMixin
    │       │   │   ├── models.py     # core.users & core.documents models
    │       │   │   └── session.py    # asyncpg session factory & get_db_session
    │       │   ├── exceptions.py     # LegalOSException, NotFoundException, BadRequestException
    │       │   └── file_storage.py   # Disk I/O utilities
    │       └── workspaces/           # 5 Isolated Business Workspaces
    │           ├── contract_intelligence/
    │           │   ├── models.py     # Contract, Clause, NegotiationSuggestion
    │           │   ├── schemas.py    # Pydantic schemas
    │           │   ├── service.py    # Background worker, chunking, scoring, redlining
    │           │   └── router.py     # /api/v1/contracts endpoints
    │           ├── legal_notice_center/
    │           │   ├── models.py     # Notice, DraftReply
    │           │   ├── schemas.py    # Pydantic schemas
    │           │   ├── service.py    # Urgency & type classifier, legal reply drafting
    │           │   └── router.py     # /api/v1/notices endpoints
    │           ├── compliance_center/
    │           │   ├── models.py     # ComplianceTask, ComplianceDocumentAnalysis
    │           │   ├── schemas.py    # Pydantic schemas
    │           │   ├── statutory_data.py # Indian tax & MCA filing rules & deadlines
    │           │   ├── service.py    # Entity calendar generator, certificate analyzer
    │           │   └── router.py     # /api/v1/compliance endpoints
    │           ├── vendor_intelligence/
    │           │   ├── models.py     # VendorCheck
    │           │   ├── schemas.py    # Pydantic schemas
    │           │   ├── sandbox_client.py # Live GSTIN API client & JWT token cache
    │           │   ├── service.py    # Trust score algorithm, audit trail logger
    │           │   └── router.py     # /api/v1/vendors endpoints
    │           └── knowledge_hub/
    │               ├── models.py     # RegisteredCompany, CompanyDocument
    │               ├── schemas.py    # Pydantic schemas
    │               ├── sandbox_client.py # Live company GSTIN profiling
    │               ├── repository.py # Database query operations
    │               ├── service.py    # AI Risk Radar, Ground-Truth RAG Q&A
    │               └── router.py     # /api/v1/knowledge endpoints
    └── frontend/
        ├── package.json
        ├── tsconfig.json
        ├── vite.config.ts
        ├── src/
        │   ├── App.tsx               # Routes definition & AppShell wrapping
        │   ├── main.tsx              # React DOM mounting
        │   ├── index.css             # Tailwind base styles
        │   ├── api/
        │   │   ├── client.ts         # Axios client + X-User-Role interceptor
        │   │   ├── types.ts          # TypeScript interfaces for API contracts
        │   │   └── knowledge.ts      # API client for Knowledge Hub
        │   ├── lib/
        │   │   └── auth/
        │   │       └── AuthContext.tsx # Role Switcher state (owner / ca / reviewer)
        │   ├── design-system/
        │   │   └── layout/
        │   │       ├── AppShell.tsx  # Top navigation bar, sidebar, workspace tabs
        │   │       └── ...
        │   └── workspaces/
        │       ├── contract-intelligence/
        │       │   └── pages/
        │       │       ├── Dashboard.tsx      # Contract upload, metrics, contract list
        │       │       └── ContractDetail.tsx # Clause viewer, risk tags, redline generator
        │       ├── legal-notice-center/
        │       │   └── pages/
        │       │       ├── Dashboard.tsx      # Notice upload, paste text, urgency feed
        │       │       └── NoticeDetail.tsx   # Formal reply editor, regeneration
        │       ├── compliance-center/
        │       │   └── pages/
        │       │       └── Dashboard.tsx      # Dynamic statutory calendar, certificate upload
        │       ├── vendor-intelligence/
        │       │   └── pages/
        │       │       └── Dashboard.tsx      # GSTIN search, trust score gauge, audit history
        │       └── knowledge-hub/
        │           └── pages/
        │               └── Dashboard.tsx      # Company registration, vault, Risk Radar, Q&A
```

---

## 5. Database Architecture & Schema Reference

LegalOS enforces modular PostgreSQL schema namespacing:

```
PostgreSQL Database: legalos
├── Schema: core
│   ├── users                  (id: UUID PK, full_name, role, timestamps)
│   └── documents              (id: UUID PK, workspace, original_filename, storage_path, uploaded_by FK -> core.users.id, uploaded_at)
├── Schema: contract_intelligence
│   ├── contracts              (id: UUID PK, document_id FK -> core.documents.id [CASCADE], title, counterparty_name, status, created_at)
│   ├── clauses                (id: UUID PK, contract_id FK -> contracts.id [CASCADE], clause_index, raw_text, summary, risk_type, risk_score 0-100, qdrant_point_id, created_at)
│   └── negotiation_suggestions(id: UUID PK, clause_id FK -> clauses.id [CASCADE], suggestion_text, created_at)
├── Schema: legal_notice_center
│   ├── notices                (id: UUID PK, document_id FK -> core.documents.id [SET NULL], raw_text, notice_type, urgency, created_at)
│   └── draft_replies          (id: UUID PK, notice_id FK -> notices.id [CASCADE], reply_text, created_at)
├── Schema: compliance_center
│   ├── compliance_tasks       (id: UUID PK, title, category, due_date, status, description, penalty_desc, document_id FK, user_id FK, timestamps)
│   └── compliance_document_analyses (id: UUID PK, document_id FK [CASCADE, UNIQUE], authority, document_type, identifier_number, issue_date, expiry_date, status, risk_assessment, extracted_actions: JSONB, timestamps)
├── Schema: vendor_intelligence
│   └── vendor_checks          (id: UUID PK, gstin, company_name, is_valid, registration_date, trust_score, fraud_flagged, raw_mock_response: JSONB, checked_by FK, checked_at)
└── Schema: knowledge_hub
    ├── registered_companies   (id: UUID PK, gstin UNIQUE INDEX, legal_name, trade_name, entity_type, registration_date, taxpayer_type, status, state_jurisdiction, center_jurisdiction, principal_address: JSONB, nature_of_business: JSONB, raw_profile_response: JSONB, registered_by FK, timestamps)
    └── company_documents      (id: UUID PK, company_id FK -> registered_companies.id [CASCADE], document_id FK, title, document_category, summary, file_name, file_type, file_path, extracted_text, risk_analysis: JSONB, timestamps)
```

### Three-Tier Cascade Deletion
When an entity (e.g. Contract, Notice, or Company Document) is deleted, LegalOS executes a clean **three-tier deletion**:
1. Physical files are removed from local disk storage.
2. Vector points are deleted from Qdrant via payload filter (`document_id` or `company_id`).
3. PostgreSQL records and all cascaded children (`clauses`, `suggestions`, `replies`, `documents`) are purged.

---

## 6. Detailed Workspace Breakdown

### Workspace 1: Contract Intelligence Platform
- **Purpose**: High-speed contract parsing, clause-level risk quantification, and counter-proposal drafting.
- **Workflow**:
  1. User uploads a contract (`.pdf`, `.docx`, `.txt`, `.md`, max 10MB).
  2. The FastAPI endpoint immediately creates a stub in `core.documents` and `contract_intelligence.contracts` with status `processing` and returns HTTP 200 within ~50ms.
  3. `BackgroundTasks` executes `run_async_contract_analysis`:
     - PyMuPDF or `python-docx` extracts clean text.
     - Document metadata (Title, Counterparty) is extracted via LLM from the first 4,000 characters.
     - Chunker extracts individual clauses (or semantic paragraphs).
     - Local `SentenceTransformer` embeds clauses into 384-dimensional vectors.
     - Vectors are upserted into Qdrant collection `contract_clauses` tagged with `document_id`.
     - Gemini LLM iterates through clauses, outputting structured JSON: clause summary, risk category (`indemnification`, `termination`, `lock_in`, `penalty`, `none`), and a quantitative **Risk Score (0–100)**.
     - Status updates to `analyzed`.
  4. **Targeted Clause Redlining / Suggestion**:
     - User clicks a risky clause → triggers `/api/v1/contracts/{id}/clauses/{clause_id}/suggest`.
     - Qdrant runs semantic search scoped strictly to that `document_id` (`top_k=3`) to fetch surrounding context.
     - Gemini drafts a redline negotiation proposal favoring the SME's position.

### Workspace 2: Legal Notice Center
- **Purpose**: Triage and respond to legal demand notices, cease & desist letters, and tax notices.
- **Workflow**:
  1. User uploads a file or pastes notice text directly into the dashboard.
  2. Ingestion worker indexes text into Qdrant collection `legal_notices`.
  3. LLM classifies:
     - **Notice Type**: *Demand Notice*, *Cease & Desist*, *Tax Show-Cause*, *Breach of Contract*, *Employment Dispute*, *Summons*, *Other*.
     - **Urgency**: *Critical* (immediate statutory action required), *High*, *Medium*, *Low*.
  4. Auto-generates a formal Indian legal reply draft adhering to standard legal formatting (citing notice references, denying unfounded allegations, and setting counter-demands).
  5. Supports reply regeneration and draft history tracking.

### Workspace 3: Compliance Center & Statutory Calendar
- **Purpose**: Proactively track recurring Indian statutory filing deadlines and convert uploaded government notices/certificates into actionable tasks.
- **Core Capabilities**:
  1. **Dynamic Statutory Calendar**:
     - Generates deadline checklists customized to business entity type:
       - **Private Limited (Pvt Ltd)**: Monthly GST (GSTR-1, GSTR-3B), Monthly TDS deposit, Monthly PF/ESI, Quarterly TDS return (Form 24Q/26Q), Advance Tax installments (June 15, Sept 15, Dec 15, Mar 15), Annual MCA AOC-4 (Financials) and MGT-7 (Annual Return), DIR-3 KYC for directors, and Annual Income Tax return (ITR-6).
       - **Limited Liability Partnership (LLP)**: GST, TDS, PF/ESI, Advance Tax, LLP Form 11 (Annual Return) and Form 8 (Statement of Account & Solvency), ITR-5.
       - **Partnership Firm**: GST, TDS, PF/ESI, Advance Tax, ITR-5.
       - **Sole Proprietorship**: GST, Monthly TDS, PF/ESI (if registered), Advance Tax, Individual/Proprietorship ITR-3/ITR-4.
  2. **GSTIN Auto-Configuration**:
     - Endpoint `/api/v1/compliance/init-by-gstin` inspects the 15-character GSTIN, queries the tax registry, extracts Constitution of Business (`ctb`), maps it to the matching entity type, and auto-populates the statutory calendar in one click.
  3. **Compliance Document Analyzer**:
     - Users upload compliance certificates (e.g., FSSAI, Pollution Control, Factory License, GST Registration, Tax Assessment orders).
     - PyMuPDF extracts text; Gemini extracts issuing authority, document type, registration number, issue/expiry dates, risk assessment, and concrete action items.
     - Action items automatically convert into tracked compliance tasks with penalty descriptions and due dates.

### Workspace 4: Vendor Intelligence & Verification Engine
- **Purpose**: Prevent vendor fraud and safeguard Input Tax Credit (ITC) by verifying vendor GSTINs against live government records.
- **Workflow & Architecture**:
  1. **Live Sandbox.co.in Integration**:
     - Communicates with official GSTIN search endpoints.
     - **Token Lifecycle Management**: Caches JWT access tokens in memory for 23 hours. On `401 Unauthorized` responses, automatically refreshes the token and retries the request seamlessly.
     - **Mock Fallback**: If Sandbox credentials are not configured or offline, falls back seamlessly to an internal mock provider.
  2. **Dynamic Trust Score & Fraud Detection**:
     - Inspects taxpayer status: `Active`, `Cancelled`, `Suspended`.
     - Checks taxpayer type: Regular vs. Composition.
     - Computes quantitative **Trust Score (0–100)**: Active vendor = 95+ score; Suspended/Cancelled = 20 score + `fraud_flagged=True`.
  3. **Audit Logging**:
     - Every vendor check is logged in `vendor_intelligence.vendor_checks` with full raw response JSON for statutory audit defense.

### Workspace 5: Knowledge Hub & Ground Truth Vault
- **Purpose**: Enterprise repository for registered companies, organizational documents (policies, employee handbooks, board resolutions, NDAs), automated risk analysis, and strict Ground-Truth RAG Q&A.
- **Key Features**:
  1. **Company Profiling & Registration**:
     - Previews and registers organizations using 15-character GSTIN.
     - Captures legal name, trade name, constitution, tax jurisdiction (State & Center), principal place of business, and nature of business activities.
  2. **Multi-Format Document Vault**:
     - Supports PDF, DOCX, CSV, Excel (`.xlsx`, `.xls`), TXT, and Markdown files.
     - Clean text parsing, non-printable unicode stripping, and storage partitioning (`storage/knowledge_hub/{company_id}/`).
  3. **AI Document Risk & Compliance Radar**:
     - Synchronously analyzes uploaded documents upon ingestion.
     - Outputs structured JSON: `risk_score` (0–100), document classification, `critical_clauses` (with severity HIGH/MEDIUM), `compliance_gaps`, `strengths`, and actionable `suggested_fixes`.
  4. **Strict Ground-Truth RAG Q&A**:
     - User queries the company's knowledge base.
     - Hybrid retrieval: Qdrant semantic vector search on collection `knowledge_base` (score threshold `0.25`) + fallback paragraph keyword ranking over stored text.
     - Strict grounding prompt: AI must ONLY use the provided document context and GST profile. If the answer is not present, it responds: *"The uploaded documents do not contain information to answer this question."* Hallucinations are strictly prevented. Returns exact document citations and matching text excerpts.

---

## 7. Authentication & Role-Based Access Control (RBAC)

To allow seamless local testing and multi-persona evaluation, LegalOS includes a **Role Simulator**:
- **Available Personas**:
  - `business_owner` ("Rajesh Kumar", ID: `11111111-1111-1111-1111-111111111111`): Focuses on financial exposure, high-level risks, and filing deadlines.
  - `ca` ("Anjali Sharma", ID: `22222222-2222-2222-2222-222222222222`): Focuses on GST/TDS filings, MCA compliance, and tax audits.
  - `legal_reviewer` ("Vikram Mehta", ID: `33333333-3333-3333-3333-333333333333`): Focuses on clause redlines, notice replies, and indemnity liabilities.
- **Implementation**:
  - The frontend `AuthContext` stores the active role in `localStorage` (`legalos_fake_role`).
  - Axios automatically attaches the header: `X-User-Role: <owner|ca|reviewer>`.
  - FastAPI dependency `get_current_user` extracts the header (or query param) and returns the populated `UserStub`.
  - Application startup automatically seeds these 3 mock users in `core.users`.

---

## 8. API Endpoint Reference

### Contract Intelligence (`/api/v1/contracts`)
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/upload` | Upload contract file (PDF/DOCX/TXT), creates DB stub, triggers background RAG analysis |
| `GET` | `/` | List all uploaded contracts with risk counts and processing status |
| `GET` | `/{id}` | Get full contract breakdown with all clause scores and annotations |
| `POST` | `/{id}/clauses/{clause_id}/suggest` | Generate targeted RAG negotiation redline for a clause |
| `DELETE` | `/{id}` | Delete contract, physical file, database rows, and Qdrant vectors |

### Vendor Intelligence (`/api/v1/vendors`)
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/verify` | Verify GSTIN via Sandbox.co.in or mock fallback, compute trust score, log audit |
| `GET` | `/` | List historical vendor verification audit logs |

### Legal Notice Center (`/api/v1/notices`)
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/analyze/file` | Upload notice document and run background classification & reply drafting |
| `POST` | `/analyze/text` | Paste raw notice text and run background classification & reply drafting |
| `GET` | `/` | List all legal notices with urgency and type tags |
| `GET` | `/{id}` | Get full notice profile and generated reply drafts |
| `POST` | `/{id}/regenerate` | Regenerate formal legal reply draft via RAG retrieval |
| `DELETE` | `/{id}` | Delete legal notice, replies, and associated vectors |

### Compliance Center (`/api/v1/compliance`)
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/tasks` | List all statutory compliance tasks for current user |
| `POST` | `/tasks` | Create a custom compliance task |
| `PUT` | `/tasks/{task_id}` | Update compliance task status or details |
| `DELETE` | `/tasks/{task_id}` | Delete a compliance task |
| `POST` | `/init` | Auto-populate statutory checklist based on entity type (`pvt_ltd`, `llp`, etc.) |
| `POST` | `/init-by-gstin` | Auto-detect entity type from GSTIN registry and populate checklist |
| `POST` | `/upload` | Upload compliance certificate/notice, extract metadata & action items |
| `GET` | `/analyses` | List historical compliance document analysis reports |
| `GET` | `/analyses/{id}` | Get detailed report for a compliance document |

### Knowledge Hub (`/api/v1/knowledge`)
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/companies/preview` | Preview live GSTIN taxpayer profile without saving |
| `POST` | `/companies` | Register company by GSTIN, fetch profile, save to DB |
| `GET` | `/companies` | List all registered companies |
| `GET` | `/companies/{company_id}` | Get detailed company profile with uploaded documents |
| `DELETE` | `/companies/{company_id}` | Unregister company, delete storage files, and purge Qdrant vectors |
| `POST` | `/documents/upload` | Upload document to company vault, parse, chunk, embed in Qdrant, run Risk Radar |
| `DELETE` | `/documents/{document_id}` | Delete company document, disk file, and Qdrant points |
| `POST` | `/ask` | Ask AI assistant using company documents as strict Ground Truth |

### System & Health (`/`)
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check endpoint returning status and active LLM provider |

---

## 9. Environment Variables & Configuration

Backend configuration is handled via Pydantic `BaseSettings` reading from `.env`:

| Variable | Default Value | Description |
|----------|---------------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://legalos:legalos_secure_password@localhost:5432/legalos` | PostgreSQL connection string using `asyncpg` |
| `QDRANT_URL` | `http://localhost:6333` (Docker: `http://qdrant:6333`) | Qdrant vector database URL |
| `QDRANT_API_KEY` | `None` | Optional Qdrant API key for cloud instances |
| `LLM_PROVIDER` | `gemini` | Active LLM provider (`gemini` or `local`) |
| `GEMINI_API_KEY` | *(Required for Gemini)* | Google Gemini API key |
| `FRONTEND_URL` | `http://localhost:5173` | Allowed CORS origin(s) |
| `HF_HOME` | `./model_cache` | Cache path for HuggingFace embeddings |
| `SENTENCE_TRANSFORMERS_HOME` | `./model_cache` | Cache path for SentenceTransformer weights |
| `ENV` | `dev` | Environment flag (`dev` or `prod`) |
| `SANDBOX_CO_MODE` | `mock` (`mock` or `live`) | Mode for Sandbox.co.in GSTIN verification |
| `SANDBOX_CO_API_KEY` | `None` | Sandbox.co.in client API key |
| `SANDBOX_CO_API_SECRET` | `None` | Sandbox.co.in client secret |
| `SANDBOX_CO_BASE_URL` | `https://api.sandbox.co.in` | Sandbox.co.in base URL |

Frontend environment:
| Variable | Default Value | Description |
|----------|---------------|-------------|
| `VITE_API_URL` | `http://localhost:8000` | Backend API base URL |

---

## 10. How to Run LegalOS Locally

### Option A: Docker Compose (Full Stack)
```bash
# In the legalos/ directory
docker compose up --build
```
- Frontend: `http://localhost:5173`
- Backend API Docs: `http://localhost:8000/docs`
- Qdrant Dashboard: `http://localhost:6335/dashboard`
- PostgreSQL: Port `5435`

### Option B: Local Development

#### 1. Start Infrastructure (PostgreSQL & Qdrant)
```bash
docker compose up db qdrant -d
```

#### 2. Backend Setup
```bash
cd legalos/backend

# Install dependencies using Poetry
poetry install

# Run database migrations
poetry run alembic upgrade head

# Start FastAPI server
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 3. Frontend Setup
```bash
cd legalos/frontend

# Install dependencies
npm install

# Run Vite dev server
npm run dev
```

---

## 11. Engineering Guidelines & Conventions for AI Coding

When assisting with code changes in this repository, always adhere to the following rules:

1. **Async PostgreSQL Operations**:
   - Always use `AsyncSession` with `await session.execute(...)`, `await session.commit()`, etc.
   - Never use synchronous DB queries.
2. **Non-Blocking LLM Calls**:
   - In FastAPI routes or async service functions, **never** call synchronous `generate()` directly.
   - Always call `await generate_async(...)` to prevent blocking the asyncio event loop during network requests to the LLM.
3. **Strict JSON Schema Enforcement**:
   - When requesting structured output from Gemini, use `json_mode=True`.
   - Strip code fences (````json ... ````) defensively before `json.loads()`.
   - Always provide fallback dictionary structures if the LLM produces malformed output or fails.
4. **Vector Search Isolation**:
   - Always include filter conditions (`document_id` or `company_id`) in Qdrant queries to eliminate cross-document or cross-tenant context leakage.
5. **Three-Tier Cascade Deletion**:
   - When writing deletion logic for any document-bearing entity, clean up in all three layers: local disk storage, Qdrant vectors, and PostgreSQL database rows.
6. **Ground-Truth RAG Rigor**:
   - For Knowledge Hub Q&A, instruct the model to answer **strictly** from provided document context. If information is absent, return the exact required fallback message rather than hallucinating external knowledge.
7. **Frontend API Interceptor**:
   - All backend API calls from the frontend must go through `apiClient` (`src/api/client.ts`) so the `X-User-Role` header is properly attached.
8. **Entity Type Mapping**:
   - When mapping Indian GSTIN `ctb` (Constitution of Business) to statutory types:
     - `Private Limited Company` / `Public Limited Company` → `pvt_ltd`
     - `Limited Liability Partnership` → `llp`
     - `Partnership` → `partnership`
     - `Proprietorship` → `sole_proprietorship`
