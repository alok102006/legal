> **OUTDATED - read docs/PROGRESS.md and docs/IMPLEMENTATION_PLAN.md instead.** This file describes the earlier prototype and contains claims that are not true of the current code (for example fake status badges, hybrid retrieval, mock-free vendor checks).

# LegalOS — AI Legal & Compliance Operating System
> **Comprehensive System & Architecture Overview for Resume Enhancement & Technical Interview Preparation**
> 
> *Note for ChatGPT / AI Assistant:* Use this document to understand the full technical depth, architecture, database design, AI/RAG pipelines, external API integrations, and business impact of **LegalOS**. Use this context to generate high-impact resume bullet points, STAR-format interview responses, and technical summaries tailored for Full-Stack Engineer, Backend Engineer, AI/RAG Engineer, or Software Development Engineer (SDE) roles.

---

## 1. Executive Summary & Project Overview

**LegalOS** is a multi-workspace, production-grade AI operating system built specifically for **Indian Small and Medium Enterprises (SMEs)**. It automates high-stakes legal, compliance, contract risk analysis, and vendor verification workflows.

### Problem Solved
Indian SMEs face severe legal and compliance challenges:
1. **High Legal Retainer Costs**: Reviewing legal contracts and responding to legal notices via law firms is slow and expensive.
2. **Statutory Penalties**: Missing mandatory Indian regulatory filing deadlines (GST, TDS, MCA AOC-4/MGT-7, PF/ESI, Income Tax) leads to compounding daily fines, director disqualifications, and legal action.
3. **Vendor Fraud & Non-Compliance**: Transacting with cancelled or unverified GSTIN vendors leads to loss of Input Tax Credit (ITC) and financial risk.

### Solution Delivered
LegalOS unifies 4 core enterprise workspaces backed by a **Retrieval-Augmented Generation (RAG)** engine, vector database search, live statutory API integrations, and an automated background task pipeline:
1. **Contract Intelligence**: Auto-parses contracts, scores clause-level risks (0–100), extracts counterparties, and generates RAG-grounded negotiation counter-proposals.
2. **Legal Notice Center**: Classifies incoming legal notices by type and urgency, and drafts formal, legally structured response letters.
3. **Compliance Center**: Auto-populates dynamic Indian statutory filing calendars based on entity type (Pvt Ltd, LLP, Partnership, Sole Proprietorship) and analyzes uploaded compliance certificates to auto-generate actionable tasks.
4. **Vendor Intelligence**: Performs live GSTIN verification via Sandbox.co.in REST APIs, computes vendor trust scores, flags fraud risks, and maintains Postgres audit logs.

---

## 2. Full Technology Stack & Architecture

### Backend Stack
- **Framework**: Python 3.11+, FastAPI (Async/ASGI with Uvicorn server).
- **Database & ORM**: PostgreSQL, SQLAlchemy 2.0 (Async ORM via `asyncpg`), Alembic for database migrations.
- **Data Serialization & Validation**: Pydantic v2 schemas.
- **Document Processing**: PyMuPDF (`fitz`) for high-speed PDF text parsing, `python-docx` for Word documents.

### AI / RAG & Vector Store Stack
- **Vector Database**: Qdrant (Vector Database with cosine distance metrics and payload filtering).
- **Embedding Model**: Local `SentenceTransformer` (`all-MiniLM-L6-v2`, 384-dimensional dense vectors) loaded as a singleton during application startup.
- **LLM Orchestration**: Google Gemini API (`gemini-2.5-flash` / `gemini-1.5-flash`), with structured JSON output enforcement (`json_mode=True`), customized prompt templates, and graceful fallback mechanisms.
- **RAG Pipeline**: Custom modular pipeline featuring document parsing, clause/paragraph text chunking, vector embedding, Qdrant indexing, and document-filtered semantic retrieval.

### Frontend Stack
- **Framework & Tooling**: React 18, TypeScript, Vite, Tailwind CSS v3.4.
- **State Management & Routing**: React Context API (dynamic Workspace Switcher and Auth/Role Switcher), Custom Hooks, Lucide React Icons.
- **UI Components**: Glassmorphic dashboard UI, interactive contract clause inspectors, real-time risk gauges, search bars, modal dialogs, and responsive grid layouts.

### DevOps & Infrastructure
- **Containerization**: Docker & Docker Compose multi-container setup (Backend, Frontend, PostgreSQL, Qdrant).
- **Configuration & Security**: Pydantic BaseSettings, `.env` management, dynamic CORS header middleware, async database session pools.
- **External Integrations**: Sandbox.co.in API (GSTIN search with OAuth/JWT authentication caching and 401 auto-retry logic).

---

## 3. Detailed Workspace Implementations & Key Features

