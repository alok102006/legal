> **OUTDATED - read docs/PROGRESS.md and docs/IMPLEMENTATION_PLAN.md instead.** This file describes the earlier prototype and contains claims that are not true of the current code (for example fake status badges, hybrid retrieval, mock-free vendor checks).

# LegalOS — Comprehensive Architecture Document

> **Version:** 1.0.0 · **Last updated:** August 2026  
> **Stack:** FastAPI · PostgreSQL · Qdrant · React/TypeScript · Gemini 2.5 Flash · SentenceTransformers · Docker

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [High-Level Architecture Diagram](#2-high-level-architecture-diagram)
3. [Technology Stack & Infrastructure](#3-technology-stack--infrastructure)
4. [Backend — Application Bootstrap](#4-backend--application-bootstrap)
5. [Core Engine — AI/RAG Pipeline](#5-core-engine--airag-pipeline)
6. [Shared Infrastructure](#6-shared-infrastructure)
7. [Workspace Modules](#7-workspace-modules)
8. [Frontend Architecture](#8-frontend-architecture)
9. [Data Models & Database Schemas](#9-data-models--database-schemas)
10. [End-to-End Data Flow Walkthroughs](#10-end-to-end-data-flow-walkthroughs)
11. [API Endpoint Reference](#11-api-endpoint-reference)
12. [What Problem Does LegalOS Solve?](#12-what-problem-does-legalos-solve)
13. [Future Evolution Roadmap](#13-future-evolution-roadmap)

---

## 1. System Overview

**LegalOS** is a full-stack AI-powered legal operating system built specifically for **Indian SMEs (Small and Medium Enterprises)**. It consolidates four high-stakes legal functions into a single unified platform:

| Workspace | Purpose |
|-----------|---------|
| **Contract Intelligence** | Upload contracts → auto-parse clauses → risk-score each clause → generate negotiation counter-proposals |
| **Legal Notice Center** | Upload legal notices → classify urgency & type → auto-draft formal reply letters |
| **Compliance Center** | Track Indian statutory deadlines (GST, TDS, MCA, PF/ESI) → upload compliance certificates → AI extracts action items |
| **Vendor Intelligence** | Verify vendor GSTIN in real-time → assess fraud risk → build audit trail |

The system is grounded in a **Retrieval-Augmented Generation (RAG)** architecture: documents are parsed, chunked, embedded into a vector database, and then retrieved as semantic context to ground every LLM response.

---

## 2. High-Level Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React + Vite)                      │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │
│  │  Contract  │  │ Legal Notice │  │  Compliance  │  │  Vendor   │  │
│  │Intelligence│  │   Center     │  │   Center     │  │  Intel.   │  │
│  └────────────┘  └──────────────┘  └──────────────┘  └───────────┘  │
│                        AuthContext (Role Switcher)                    │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ HTTP / REST (CORS)
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       BACKEND (FastAPI / Uvicorn)                    │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                   API Routers (/api/v1/...)                   │    │
│  │  /contracts   /notices   /compliance   /vendors               │    │
│  └───────────────────────────┬──────────────────────────────────┘    │
│                              │ FastAPI DI (db_session, get_user)     │
│  ┌───────────────────────────▼──────────────────────────────────┐    │
│  │                     Service Layer                             │    │
│  │  (Business logic, background tasks, LLM orchestration)       │    │
│  └─────────────┬────────────────────────────┬────────────────── ┘    │
│                │                            │                         │
│  ┌─────────────▼───────────┐   ┌───────────▼──────────┐             │
│  │   CORE RAG ENGINE       │   │   SHARED INFRA        │             │
│  │  document_parser        │   │  auth_service         │             │
│  │  chunker                │   │  db/session           │             │
│  │  embedder               │   │  file_storage         │             │
│  │  rag_pipeline           │   │  exceptions           │             │
│  │  retrieval_service      │   └──────────────────────┘             │
│  │  llm_client             │                                         │
│  └─────────────┬───────────┘                                         │
│       ┌────────┴──────────┐                                          │
│       │   LLM Providers   │                                          │
│       │  [Gemini 2.5]     │                                          │
│       │  [Local/Ollama]   │                                          │
│       └───────────────────┘                                          │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
          ┌────────────────────┼──────────────────────┐
          ▼                    ▼                       ▼
   ┌────────────┐    ┌──────────────┐    ┌────────────────────┐
   │ PostgreSQL  │    │    Qdrant    │    │  Sandbox.co.in API │
   │ (Metadata, │    │ (384-dim     │    │  (Live GSTIN lookup│
   │  Audit     │    │  cosine      │    │   + JWT auth)      │
   │  Trail)    │    │  vectors)    │    └────────────────────┘
   └────────────┘    └──────────────┘
```

---

## 3. Technology Stack & Infrastructure

### Backend
| Layer | Technology | Version |
|-------|-----------|---------|
| Web framework | FastAPI | ^0.110.0 |
| ASGI server | Uvicorn (standard) | ^0.28.0 |
| ORM | SQLAlchemy (asyncio) | ^2.0.28 |
| DB migrations | Alembic | ^1.13.1 |
| Async DB driver | asyncpg | ^0.29.0 |
| Vector DB client | qdrant-client | ^1.8.0 |
| LLM | google-genai (Gemini 2.5 Flash) | * |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | ^2.5.1 |
| PDF parsing | PyMuPDF (fitz) | ^1.23.26 |
| DOCX parsing | python-docx | ^1.1.0 |
| HTTP client | httpx | ^0.27.0 |
| File uploads | python-multipart | ^0.0.9 |
| Async file I/O | aiofiles | ^23.2.1 |
| Schema validation | Pydantic v2 | ^2.6.4 |

### Frontend
| Layer | Technology |
|-------|-----------|
| Framework | React 18 + TypeScript |
| Build tool | Vite |
| Routing | React Router v6 |
| Styling | TailwindCSS |
| State / Auth | React Context API |

### Infrastructure (Docker Compose)
| Service | Image | Port Mapping |
|---------|-------|------|
| PostgreSQL 15 | postgres:15-alpine | 5435 → 5432 |
| Qdrant | qdrant/qdrant:latest | 6335 → 6333 |
| Backend | Custom Dockerfile | 8000 → 8000 |
| Frontend | Custom Dockerfile | 5173 → 5173 |

---

## 4. Backend — Application Bootstrap

### 4.1 `main.py` — Lifespan & App Factory

**Objective:** Create, configure, and boot the FastAPI application. Establish application-wide services during startup and gracefully shut them down on exit.

#### `lifespan(app)` — Async Context Manager

```
STARTUP sequence (runs before serving any requests):

  Step 1 → get_embedder()
    Warms up the SentenceTransformer singleton.
    Downloads model from HuggingFace on first run (~60s).
    Loads from local ./model_cache on subsequent runs (~1-2s).
    In prod mode, a failure here crashes startup intentionally.

  Step 2 → init_collections()
    Idempotently creates Qdrant vector collections:
      - "contract_clauses"  (384-dim, COSINE distance)
      - "legal_notices"     (384-dim, COSINE distance)
    Safe to call multiple times — no-op if already created.

  Step 3 → Seed mock users into PostgreSQL
    Three users seeded: owner / ca / reviewer
    Only inserts if not already present (idempotent).
    Required so FK constraints (uploaded_by, user_id) work.

TEARDOWN → logs shutdown, async context cleanup.
```

**CORS:** Dynamic origin list from `settings.frontend_url` (comma-separated for multi-origin support).

**Exception Handler:** Catches all `LegalOSException` subclasses → structured JSON:
```json
{"detail": "...", "timestamp": 1754294100.0, "path": "/api/v1/..."}
```

**Health Check:** `GET /health` → returns `{status, timestamp, provider}` for Docker probes.

---

### 4.2 `config.py` — Settings Singleton

**Objective:** Centralize all environment-variable configuration into a single `Settings` object, loaded once at import time using pydantic-settings.

```python
Settings fields:
  database_url          # PostgreSQL asyncpg connection string
  qdrant_url            # Qdrant HTTP URL
  qdrant_api_key        # Optional (for Qdrant Cloud)
  llm_provider          # "gemini" | "local"
  gemini_api_key        # Google Gemini API key
  frontend_url          # CORS allowed origins (comma-separated)
  hf_home               # HuggingFace model cache path
  sentence_transformers_home
  env                   # "dev" | "prod"
  sandbox_co_mode       # "mock" | "live"
  sandbox_co_api_key    # Sandbox.co.in credentials
  sandbox_co_api_secret
  sandbox_co_base_url
```

All settings are **debug-printed at startup** to make misconfiguration immediately visible. The `settings` singleton is imported directly across the entire app.

---

### 4.3 `dependencies.py` — FastAPI DI Layer

**Objective:** Reusable dependency injection functions for database sessions and user resolution.

#### `get_current_user(x_user_role, role)` → `UserStub`

```
Resolution priority:
  1. X-User-Role HTTP header  (e.g., "owner", "ca", "reviewer")
  2. ?role= query parameter
  3. Default fallback: "owner" (business owner)

→ Calls auth_service.get_user_by_role(resolved_role)
→ Returns a UserStub(id, full_name, role)
```

This is a **mock auth system** — no JWT validation exists yet. In production, this would decode/verify a JWT and query the database for the real user.

---

## 5. Core Engine — AI/RAG Pipeline

The `app/core/` directory is the **heart of LegalOS**. It provides the complete AI stack as reusable services.

```
core/
  embeddings/embedder.py        ← SentenceTransformer singleton
  llm/
    llm_client.py               ← Provider-agnostic LLM router
    providers/gemini_provider.py ← Google Gemini 2.5 Flash
    providers/local_provider.py  ← Ollama / local LLM stub
    prompts/                    ← All prompt templates
  rag/
    document_parser.py          ← PDF / DOCX / TXT → raw text
    chunker.py                  ← Text → semantic chunks
    rag_pipeline.py             ← Ingest + retrieve-and-generate
  vectorstore/
    qdrant_client.py            ← Qdrant connection singleton
    collections.py              ← Collection initialization
    retrieval_service.py        ← Upsert, search, delete operations
```

---

### 5.1 Document Parser (`core/rag/document_parser.py`)

**Objective:** Convert raw file bytes into a plain-text string, regardless of file format.

| Function | Input | Output | Library |
|----------|-------|--------|---------|
| `parse_pdf(file_bytes)` | `bytes` | `str` | PyMuPDF — opens PDF stream, iterates pages calling `page.get_text()` |
| `parse_docx(file_bytes)` | `bytes` | `str` | python-docx — wraps in BytesIO, extracts non-empty paragraphs |
| `parse_txt(file_bytes)` | `bytes` | `str` | Built-in — decodes UTF-8, ignoring errors |
| `parse_document(file_bytes, filename)` | `bytes`, `str` | `str` | **Dispatcher** — reads extension, routes to matching parser |

**Supported formats:** `.pdf`, `.docx`, `.txt`, `.md`

**Error handling:** All parsers raise `BadRequestException` (HTTP 400) on failure, surfacing cleanly to the API client.

---

### 5.2 Chunker (`core/rag/chunker.py`)

**Objective:** Split extracted document text into semantically coherent chunks suitable for vector embedding and retrieval.

#### `clean_text(text)` → `str`
Normalizes whitespace: collapses multiple spaces/tabs to single space, collapses multiple newlines.

#### `chunk_by_clause(text, max_chars=4000)` → `List[Dict]`

Legal contract-aware chunking:
```
1. Define clause header regex patterns:
   - "Section 2.1 Payment Terms"
   - "ARTICLE IV TERMINATION"  
   - "1. Scope of Work"
   - All-uppercase headings like "INDEMNIFICATION:"

2. Iterate lines:
   - Clause header matched → flush current chunk, start new chunk
   - Current chunk exceeds max_chars → flush and start new chunk

3. Return list of {"clause_index": N, "text": "..."}
```

Each chunk's `clause_index` links the SQL record to its Qdrant vector point.

#### `chunk_by_paragraph(text, max_chars=1500)` → `List[Dict]`

Standard paragraph chunking:
```
1. Split on double-newlines (paragraph boundaries)
2. Clean each paragraph
3. Paragraphs > max_chars → further split into character windows
4. Return list of {"clause_index": N, "text": "..."}
```

Used for notices and compliance documents where legal clause structure doesn't apply.

#### `chunk_document(text, strategy="clause")` → `List[Dict]`

Dispatcher:
- `"clause"` → `chunk_by_clause()`
- `"paragraph"` → `chunk_by_paragraph()`
- Other values → raises `ValueError`

---

### 5.3 Embedder (`core/embeddings/embedder.py`)

**Objective:** Provide a **process-wide singleton** generating 384-dimensional dense vector embeddings using `sentence-transformers/all-MiniLM-L6-v2`.

#### `class Embedder`

```python
__init__():
  # Set HF_HOME and SENTENCE_TRANSFORMERS_HOME env vars
  # to point to ./model_cache (local project directory)
  # Check if cache exists (model already downloaded)
  # Load SentenceTransformer from cache or download (~60MB)
  # Log load time (1-2s cached, 30-60s first download)

embed(texts: list[str]) → list[list[float]]:
  # Batch encode using model.encode()
  # Returns list of 384-float vectors (one per text)
  # Returns [] for empty input (short-circuit guard)
```

#### `get_embedder()` → `Embedder` (Singleton Factory)

```python
_embedder_instance = None  # module-level global

def get_embedder():
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = Embedder()  # load once per process
    return _embedder_instance
```

**Why singleton?** SentenceTransformer takes 1-2s to load and uses ~90MB RAM. Loading once at startup and reusing across all requests is essential for performance.

---

### 5.4 Vector Store (`core/vectorstore/`)

#### `qdrant_client.py` — Connection Singleton

```python
get_qdrant_client() → QdrantClient:
  # Lazily initializes using qdrant_url + qdrant_api_key from settings
  # Returns the singleton client
```

#### `collections.py` — `init_collections()`

**Objective:** Idempotently ensure all required Qdrant collections exist at startup.

```
Defined collections:
  "contract_clauses": size=384, distance=COSINE
  "legal_notices":    size=384, distance=COSINE

For each collection:
  collection_exists() → if False → create_collection()
                      → if True  → log "already active" (no-op)
  On error → raise (hard fail — these collections are mission-critical)
```

#### `retrieval_service.py` — Core Vector Operations

##### `upsert_chunks(collection, items: list[ChunkRecord])` → `None`

**Objective:** Index embedded document chunks into Qdrant.

```
1. Convert ChunkRecord list → list[PointStruct]
   Each: id (UUID str), vector (list[float]), payload (dict)
2. client.upsert(collection_name, points, wait=True)
   wait=True ensures synchronous confirmation before returning
```

Payload per point: `{document_id, clause_index, text, ...workspace metadata}`

##### `search(collection, query, top_k=5, filters=None)` → `list[RetrievedChunk]`

**Objective:** Semantic similarity search to retrieve relevant chunks for a query.

```
1. Embed query string → single 384-dim vector (via get_embedder())
2. Parse filters dict into Qdrant Filter:
   Each key-value pair → FieldCondition(key, MatchValue(value))
   Multiple conditions joined with must (logical AND)
3. client.query_points(collection, query_vector, filter, limit=top_k)
4. Map results → list[RetrievedChunk(id, score, payload)]
```

**Why filters?** Searches are scoped to a specific `document_id` to prevent cross-document contamination of RAG context.

##### `delete_by_document(collection, document_id)` → `None`

**Objective:** Delete all vector points for a document when it's removed from the system.

```python
client.delete(collection_name,
    points_selector=Filter(must=[
        FieldCondition("document_id", MatchValue(document_id))
    ]))
```

---

### 5.5 RAG Pipeline Orchestrator (`core/rag/rag_pipeline.py`)

**Objective:** The two core RAG operations — **ingestion** and **retrieval-augmented generation** — as reusable functions for any workspace.

#### Workspace → Collection Mapping
```python
WORKSPACE_COLLECTIONS = {
    "contract_intelligence": "contract_clauses",
    "legal_notice_center":   "legal_notices",
}
```

#### `ingest_document(file_bytes, filename, workspace, metadata)` → `str`

Full ingestion pipeline — parse → chunk → embed → index:

```
Step 1: Resolve collection from workspace key
Step 2: Extract/generate document_id from metadata
Step 3: parse_document(file_bytes, filename) → raw text
        Raises BadRequestException if empty

Step 4: chunk_document(text, strategy)
        strategy = "clause"     → contract_intelligence
        strategy = "paragraph"  → all other workspaces

Step 5: get_embedder().embed(chunk_texts)
        → list of 384-dim float vectors, one per chunk

Step 6: For each (chunk, vector):
        - Generate unique point_id (UUID)
        - Build payload: {document_id, clause_index, text, ...metadata}
        - Store point_id back into chunk dict (for SQL FK linking)
        - Create ChunkRecord(id, vector, payload)

Step 7: retrieval_service.upsert_chunks(collection, records)

Step 8: Store processed_chunks back into metadata dict
        (calling service reads chunk["point_id"] for DB FK linking)

Step 9: Return document_id
```

#### `retrieve_and_generate(query, workspace, system_prompt, top_k, filters, json_mode)` → `str`

Full RAG query — embed → retrieve → build context → generate:

```
Step 1: Resolve collection from workspace
Step 2: retrieval_service.search(collection, query, top_k, filters)
        → list[RetrievedChunk] sorted by cosine similarity

Step 3: Build context string:
        No results → "No reference text available."
        Results    → "--- Chunk N (Clause Index: X) ---\n{text}\n\n..."

Step 4: Construct user_prompt:
        "Use the following legal context to address the query.
         ### Legal Context: {context}
         ### User Query: {query}
         Answer:"

Step 5: llm_client.generate(prompt, system=system_prompt, json_mode, workspace)
        → LLM response string
```

---

### 5.6 LLM Client (`core/llm/llm_client.py`)

**Objective:** Single, provider-agnostic entry point for all LLM calls. Any workspace calls `llm_client.generate(...)` without knowing which AI provider is configured.

#### `generate(prompt, system="", json_mode=False, workspace="")` → `str`

```
1. Read settings.llm_provider ("gemini" | "local")
2. Log: timestamp, workspace name, provider, json_mode
3. If provider == "gemini" → generate_gemini(prompt, system, json_mode)
4. If provider == "local"  → generate_local(prompt, system, json_mode)
5. Other values → raise ValueError("Unsupported LLM_PROVIDER")
6. Log: elapsed time on success
7. On error: log elapsed + re-raise
```

`workspace` is used for logging/telemetry only — it doesn't change model behavior.

---

### 5.7 LLM Providers

#### Gemini Provider (`core/llm/providers/gemini_provider.py`)

```python
get_gemini_client() → genai.Client:
  # Lazily instantiates using GEMINI_API_KEY
  # Returns singleton client

generate_gemini(prompt, system, json_mode) → str:
  # Model: "gemini-2.5-flash" (fast, cost-efficient)
  # Config:
  #   system_instruction = system (if provided)
  #   response_mime_type = "application/json" (json_mode=True)
  #                      = "text/plain"        (json_mode=False)
  # Raises RuntimeError if response.text is empty
```

**Why json_mode?** Forces Gemini to output valid JSON — critical for clause analysis, metadata extraction, and compliance parsing where the response is fed directly to `json.loads()`.

#### Local Provider (`core/llm/providers/local_provider.py`)

```python
generate_local(prompt, system, json_mode) → str:
  # POST http://localhost:11434/v1/chat/completions (Ollama)
  # Model: "llama3" (default)
  # Timeout: 5 seconds
  # On failure → returns mocked fallback JSON/text response
```

Enables **fully offline development** without a Gemini API key. The fallback mock keeps the app functional even with no local model running.

---

### 5.8 LLM Prompts

All prompts are isolated in `core/llm/prompts/` as constants, cleanly separating prompt engineering from business logic.

#### Contract Intelligence Prompts

| Constant | LLM Role | JSON Output Schema |
|----------|----------|-------------------|
| `CONTRACT_METADATA_SYSTEM` | Expert contracts analyst | `{"title": "...", "counterparty_name": "..."}` |
| `CLAUSE_ANALYSIS_SYSTEM` | Indian contract law compliance officer | `{"summary": "...", "risk_type": "penalty\|lock_in\|indemnity\|termination\|none", "risk_score": 0-100}` |
| `NEGOTIATION_SUGGESTION_SYSTEM` | Commercial attorney for Indian SME | Free-text counter-proposal |

#### Legal Notice Prompts

| Constant | LLM Role | JSON Output Schema |
|----------|----------|-------------------|
| `LEGAL_NOTICE_ANALYSIS_SYSTEM` | Expert legal analyst (Indian corporate law) | `{"notice_type": "demand\|show_cause\|summons\|other", "urgency": "low\|medium\|high\|critical", "reply_text": "..."}` |

#### Compliance Center Prompts

| Constant | LLM Role | JSON Output Schema |
|----------|----------|-------------------|
| `COMPLIANCE_DOCUMENT_ANALYSIS_SYSTEM` | Indian regulatory compliance officer | `{"authority", "document_type", "identifier_number", "issue_date", "expiry_date", "status", "risk_assessment", "action_items": [...]}` |

---

## 6. Shared Infrastructure

### 6.1 Database Layer (`shared/db/`)

#### `session.py` — Async Engine & Session Factory

```python
engine = create_async_engine(
    settings.database_url,
    echo=True  # in dev mode — logs all SQL
)

async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False  # prevents lazy-load issues in async
)

async def get_db_session() → AsyncGenerator[AsyncSession, None]:
    # Yields a session per request (FastAPI DI)
    # Closes session in finally block (even on error)
```

#### `models.py` — Core Database Models

```
core.users
  id (UUID PK), full_name, role, created_at, updated_at

core.documents
  id (UUID PK), workspace, original_filename, storage_path,
  uploaded_by (FK → users.id), uploaded_at
```

`Document` is the **central entity** all workspaces reference. Every uploaded file creates a Document, and each workspace creates its own linked record.

#### `mixins.py` — Reusable Model Mixins

```python
UUIDPrimaryKeyMixin:
    id = UUID primary key, default=uuid.uuid4

TimestampMixin:
    created_at = server_default now()
    updated_at = onupdate func.now()
```

---

### 6.2 Auth Service (`shared/auth/auth_service.py`)

**Objective:** Stub authentication mapping role names to pre-defined user profiles.

```python
MOCK_USERS = {
    "owner":    UserStub(id=UUID("1111..."), full_name="Rajesh Kumar",  role="business_owner"),
    "ca":       UserStub(id=UUID("2222..."), full_name="Anjali Sharma", role="ca"),
    "reviewer": UserStub(id=UUID("3333..."), full_name="Vikram Mehta",  role="legal_reviewer"),
}

def get_user_by_role(role: str) → Optional[UserStub]:
    return MOCK_USERS.get(role, MOCK_USERS["owner"])  # defaults to owner
```

These three users are seeded into PostgreSQL at startup so all FK constraints remain valid.

---

### 6.3 Exception Hierarchy (`shared/exceptions.py`)

```
LegalOSException (HTTPException)
  ├── BadRequestException     (400) — Invalid input, unsupported file type
  ├── NotFoundException       (404) — Contract/notice/task not found
  ├── UnauthorizedException   (401) — Auth failure (future)
  ├── ForbiddenException      (403) — Permission denied (future)
  └── InternalServerException (500) — Unexpected server errors
```

All caught by global `legalos_exception_handler` in `main.py`.

---

### 6.4 File Storage (`shared/storage/file_storage.py`)

**Objective:** Persist uploaded file bytes to local filesystem under `uploads/`.

```
save_file(filename, file_bytes) → str:
  - Generates unique path: uploads/<workspace>/<uuid>_<filename>
  - Creates parent directories (aiofiles)
  - Writes file bytes asynchronously
  - Returns storage_path string for DB recording
```

> **Production note:** Replace with S3/GCS/Azure Blob for scalability.

---

## 7. Workspace Modules

Each workspace follows an identical **4-layer architecture**:

```
workspaces/<name>/
  models.py      ← SQLAlchemy ORM models (DB tables)
  schemas.py     ← Pydantic schemas (request/response validation)
  repository.py  ← Pure DB operations (no business logic)
  router.py      ← FastAPI route handlers (HTTP layer)
  service.py     ← Business logic, LLM orchestration, background workers
```

---

### 7.1 Contract Intelligence Workspace

**Objective:** AI-powered contract analysis — extract clauses, score risk, generate negotiation counter-proposals.

#### `create_and_start_analysis(session, file_bytes, filename, user_id)` → `Contract`

Synchronous portion — returns immediately to HTTP client:
```
1. file_storage.save_file() → persist to disk
2. INSERT core.documents
3. INSERT contract_intelligence.contracts (status="processing")
4. commit + refresh
5. Return contract stub
```

#### `run_async_contract_analysis(contract_id, file_bytes, filename, document_id)` → `None`

Background task — runs after HTTP response is sent:
```
1. rag_pipeline.ingest_document(workspace="contract_intelligence")
   → parse → chunk_by_clause → embed → upsert("contract_clauses")
   → metadata["processed_chunks"] now has chunk data + point_ids

2. For EACH chunk:
   a. CLAUSE_ANALYSIS_USER.format(clause_text=chunk["text"])
   b. llm_client.generate(..., json_mode=True)
      → {"summary", "risk_type", "risk_score"}
   c. INSERT clause(contract_id, clause_index, raw_text,
                    summary, risk_type, risk_score, qdrant_point_id)

3. CONTRACT_METADATA_USER.format(document_text=first_4000_chars)
   llm_client.generate(..., json_mode=True)
   → {"title", "counterparty_name"}

4. UPDATE contract(title, counterparty, status="analyzed")
5. session.commit()

On error:
   rollback → UPDATE contract(status="failed") → commit
```

#### `generate_clause_suggestion(session, contract_id, clause_id)` → `NegotiationSuggestion`

```
1. Verify clause belongs to contract (raises NotFoundException if not)
2. Check if suggestion already exists → return early if found
3. rag_pipeline.retrieve_and_generate(
     query="Analyze target clause + provide negotiation recommendations",
     workspace="contract_intelligence",
     system_prompt=NEGOTIATION_SUGGESTION_SYSTEM,
     top_k=3,
     filters={"document_id": contract.document_id}
   )
   → Retrieves 3 semantically similar clauses from the same document
   → LLM generates counter-proposal using them as grounding context
4. INSERT negotiation_suggestion(clause_id, suggestion_text)
5. session.commit()
```

#### `delete_contract_and_document(session, contract_id)` → `None`

```
1. retrieval_service.delete_by_document("contract_clauses", document_id)
2. os.remove(doc.storage_path) — delete file from disk
3. session.delete(doc) — cascades to Contract → Clauses → Suggestions
4. session.commit()
```

#### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/contracts/upload` | Upload contract (≤10MB, PDF/DOCX/TXT) |
| `GET` | `/api/v1/contracts/` | List all contracts with risk metrics |
| `GET` | `/api/v1/contracts/{id}` | Full contract + all clauses |
| `POST` | `/api/v1/contracts/{id}/clauses/{clause_id}/suggest` | Generate negotiation suggestion |
| `DELETE` | `/api/v1/contracts/{id}` | Delete contract + all associated data |

---

### 7.2 Legal Notice Center Workspace

**Objective:** Parse legal notices, classify urgency, and auto-draft formal reply letters.

#### `create_and_start_analysis(session, file_bytes, filename, user_id)` → `Notice`

```
Synchronous:
  1. Create storage_path, INSERT core.documents
  2. INSERT notice (raw_text="Processing...", notice_type=null, urgency=null)
  3. Return Notice stub
```

#### `run_async_notice_analysis(notice_id, file_bytes, filename, document_id)` → `None`

```
Background:
  1. rag_pipeline.ingest_document(workspace="legal_notice_center")
     → paragraph chunking (not clause-based)
  2. Reconstruct full_text from all chunks
  3. LEGAL_NOTICE_ANALYSIS_USER.format(notice_text=full_text)
     llm_client.generate(json_mode=True)
     → {"notice_type", "urgency", "reply_text"}
  4. UPDATE notice(raw_text, notice_type, urgency)
  5. INSERT draft_reply(notice_id, reply_text)
  6. session.commit()

On error → save fallback: type="other", urgency="medium", generic reply text
```

#### `regenerate_reply(session, notice_id)` → `DraftReply`

```
1. Load notice from DB
2. rag_pipeline.retrieve_and_generate(
     query="Draft formal legal reply letter addressing notice points",
     workspace="legal_notice_center",
     system_prompt=LEGAL_NOTICE_ANALYSIS_SYSTEM,
     top_k=5,
     filters={"document_id": notice.document_id},
     json_mode=True
   )
3. If RAG fails → fallback: direct LLM call without retrieval
4. INSERT new draft_reply (history preserved — never overwrites)
```

#### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/notices/upload` | Upload legal notice |
| `GET` | `/api/v1/notices/` | List all notices |
| `GET` | `/api/v1/notices/{id}` | Notice details + all draft replies |
| `POST` | `/api/v1/notices/{id}/regenerate` | Generate new RAG-enhanced reply |

---

### 7.3 Compliance Center Workspace

**Objective:** Indian SME compliance calendar management — statutory task generation, document analysis, GSTIN-based onboarding.

#### `initialize_statutory_tasks(session, business_type, user_id)` → `List[ComplianceTask]`

Generates a complete statutory compliance calendar for FY 2026-27:

```
1. DELETE all existing tasks for user (clean re-initialization)

2. Generate tasks based on business_type:
   ALL types receive:
     - GST GSTR-1 Filing (11th of each month, Jul-Dec 2026)
     - GST GSTR-3B Filing (20th of each month, Jul-Dec 2026)
     - TDS Deposit (7th of following month)
     - Advance Tax Q2 (Sep 15) + Q3 (Dec 15)
     - Annual ITR filing

   private_limited / llp / partnership additionally receive:
     - PF & ESI Monthly Deposit (15th of each month)

   private_limited specifically:
     - DIR-3 KYC (Sep 30)
     - MCA AOC-4 Financial Statements (Oct 30)
     - MCA MGT-7 Annual Return (Nov 29)

   llp specifically:
     - MCA Form 11 Annual Return (Jul 30)
     - MCA Form 8 Statement of Account (Oct 30)

3. Batch INSERT all tasks
4. Return fresh list from DB (with server-generated timestamps)
```

#### `initialize_statutory_tasks_by_gstin(session, gstin, user_id)` → `dict`

```
1. If mode=="live":
   sandbox_client.search_gstin_live(gstin)
   → taxpayer dict (lgnm, ctb, sts, etc.)

2. If mode=="mock":
   VendorVerificationProvider.verify_gstin(gstin) → mock data

3. Auto-resolve ctb → business_type:
   "private limited" / "company" → "private_limited"
   "partnership" (not LLP)       → "partnership"
   "llp"                         → "llp"
   All others                    → "sole_proprietorship"

4. initialize_statutory_tasks(session, business_type, user_id)

5. INSERT welcome task (status="completed"):
   "Setup Completed for {company_name} (GSTIN: ...)"

6. Return {company_name, business_type, gstin, constitution, tasks[]}
```

#### `run_async_compliance_analysis(analysis_id, file_bytes, filename, document_id, user_id)` → `None`

```
Background:
  1. parse_document(file_bytes, filename) → document_text
  2. Truncate to first 8000 characters (LLM context limit management)
  3. COMPLIANCE_DOCUMENT_ANALYSIS_USER.format(document_text=...)
     llm_client.generate(json_mode=True)
     → {"authority", "document_type", "identifier_number",
        "issue_date", "expiry_date", "status", "risk_assessment",
        "action_items": [{title, due_date, description, category, penalty_desc}]}

  4. UPDATE ComplianceDocumentAnalysis with all extracted fields
  5. For each action_item → INSERT compliance_task
     (due_date defaults to expiry_date or today+7 if not in document)
  6. session.commit()

On error → mark analysis.status="warning", record error in risk_assessment
```

#### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/compliance/tasks` | List user's compliance tasks |
| `POST` | `/api/v1/compliance/tasks` | Create manual task |
| `PUT` | `/api/v1/compliance/tasks/{id}` | Update task (e.g., mark completed) |
| `DELETE` | `/api/v1/compliance/tasks/{id}` | Delete task |
| `POST` | `/api/v1/compliance/init` | Init calendar by business type |
| `POST` | `/api/v1/compliance/init-by-gstin` | Auto-init by GSTIN lookup |
| `POST` | `/api/v1/compliance/upload` | Upload compliance document for AI analysis |
| `GET` | `/api/v1/compliance/analyses` | List all document analyses |
| `GET` | `/api/v1/compliance/analyses/{id}` | Get analysis report |

---

### 7.4 Vendor Intelligence Workspace

**Objective:** Verify vendor legitimacy via GSTIN, compute trust score, detect fraud flags, maintain audit trail.

#### External API: Sandbox.co.in (`sandbox_client.py`)

##### `get_sandbox_token()` → `str`

JWT caching strategy:
```
In-memory: _token_cache (str) and _token_expiry (float timestamp)
If cached and > 1 minute remaining → return cached token

Otherwise:
  POST https://api.sandbox.co.in/authenticate
  Headers: x-api-key, x-api-secret, x-api-version: "1.0"
  → Extract access_token from response.data.access_token
  → Cache with 23-hour expiry (safe margin below 24h token validity)
```

##### `search_gstin_live(gstin)` → `Dict[str, Any]`

```
1. get_sandbox_token() → JWT
2. POST https://api.sandbox.co.in/gst/compliance/public/gstin/search
   Headers: x-api-key, authorization=JWT
   Body: {"gstin": gstin}
3. If 401 (token expired) → reset cache + retry once with fresh token
4. Parse nested: res_data.data.data → taxpayer details dict
5. Return taxpayer dict (lgnm, tradeNam, sts, rgdt, ctb, etc.)
```

#### `verify_and_log_vendor(session, gstin, user_id)` → `VendorCheck`

```
1. If mode=="live":
   search_gstin_live(gstin) → taxpayer
   Extract: company_name, registration_date, status
   Parse date: "DD/MM/YYYY" → "YYYY-MM-DD"
   is_valid = status.upper() == "ACTIVE"
   trust_score = 95 if active, else 20
   fraud_flagged = status in ["CANCELLED", "SUSPENDED"]

2. If mode=="mock":
   VendorVerificationProvider.verify_gstin(gstin) → pre-defined mock

3. INSERT vendor_check(gstin, company_name, is_valid, registration_date,
     trust_score, fraud_flagged, raw_response (full JSONB), checked_by)

4. Return VendorCheck record
```

#### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/vendors/verify` | Verify GSTIN and log result |
| `GET` | `/api/v1/vendors/history` | List all past GSTIN checks |

---

### 7.5 Knowledge Hub (Planned)

Reserved workspace — currently empty. See [Future Roadmap](#13-future-evolution-roadmap).

---

## 8. Frontend Architecture

The frontend is a React + TypeScript SPA built with Vite and TailwindCSS.

### Directory Structure
```
src/
  App.tsx              ← Root router + AuthProvider wrapper
  main.tsx             ← ReactDOM.createRoot entry point
  api/                 ← API client wrappers (fetch calls to backend)
  lib/auth/AuthContext.tsx ← React context for mock role switcher
  design-system/layout/AppShell.tsx ← Sidebar nav + main content
  workspaces/
    contract-intelligence/
      pages/Dashboard.tsx        ← Contract list + upload
      pages/ContractDetail.tsx   ← Clause analysis + risk heatmap
    vendor-intelligence/
      pages/Dashboard.tsx        ← GSTIN verification + history
    legal-notice-center/
      pages/Dashboard.tsx        ← Notice list + upload
      pages/NoticeDetail.tsx     ← Notice details + reply drafts
    compliance-center/
      pages/Dashboard.tsx        ← Task calendar + document upload
```

### Routing

| Route | Component |
|-------|-----------|
| `/` | Contract Intelligence Dashboard |
| `/contracts/:id` | Contract Detail (clause breakdown) |
| `/vendors` | Vendor Intelligence |
| `/notices` | Legal Notice Dashboard |
| `/notices/:id` | Legal Notice Detail |
| `/compliance` | Compliance Center |
| `*` | Fallback → Contract Dashboard |

### Auth Context

`AuthProvider` wraps the entire app. Users switch between `owner`, `ca`, `reviewer` roles via a UI dropdown. Selected role is sent as `X-User-Role` HTTP header with every request.

---

## 9. Data Models & Database Schemas

PostgreSQL uses **schema namespacing** to isolate workspace data:

```
core schema:
  users                     (id, full_name, role)
  documents                 (id, workspace, original_filename, storage_path, uploaded_by, uploaded_at)

contract_intelligence schema:
  contracts                 (id, document_id → core.documents, title, counterparty_name, status)
  clauses                   (id, contract_id, clause_index, raw_text, summary, risk_type, risk_score, qdrant_point_id)
  negotiation_suggestions   (id, clause_id, suggestion_text)

legal_notice_center schema:
  notices                   (id, document_id → core.documents, raw_text, notice_type, urgency)
  draft_replies             (id, notice_id, reply_text)

compliance_center schema:
  compliance_tasks          (id, title, category, due_date, status, description, penalty_desc, document_id, user_id)
  compliance_document_analyses (id, document_id, authority, document_type, identifier_number,
                                issue_date, expiry_date, status, risk_assessment, extracted_actions[JSONB])

vendor_intelligence schema:
  vendor_checks             (id, gstin, company_name, is_valid, registration_date, trust_score,
                              fraud_flagged, raw_mock_response[JSONB], checked_by)
```

### Key Relationships

```
core.users ──1:N──► core.documents
core.documents ──1:1──► contract_intelligence.contracts
  contracts ──1:N──► clauses ──1:N──► negotiation_suggestions
core.documents ──1:1──► legal_notice_center.notices
  notices ──1:N──► draft_replies
core.documents ──1:1──► compliance_center.compliance_document_analyses
compliance_center.compliance_tasks ──N:1──► core.documents (nullable)
```

---

## 10. End-to-End Data Flow Walkthroughs

### 10.1 Contract Upload & Analysis Flow

```
Browser ──POST /api/v1/contracts/upload──► Router
                                            │ validate: size ≤ 10MB, extension ∈ {pdf,docx,txt,md}
                                            │
                                            ▼ service.create_and_start_analysis()
                                            │ save_file → INSERT documents → INSERT contract (status=processing)
                                            │ commit + refresh
                                            │
Browser ◄─── 200 Contract stub ────────────┘
             (status="processing")         │ background_tasks.add_task(run_async_contract_analysis)
                                           │
                                     [BACKGROUND WORKER]
                                           │
                                           ▼ rag_pipeline.ingest_document()
                                           │ parse_document() → raw text
                                           │ chunk_by_clause() → [{"clause_index": 0, "text": "..."}, ...]
                                           │ embedder.embed(texts) → 384-dim vectors[]
                                           │ retrieval_service.upsert_chunks("contract_clauses")
                                           │
                                           ▼ For each chunk:
                                           │ llm_client.generate(CLAUSE_ANALYSIS prompt, json_mode=True)
                                           │ → {"summary": "...", "risk_type": "penalty", "risk_score": 75}
                                           │ INSERT clause(risk_type, risk_score, qdrant_point_id)
                                           │
                                           ▼ llm_client.generate(CONTRACT_METADATA prompt, json_mode=True)
                                           │ → {"title": "...", "counterparty_name": "..."}
                                           │ UPDATE contract(title, counterparty, status="analyzed")
                                           │ session.commit()

Browser polls GET /api/v1/contracts/{id} → status="analyzed" when done

Browser ──POST /api/v1/contracts/{id}/clauses/{clause_id}/suggest──►
                                           ▼ service.generate_clause_suggestion()
                                           │ verify clause belongs to contract
                                           │ check existing suggestion (return if found)
                                           │
                                           ▼ rag_pipeline.retrieve_and_generate()
                                           │ embed(query) → search "contract_clauses"
                                           │   filter: document_id = contract.document_id, top_k=3
                                           │ → 3 most similar clauses as context
                                           │ llm_client.generate(NEGOTIATION_SUGGESTION_SYSTEM)
                                           │ → counter-proposal text
                                           │ INSERT negotiation_suggestion
Browser ◄─── NegotiationSuggestion ───────┘
```

---

### 10.2 Legal Notice Flow

```
POST /api/v1/notices/upload
  │ [Sync] save_file → INSERT documents → INSERT notice (raw_text="Processing...")
  │ Return Notice stub
  │
  └── [Background]
        rag_pipeline.ingest_document(workspace="legal_notice_center")
          parse → chunk_by_paragraph → embed → upsert("legal_notices")
        full_text = join all chunk texts
        llm_client.generate(LEGAL_NOTICE_ANALYSIS_SYSTEM, json_mode=True)
          → {notice_type, urgency, reply_text}
        UPDATE notice(raw_text, notice_type, urgency)
        INSERT draft_reply(reply_text)
        session.commit()

POST /api/v1/notices/{id}/regenerate
  │ load notice from DB
  ├── rag_pipeline.retrieve_and_generate(
  │     query="Draft formal legal reply addressing notice points",
  │     filters={document_id},  top_k=5,  json_mode=True
  │   ) → new reply_text
  └── INSERT draft_reply (history preserved — previous drafts kept)
```

---

### 10.3 Compliance GSTIN Init Flow

```
POST /api/v1/compliance/init-by-gstin
  Body: {"gstin": "27AAPCA1234B1ZV"}
  │
  ├── If mode=="live":
  │     get_sandbox_token() → JWT (cached 23h)
  │     POST api.sandbox.co.in/gst/.../search → taxpayer dict
  │     extract: company_name (lgnm), ctb (constitution)
  │
  ├── If mode=="mock":
  │     VendorVerificationProvider.verify_gstin(gstin) → mock
  │
  ├── ctb → business_type:
  │     "Private Limited Co" → "private_limited"
  │     "LLP"               → "llp"
  │     "Partnership"       → "partnership"
  │     default             → "sole_proprietorship"
  │
  ├── DELETE all existing user tasks
  ├── INSERT 30–40 statutory tasks (GST, TDS, ITR, PF, MCA, AdvanceTax)
  ├── INSERT welcome task (status="completed")
  └── Return {company_name, business_type, gstin, constitution, tasks[]}
```

---

### 10.4 Vendor GSTIN Verification Flow

```
POST /api/v1/vendors/verify
  Body: {"gstin": "29AAFCA1234B1ZN"}
  │
  ├── verify_and_log_vendor(session, gstin, current_user.id)
  │
  │   [live mode]
  │     get_sandbox_token() → JWT (with 23h cache)
  │     search_gstin_live(gstin)
  │       If 401 → reset cache → retry once
  │     Parse: company_name, status, registration_date
  │     trust_score = 95 (ACTIVE) | 20 (other)
  │     fraud_flagged = status in [CANCELLED, SUSPENDED]
  │
  │   [mock mode]
  │     VendorVerificationProvider.verify_gstin(gstin) → pre-defined mock
  │
  └── INSERT vendor_check(gstin, company_name, is_valid, trust_score,
                          fraud_flagged, raw_response[JSONB], checked_by)
      Return VendorCheck
```

---

## 11. API Endpoint Reference

| Workspace | Method | Path | Description |
|-----------|--------|------|-------------|
| **Health** | `GET` | `/health` | System health check |
| **Contracts** | `POST` | `/api/v1/contracts/upload` | Upload + analyze contract |
| | `GET` | `/api/v1/contracts/` | List contracts |
| | `GET` | `/api/v1/contracts/{id}` | Contract detail + clauses |
| | `POST` | `/api/v1/contracts/{id}/clauses/{clause_id}/suggest` | Negotiation suggestion |
| | `DELETE` | `/api/v1/contracts/{id}` | Delete contract + cleanup |
| **Vendors** | `POST` | `/api/v1/vendors/verify` | Verify GSTIN |
| | `GET` | `/api/v1/vendors/history` | GSTIN audit history |
| **Notices** | `POST` | `/api/v1/notices/upload` | Upload legal notice |
| | `GET` | `/api/v1/notices/` | List notices |
| | `GET` | `/api/v1/notices/{id}` | Notice detail + drafts |
| | `POST` | `/api/v1/notices/{id}/regenerate` | Regenerate reply draft |
| **Compliance** | `GET` | `/api/v1/compliance/tasks` | List tasks |
| | `POST` | `/api/v1/compliance/tasks` | Create manual task |
| | `PUT` | `/api/v1/compliance/tasks/{id}` | Update task |
| | `DELETE` | `/api/v1/compliance/tasks/{id}` | Delete task |
| | `POST` | `/api/v1/compliance/init` | Init calendar by business type |
| | `POST` | `/api/v1/compliance/init-by-gstin` | Auto-init by GSTIN |
| | `POST` | `/api/v1/compliance/upload` | Upload compliance document |
| | `GET` | `/api/v1/compliance/analyses` | List document analyses |
| | `GET` | `/api/v1/compliance/analyses/{id}` | Get analysis report |

---

## 12. What Problem Does LegalOS Solve?

### The Core Problem

**Indian SMEs operate in one of the world's most complex regulatory environments** — GST with monthly filings, TDS deposits, PF/ESI contributions, MCA corporate filings, income tax returns, and sector-specific licenses. On top of this, they routinely face:

- **Opaque vendor contracts** with hidden penalty clauses, unfavorable lock-in periods, or excessive indemnity obligations written in dense legal language.
- **Legal notices** from counterparties, regulators, or courts requiring rapid professional responses within strict deadlines.
- **Compliance certificates** (FSSAI, shop licenses, GST registrations) that expire or trigger action items that go untracked.
- **Vendor fraud risk** when onboarding new partners without GSTIN verification.

**The costs without LegalOS:**

| Problem | Traditional Cost |
|---------|----------------|
| Contract review | ₹5,000–50,000 per contract |
| CA compliance retainer | ₹10,000–30,000/month |
| Legal notice response | ₹5,000–20,000 per notice |
| GST late penalty | ₹50/day (₹20 for nil returns) |
| Income tax late fee | Up to ₹5,000 (section 234F) |

### What LegalOS Delivers

| Problem | LegalOS Solution |
|---------|----------------|
| Contract review is expensive and slow | Upload PDF → AI analyzes every clause in minutes, risk-scores 0-100, flags penalty/lock-in/indemnity/termination risks |
| Negotiation requires legal expertise | AI generates context-aware counter-proposals using RAG (similar clauses from the same document as grounding) |
| Compliance deadlines are complex and business-type specific | One GSTIN lookup → auto-generates 30–40 statutory tasks with due dates, categories, and penalty descriptions |
| Legal notices require immediate expert response | Upload notice → AI classifies urgency + type + drafts formal reply letter in seconds |
| Vendor legitimacy is hard to verify | GSTIN lookup → instant trust score, fraud flag, registration date, full audit trail |
| Compliance documents expire unnoticed | Upload certificate → AI extracts expiry date + auto-creates follow-up tasks |

### The Technical Enabler: RAG Architecture

The system is not just a "chatbot" — every LLM response is **grounded in the actual content of your documents** via RAG:

1. Documents are chunked into clause-level or paragraph-level segments
2. Each segment is embedded into a 384-dimensional semantic vector
3. When generating any AI output, the most relevant segments are retrieved and injected as grounding context
4. This prevents hallucination and ensures responses are traceable to real document text

---

## 13. Future Evolution Roadmap

### Phase 2 — Near-term (3–6 months)

#### 🔐 Real Authentication System
- Replace mock role auth with JWT + OAuth2 (Google/Microsoft SSO)
- Multi-tenant isolation: each organization gets isolated data partitions
- RBAC: business owner vs. CA vs. legal reviewer permissions on each workspace

#### 📚 Knowledge Hub Workspace (Planned Module)
- Upload company policies, legal handbooks, regulatory circulars
- Build semantic Q&A: "What is our termination notice policy?"
- Qdrant collection: `knowledge_base`
- RAG-grounded answers from internal document library

#### 📧 Notification & Deadline Alerts
- Email/SMS/WhatsApp reminders before compliance deadlines
- Push notifications X days before due dates
- Google Calendar / Outlook sync integration

#### 📊 Contract Portfolio Analytics
- Dashboard: risk distribution across all contracts
- Pattern detection: "70% of your contracts have high lock-in risk"
- Vendor risk comparison across counterparties

### Phase 3 — Medium-term (6–12 months)

#### ☁️ Production Infrastructure Migration
- Replace local disk storage with AWS S3 / Azure Blob / GCS
- Redis caching for LLM responses (avoid duplicate API calls for same clause)
- Horizontal Uvicorn workers behind a load balancer
- Celery + Redis task queue (replace FastAPI BackgroundTasks for reliability)

#### 🤖 Advanced RAG — Hybrid Search
- BM25 keyword search alongside vector search
- Hybrid ranking: semantic score + keyword frequency
- Cross-encoder reranking for highest-quality retrieval
- LLM query expansion to broaden semantic coverage

#### 📝 Contract Drafting Assistant
- Plain-English description → draft full contract sections
- Pre-approved clause library (NDA, service agreement, employment contract)
- Track-changes mode: AI suggests inline edits in document

#### 🔗 Court & Regulatory API Integrations
- MCA (Ministry of Corporate Affairs) API: auto-track filing status
- Income Tax portal: real-time demand notice pull
- High Court e-filing portal: case status monitoring

### Phase 4 — Long-term (12+ months)

#### 🌐 Multi-jurisdiction Support
- Extend beyond India: UAE, UK, Singapore legal frameworks
- Jurisdiction-aware prompts and compliance calendars
- Multi-currency penalty calculations

#### 🧠 Fine-tuned Legal LLM
- Fine-tune on Indian legal corpus: IT Act, GST Act, Companies Act, contract case law
- Lower hallucination rates and better Indian legal reasoning
- Reduced reliance on Gemini API (cost + latency savings)

#### 📋 E-Signature & Workflow
- Leegality / DocuSign integration for contract signing
- Approval workflows: legal reviewer must approve before signing
- Immutable audit trail: who viewed, annotated, and signed

#### 🔄 ERP & Accounting Integrations
- Tally, Zoho Books, QuickBooks → auto-sync vendor GST filing status
- Bank statement parsing → detect TDS deductions automatically
- MCA filing status sync → auto-mark compliance tasks as completed

#### 🤝 Lawyer Marketplace (B2B2C Extension)
- Connect users with verified Indian lawyers for complex matters
- AI triage: route simple matters to AI, complex matters to lawyers
- Revenue stream: referral fee per successful consultation

---

## Appendix: Directory Map

```
LegalOs/
└── legalos/
    ├── architecture.md           ← This document
    ├── docker-compose.yml
    ├── .env.example
    ├── backend/
    │   ├── app/
    │   │   ├── main.py           ← App bootstrap + lifespan
    │   │   ├── config.py         ← Settings singleton
    │   │   ├── dependencies.py   ← FastAPI DI
    │   │   ├── core/
    │   │   │   ├── embeddings/embedder.py
    │   │   │   ├── llm/
    │   │   │   │   ├── llm_client.py
    │   │   │   │   ├── providers/gemini_provider.py
    │   │   │   │   ├── providers/local_provider.py
    │   │   │   │   └── prompts/{contract, notice, compliance, vendor}_prompts.py
    │   │   │   ├── rag/
    │   │   │   │   ├── document_parser.py
    │   │   │   │   ├── chunker.py
    │   │   │   │   └── rag_pipeline.py
    │   │   │   └── vectorstore/
    │   │   │       ├── qdrant_client.py
    │   │   │       ├── collections.py
    │   │   │       └── retrieval_service.py
    │   │   ├── shared/
    │   │   │   ├── auth/auth_service.py
    │   │   │   ├── db/{base, models, mixins, session}.py
    │   │   │   ├── storage/file_storage.py
    │   │   │   └── exceptions.py
    │   │   └── workspaces/
    │   │       ├── contract_intelligence/{models, schemas, repository, router, service}.py
    │   │       ├── legal_notice_center/{models, schemas, repository, router, service}.py
    │   │       ├── compliance_center/{models, schemas, repository, router, service}.py
    │   │       ├── vendor_intelligence/{models, schemas, repository, router, service, sandbox_client}.py
    │   │       └── knowledge_hub/ (planned)
    │   └── pyproject.toml
    └── frontend/
        └── src/
            ├── App.tsx
            ├── lib/auth/AuthContext.tsx
            ├── design-system/layout/AppShell.tsx
            └── workspaces/{contract-intelligence, legal-notice-center, compliance-center, vendor-intelligence}/
```