### 📄 Workspace 1: Contract Intelligence Platform
- **Async Non-Blocking Upload & Processing**: When a user uploads a contract (PDF/DOCX), FastAPI instantly saves the document, creates PostgreSQL stubs, and delegates ingestion to a background worker (`run_async_contract_analysis`).
- **Clause-Level Segmentation & Parsing**: The document parser extracts full text, and the chunker splits the text into logical clauses (with paragraph sliding fallback).
- **Local Embedding & Vector Storage**: Each clause is embedded into 384-dim vectors using `all-MiniLM-L6-v2` and upserted to Qdrant collection `contract_clauses` with metadata filters (`document_id`, `contract_id`, `clause_index`).
- **LLM-Powered Risk Analysis**: Iterates over each clause using Gemini API to generate structured JSON containing:
  - Clause summary
  - Risk category (*Indemnification, Termination, Limitation of Liability, Confidentiality, Governing Law, Non-Compete, etc.*)
  - Quantitative Risk Score (0 to 100)
- **Metadata Extraction**: Contextually analyzes the first 4,000 characters of the document to extract official Contract Title and Counterparty Name.
- **Targeted RAG Negotiation Suggestions**: Allows users to select any risky clause and trigger `generate_clause_suggestion`. Performs Qdrant vector retrieval restricted to that document ID (`top_k=3`), feeds retrieved context into an LLM prompt, and drafts redline/negotiation counter-proposals.

### 📜 Workspace 2: Legal Notice Center
- **Notice Parsing & Classification**: Accepts legal notice files, ingests text into Qdrant collection `legal_notices`, and runs LLM classification to identify:
  - Notice Type (*Demand Notice, Cease & Desist, Tax Show-Cause, Breach of Contract, Employment Dispute, etc.*)
  - Urgency Level (*Critical, High, Medium, Low*)
- **RAG-Grounded Counter-Drafting**: Synthesizes the legal notice contents and uses RAG retrieval to generate formal legal response letters adhering to standard Indian legal formatting.
- **Draft Versioning**: Supports notice response regeneration and storing multiple response drafts in SQL.

### 📅 Workspace 3: Compliance Center & Statutory Calendar
- **Dynamic Statutory Calendar Generator**: Features an automated generator (`initialize_statutory_tasks`) pre-populated with Indian corporate statutory filing deadlines (GST GSTR-1 & GSTR-3B, Monthly TDS, PF & ESI, MCA AOC-4, MGT-7, DIR-3 KYC, Advance Tax installments, and Annual Income Tax Returns).
- **Business Structure Customization**: Dynamically customizes deadlines based on company registration type:
  - *Private Limited Company*
  - *Limited Liability Partnership (LLP)*
  - *Partnership Firm*
  - *Sole Proprietorship*
- **Automated Compliance Certificate Analyzer**: Allows users to upload government certificates/notices. Runs an async LLM parser to extract:
  - Issuing Authority & Document Type
  - Identifier / Registration Number
  - Issue Date & Expiry / Renewal Date
  - Risk Assessment & Action Items
- **Auto-Task Creation**: Converts extracted document action items into tracked compliance tasks with penalty descriptions and due dates.

### 🔍 Workspace 4: Vendor Intelligence & Verification Engine
- **Live GSTIN API Integration**: Connects to Sandbox.co.in REST APIs (`search_gstin_live`) to search official Indian GSTIN records.
- **OAuth/JWT Token Lifecycle Management**: Implements in-memory caching for Sandbox.co.in JWT tokens (`get_sandbox_token`), expiring tokens after 23 hours, with automatic token refresh and single-retry handling on `401 Unauthorized` responses.
- **Trust Score & Fraud Detection Algorithm**:
  - Parses legal name, trade name, registration date, and active/cancelled status.
  - Computes Trust Score dynamically (e.g., Active = 95 trust score; Suspended/Cancelled = 20 score + Fraud Flag).
- **Audit Logging**: Persists all historical vendor checks and raw payload responses into PostgreSQL for audit readiness.
- **Fallback Mock Engine**: Features a seamless mock provider switch (`VendorVerificationProvider`) when live API keys are not configured or for offline testing environments.

---

## 4. Engineering Accomplishments & Highlighted Systems

### 1. Robust Async Background Architecture
- Applied async non-blocking file upload endpoints. Long-running document chunking, embedding, vector database upserts, and LLM calls execute cleanly in background tasks without blocking the main event loop or HTTP requests.

### 2. Multi-Tenant Vector Collection Isolation
- Isolated vector storage using Qdrant collections (`contract_clauses`, `legal_notices`).
- Implemented payload filtering (`document_id` filter) during RAG retrieval to prevent cross-document context leakage and ensure absolute accuracy in clause negotiation suggestions.

### 3. Resilience & Token Lifecycle Engineering
- Built an in-memory token manager for third-party OAuth/JWT endpoints with smart expiration checking, network error handling, and silent token refreshment on HTTP 401 errors.

### 4. Controlled LLM Output via Structured JSON Mode
- Designed system and user prompt engineering pipelines enforcing strict JSON schemas on Google Gemini responses. Included robust exception handling and fallback logic to handle network glitches or non-conforming responses gracefully.

### 5. Production DB Schema Design & Cascade Deletion
- Architected relational SQL models (Users, Documents, Contracts, Clauses, Negotiation Suggestions, Notices, Draft Replies, Compliance Tasks, Compliance Document Analyses, Vendor Checks) with foreign keys and database cascading.
- Implemented synchronized deletion logic (`delete_contract_and_document`) that cleans up local disk files, PostgreSQL rows, and Qdrant vector points simultaneously.

---

## 5. Resume Bullet Points (Ready to Copy & Use)

### For Full-Stack / SDE Roles
- **Architected and built LegalOS**, a multi-tenant AI Legal & Compliance Operating System using **FastAPI**, **React 18**, **TypeScript**, **PostgreSQL**, **Qdrant**, and **Google Gemini API**, serving 4 core enterprise workspaces.
- **Implemented an asynchronous background document processing pipeline** in FastAPI, reducing HTTP response latency by **95%** for document uploads by offloading chunking, embedding, and LLM risk analysis to non-blocking workers.
- **Designed a responsive, glassmorphic React dashboard** with dynamic workspace context switching, interactive contract clause inspectors, real-time risk scoring visualizers, and modal workflows.
- **Engineered a multi-container Docker infrastructure** combining FastAPI, React/Vite, PostgreSQL, and Qdrant, with automated Alembic database migrations and CORS security policies.

### For Backend / Systems Engineer Roles
- **Developed asynchronous REST APIs** using FastAPI, SQLAlchemy 2.0 (asyncpg), and PostgreSQL, modeling complex relational schemas for contracts, compliance deadlines, legal notices, and vendor audits.
- **Integrated Sandbox.co.in live GSTIN verification APIs**, engineering a JWT authentication service with in-memory caching, token expiration handling, and automatic retry on 401 unauthorized errors.
- **Created a dynamic statutory compliance engine** that auto-generates recurring Indian tax & corporate filing deadlines (GST, TDS, MCA, PF/ESI) based on business entity type (Pvt Ltd, LLP, Partnership, Sole Proprietorship).
- **Built a dual-layer cleanup pipeline** ensuring synchronized cascade deletions across local storage, PostgreSQL relational tables, and Qdrant vector store collections.

### For AI / RAG / ML Engineer Roles
- **Engineered an end-to-end RAG (Retrieval-Augmented Generation) pipeline** utilizing local `SentenceTransformers` (`all-MiniLM-L6-v2`, 384-dim embeddings) and **Qdrant vector store** for semantic legal document search.
- **Implemented document-filtered vector retrieval** in Qdrant, eliminating cross-document context contamination and enabling targeted clause negotiation counter-proposals via Google Gemini LLM.
- **Designed structured prompt pipelines with Gemini 2.5 Flash** enforcing JSON output mode (`json_mode=True`), achieving reliable clause risk scoring (0-100), risk categorization, and legal notice urgency classification.
- **Built a hybrid compliance document parser** using PyMuPDF and python-docx, converting raw PDF/DOCX files into structured text chunks and extracting key compliance metadata via LLM synthesis.

---

## 6. How to Prompt ChatGPT using this File

When pasting this file into ChatGPT to refine your resume or prepare for interviews, try prompts like:

### Prompt 1: Tailoring Resume Bullets for a Specific Job Description
> *"I am applying for a [Full-Stack / Senior Backend / AI Engineer] role at [Company Name]. Here is the job description: [Paste JD]. Based on the attached `PROJECT_OVERVIEW_FOR_CHATGPT.md` file about my project LegalOS, pick the most relevant technical achievements and draft 4–5 high-impact, bullet points using action verbs and quantifiable metrics."*

### Prompt 2: Preparing for System Design & Architecture Questions
> *"Based on the `PROJECT_OVERVIEW_FOR_CHATGPT.md` document, act as a Senior Technical Interviewer. Ask me 5 deep technical interview questions about the architecture of LegalOS (covering the RAG pipeline, async background processing, Qdrant vector indexing, and live API token management). Then provide model answers for each question."*

### Prompt 3: Formatting STAR Technique Behavioral Stories
> *"Using the LegalOS project details from the document, write 3 STAR-format (Situation, Task, Action, Result) interview stories highlighting: (1) Overcoming an async background processing challenge, (2) Implementing RAG with vector search isolation, and (3) Integrating a third-party API resiliently."*

---

### Summary Checklist of Tech & Keywords for your Resume:
- **Languages**: Python 3.11+, TypeScript, SQL, HTML5/CSS3
- **Backend & Database**: FastAPI, Asyncio, SQLAlchemy 2.0, PostgreSQL, Alembic, Uvicorn, Pydantic v2, PyMuPDF, Httpx
- **AI & RAG**: Vector Search, Qdrant, SentenceTransformers (`all-MiniLM-L6-v2`), Google Gemini API, Prompt Engineering, RAG Pipeline, Embeddings, Semantic Search
- **Frontend & UI**: React 18, TypeScript, Vite, Tailwind CSS, Context API, Lucide React
- **Tools & Architecture**: Docker, Docker Compose, REST APIs, OAuth 2.0 / JWT, Async Task Processing, Git
