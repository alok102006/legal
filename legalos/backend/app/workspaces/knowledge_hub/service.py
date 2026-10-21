import asyncio
import functools
import os
import re
import uuid
import json
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.exceptions import NotFoundException, BadRequestException
from app.workspaces.knowledge_hub import repository
from app.workspaces.knowledge_hub.models import RegisteredCompany, CompanyDocument
from app.workspaces.knowledge_hub.sandbox_client import fetch_sandbox_company_profile
from app.core.rag.document_parser import parse_document
from app.core.rag.chunker import chunk_by_paragraph_with_overlap
from app.core.llm.llm_client import generate, generate_async
from app.core.embeddings.embedder import get_embedder
from app.core.vectorstore.qdrant_client import get_qdrant_client
from qdrant_client.http import models as qmodels


STORAGE_DIR = os.path.join(os.getcwd(), "storage", "knowledge_hub")


def clean_text_excerpt(text: str) -> str:
    """Removes non-printable unicode noise, control characters, PUA chars, and redundant spacing."""
    if not text:
        return ""
    clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ue000-\uf8ff\ufffd]', '', text)
    clean = re.sub(r'[ \t]+', ' ', clean)
    return clean.strip()


async def preview_company_profile(gstin: str) -> Dict[str, Any]:
    """Fetches company taxpayer profile from Sandbox API (or mock) without committing to DB."""
    return await fetch_sandbox_company_profile(gstin)


async def register_company_by_gstin(
    session: AsyncSession,
    gstin: str,
    user_id: Optional[uuid.UUID] = None
) -> RegisteredCompany:
    """Fetches profile via Sandbox API and registers/persists company in PostgreSQL."""
    profile = await fetch_sandbox_company_profile(gstin)
    company = await repository.upsert_company(session, profile, user_id=user_id)
    return company


async def list_registered_companies(
    session: AsyncSession
) -> List[RegisteredCompany]:
    """Retrieve all registered companies."""
    return await repository.list_companies(session)


async def get_registered_company(
    session: AsyncSession,
    company_id: uuid.UUID
) -> RegisteredCompany:
    """Retrieve specific company profile."""
    company = await repository.get_company_by_id(session, company_id)
    if not company:
        raise NotFoundException(f"Registered company with ID {company_id} not found.")
    return company


async def delete_registered_company(
    session: AsyncSession,
    company_id: uuid.UUID
) -> bool:
    """Unregister / delete company profile, physical file storage, and Qdrant vectors."""
    company = await repository.get_company_by_id(session, company_id)
    if not company:
        raise NotFoundException(f"Registered company with ID {company_id} not found.")

    # 1. Remove company physical storage directory
    company_dir = os.path.join(STORAGE_DIR, str(company_id))
    if os.path.exists(company_dir):
        try:
            import shutil
            shutil.rmtree(company_dir)
            print(f"[KNOWLEDGE HUB DELETE] Removed company storage directory: {company_dir}")
        except Exception as e:
            print(f"[KNOWLEDGE HUB DELETE] Storage remove exception: {str(e)}")

    # 2. Remove vector points from Qdrant for this company
    try:
        qclient = get_qdrant_client()
        qclient.delete(
            collection_name="knowledge_base",
            points_selector=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="company_id",
                        match=qmodels.MatchValue(value=str(company_id))
                    )
                ]
            )
        )
        print(f"[KNOWLEDGE HUB DELETE] Deleted Qdrant vector points for company {company_id}")
    except Exception as e:
        print(f"[KNOWLEDGE HUB DELETE] Qdrant vector deletion fallback: {str(e)}")

    # 3. Delete record from PostgreSQL database
    deleted = await repository.delete_company(session, company_id)
    return True



async def upload_and_process_company_document(
    session: AsyncSession,
    company_id: uuid.UUID,
    filename: str,
    file_bytes: bytes,
    title: Optional[str] = None,
    document_category: str = "Policy"
) -> CompanyDocument:
    """
    Parses PDF, DOCX, CSV, EXCEL, TXT, or MD file bytes, extracts text,
    indexes into Qdrant vector database with overlap-aware chunking, saves to
    PostgreSQL, and runs AI risk analysis (synchronous, stored as JSONB).
    """
    company = await repository.get_company_by_id(session, company_id)
    if not company:
        raise NotFoundException(f"Registered company with ID {company_id} not found.")

    doc_title = title.strip() if title and title.strip() else filename

    # 1. Parse file content
    extracted_text = parse_document(file_bytes, filename)
    if not extracted_text or not extracted_text.strip():
        raise BadRequestException(f"Failed to extract readable text content from file '{filename}'.")

    extracted_text = clean_text_excerpt(extracted_text)

    # 2. Save physical file to storage
    company_dir = os.path.join(STORAGE_DIR, str(company_id))
    os.makedirs(company_dir, exist_ok=True)
    file_path = os.path.join(company_dir, filename)
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    # 3. Determine file type
    ext = filename.lower().split(".")[-1]
    file_type_map = {
        "pdf": "PDF",
        "docx": "DOCX",
        "doc": "DOCX",
        "csv": "CSV",
        "xlsx": "EXCEL",
        "xls": "EXCEL",
        "txt": "TXT",
        "md": "MD"
    }
    file_type = file_type_map.get(ext, ext.upper())

    # 4. Generate clean preview summary (first 350 chars of clean non-empty lines)
    clean_lines = [l.strip() for l in extracted_text.splitlines() if l.strip()]
    preview_summary = " ".join(clean_lines)[:350] + ("..." if len(" ".join(clean_lines)) > 350 else "")

    # 5. Persist to PostgreSQL (initial insert, risk_analysis updated below)
    doc_entry = await repository.create_company_document(
        session=session,
        company_id=company_id,
        title=doc_title,
        document_category=document_category,
        summary=preview_summary,
        file_name=filename,
        file_type=file_type,
        file_path=file_path,
        extracted_text=extracted_text
    )

    # 6. Chunk (with overlap) & Index into Qdrant Vector Store
    try:
        embedder = get_embedder()
        qclient = get_qdrant_client()

        # Use the proper overlap-aware chunker from core/rag/chunker.py
        # max_chars=800 gives ~160-200 tokens per chunk; overlap=150 preserves context
        chunk_dicts = chunk_by_paragraph_with_overlap(
            extracted_text, max_chars=800, overlap_chars=150
        )

        # Fallback: hard character split if no paragraph breaks found
        if not chunk_dicts:
            chunk_dicts = [
                {"clause_index": i, "text": extracted_text[j: j + 800]}
                for i, j in enumerate(range(0, len(extracted_text), 650))
            ]

        chunks = [cd["text"] for cd in chunk_dicts]

        # Generate embeddings in batches of 50
        EMBED_BATCH = 50
        all_embeddings: List[List[float]] = []
        for i in range(0, len(chunks), EMBED_BATCH):
            all_embeddings.extend(embedder.embed(chunks[i: i + EMBED_BATCH]))

        points = []
        for c_idx, (chunk_text, vector) in enumerate(zip(chunks, all_embeddings)):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{doc_entry.id}_{c_idx}"))
            points.append(
                qmodels.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "company_id": str(company_id),
                        "document_id": str(doc_entry.id),
                        "title": doc_title,
                        "file_name": filename,
                        "file_type": file_type,
                        "chunk_text": chunk_text
                    }
                )
            )

        if points:
            qclient.upsert(collection_name="knowledge_base", points=points)
            print(f"[KNOWLEDGE HUB RAG] Indexed {len(points)} overlap-aware chunks into Qdrant 'knowledge_base'.")
    except Exception as e:
        print(f"[KNOWLEDGE HUB RAG] Warning: Vector indexing fallback: {str(e)}")

    # 7. Run AI Risk Analysis (synchronous — completes before returning to user)
    risk_data: Optional[Dict[str, Any]] = None
    if file_type in ("PDF", "DOCX", "TXT", "MD"):
        try:
            risk_data = await analyze_document_risk(
                extracted_text=extracted_text,
                doc_title=doc_title,
                file_type=file_type,
                company_name=company.legal_name,
                document_category=document_category
            )
            # Persist risk analysis to DB
            await repository.update_document_risk_analysis(session, doc_entry.id, risk_data)
            doc_entry.risk_analysis = risk_data
        except Exception as e:
            print(f"[KNOWLEDGE HUB RISK] Risk analysis failed (non-fatal): {str(e)}")

    return doc_entry


async def delete_company_document_by_id(
    session: AsyncSession,
    document_id: uuid.UUID
) -> bool:
    """
    Deletes a company document completely from PostgreSQL, removes physical file from disk,
    and removes points from Qdrant vector collection.
    """
    doc = await repository.get_company_document(session, document_id)
    if not doc:
        raise NotFoundException(f"Document with ID {document_id} not found.")

    # 1. Remove physical file from storage if present
    if doc.file_path and os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
            print(f"[KNOWLEDGE HUB DELETE] Deleted physical file: {doc.file_path}")
        except Exception as e:
            print(f"[KNOWLEDGE HUB DELETE] Storage remove exception: {str(e)}")

    # 2. Remove vector points from Qdrant
    try:
        qclient = get_qdrant_client()
        qclient.delete(
            collection_name="knowledge_base",
            points_selector=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="document_id",
                        match=qmodels.MatchValue(value=str(document_id))
                    )
                ]
            )
        )
        print(f"[KNOWLEDGE HUB DELETE] Deleted Qdrant vector points for doc {document_id}")
    except Exception as e:
        print(f"[KNOWLEDGE HUB DELETE] Qdrant deletion fallback: {str(e)}")

    # 3. Delete record in PostgreSQL
    return await repository.delete_company_document(session, document_id)


# ---------------------------------------------------------------------------
# AI Document Risk & Compliance Radar
# ---------------------------------------------------------------------------

_RISK_SYSTEM_PROMPT = """You are LegalOS Risk Intelligence AI — a strict legal and compliance analyst.
You analyse corporate documents (policies, NDAs, contracts, tax filings) and produce a structured
JSON risk report. You NEVER hallucinate. You ONLY flag clauses or gaps that are actually present
(or absent) in the provided text. Be concise but precise."""

_RISK_SCHEMA_DESCRIPTION = """Return ONLY valid JSON (no markdown, no code fences) with this exact structure:
{
  "risk_score": <integer 0-100, where 100 is highest risk>,
  "classification": "<one of: NDA | Service Agreement | Employment Contract | HR Policy | Compliance Certificate | Tax Document | Board Resolution | General Policy | Other>",
  "critical_clauses": [
    {"clause": "<short clause title>", "reason": "<why it is a high-risk clause>", "severity": "<HIGH|MEDIUM>"}
  ],
  "compliance_gaps": [
    {"gap": "<short title>", "detail": "<what is missing or non-compliant>"}
  ],
  "strengths": [
    "<one-line description of a well-drafted section or strong protection>"
  ],
  "suggested_fixes": [
    {"issue": "<clause or gap title>", "fix": "<concrete rewrite or addition recommendation>"}
  ]
}
Rules:
- risk_score: start at 30 (baseline), add 10 per HIGH severity critical clause, add 5 per MEDIUM, add 3 per compliance gap, subtract 5 per strength. Clamp to [0, 100].
- critical_clauses: maximum 5 items.
- compliance_gaps: maximum 4 items.
- strengths: maximum 4 items.
- suggested_fixes: one per critical_clause, maximum 5 items.
- If no risks found, return risk_score=15, empty arrays for critical_clauses/gaps, at least one strength.
- NEVER return markdown. ONLY raw JSON."""


async def analyze_document_risk(
    extracted_text: str,
    doc_title: str,
    file_type: str,
    company_name: str,
    document_category: str
) -> Dict[str, Any]:
    """
    Runs LLM-powered risk & compliance analysis on a document's extracted text.
    Returns a validated dict matching the risk schema, or a safe fallback on error.
    """
    # Use first 6000 chars to keep context manageable and cost low
    text_sample = clean_text_excerpt(extracted_text)[:6000]

    user_prompt = f"""{_RISK_SCHEMA_DESCRIPTION}

DOCUMENT DETAILS:
- Title: {doc_title}
- Category: {document_category}
- File Type: {file_type}
- Company: {company_name}

DOCUMENT TEXT (first 6000 characters):
\"\"\"
{text_sample}
\"\"\"

Analyse the above document and return the JSON risk report now:"""

    try:
        # Use async-safe LLM call to avoid blocking the event loop
        raw = await generate_async(
            prompt=user_prompt,
            system=_RISK_SYSTEM_PROMPT,
            json_mode=True,
            workspace="knowledge_hub_risk"
        )
        # Strip any accidental markdown fences the LLM may add
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw).strip()

        parsed = json.loads(raw)

        # Validate and normalise required keys
        risk_score = int(parsed.get("risk_score", 30))
        risk_score = max(0, min(100, risk_score))

        return {
            "risk_score": risk_score,
            "classification": str(parsed.get("classification", "General Policy")),
            "critical_clauses": parsed.get("critical_clauses", []),
            "compliance_gaps": parsed.get("compliance_gaps", []),
            "strengths": parsed.get("strengths", []),
            "suggested_fixes": parsed.get("suggested_fixes", []),
        }
    except json.JSONDecodeError as je:
        print(f"[KNOWLEDGE HUB RISK] JSON parse error: {str(je)}. Raw: {raw[:200] if 'raw' in dir() else 'N/A'}")
        return _default_risk_report(doc_title)
    except Exception as e:
        print(f"[KNOWLEDGE HUB RISK] LLM call failed: {str(e)}")
        return _default_risk_report(doc_title)


def _default_risk_report(doc_title: str) -> Dict[str, Any]:
    """Safe fallback risk report when analysis fails."""
    return {
        "risk_score": 0,
        "classification": "General Policy",
        "critical_clauses": [],
        "compliance_gaps": [],
        "strengths": [f"Document '{doc_title}' was successfully indexed for Q&A."],
        "suggested_fixes": [],
    }


STOPWORDS = {
    "the", "and", "for", "are", "was", "were", "with", "from", "that", "this",
    "have", "has", "been", "will", "can", "not", "but", "its", "our", "their",
    "what", "how", "when", "who", "why", "all", "any", "you", "your", "they",
    "than", "then", "into", "more", "also", "well", "such", "each", "which",
    "there", "after", "before", "about", "over", "under", "through", "within",
    "shall", "should", "would", "could", "may", "must", "being", "having",
    "per", "via", "etc", "both", "every", "other", "upon", "some", "does",
}


def extract_best_matching_paragraphs(question: str, docs: List[CompanyDocument]) -> List[Dict[str, str]]:
    """
    Ranks paragraphs across all uploaded documents by keyword overlap to produce
    clean, grounded excerpts for the user's question.

    BUG FIX: previously used .splitlines() which broke on single-newline text,
    producing one-liner "paragraphs" that score 0 on most queries.
    Now splits on double-newlines to match the granularity used during indexing.
    """
    words = [
        w.lower() for w in re.findall(r'\w+', question)
        if len(w) > 3 and w.lower() not in STOPWORDS
    ]
    if not words:
        return []
    matched_excerpts = []

    for doc in docs:
        if not doc.extracted_text:
            continue

        # Split on paragraph breaks (double newlines) — matches chunking granularity
        raw_paras = re.split(r'\n[ \t]*\n', doc.extracted_text)
        paras = [clean_text_excerpt(p) for p in raw_paras if len(clean_text_excerpt(p)) > 15]

        for p in paras:
            p_lower = p.lower()
            score = sum(1 for w in words if w in p_lower)
            if score > 0:
                matched_excerpts.append({
                    "score": score,
                    "title": doc.title,
                    "file_name": doc.file_name or doc.title,
                    "text": p
                })

    matched_excerpts.sort(key=lambda x: x["score"], reverse=True)
    return matched_excerpts[:6]


async def ask_company_knowledge(
    session: AsyncSession,
    question: str,
    company_id: Optional[uuid.UUID] = None,
    document_id: Optional[uuid.UUID] = None
) -> Dict[str, Any]:
    """
    RAG AI Q&A engine taking uploaded PDF, Word, CSV, Excel, and TXT files as strict GROUND TRUTH.
    """
    if not company_id:
        return {
            "answer": "Please select or register an organization and upload documents to ask questions.",
            "company_context": "",
            "sources": [],
            "ground_truth_excerpts": []
        }

    company = await repository.get_company_by_id(session, company_id)
    if not company:
        raise NotFoundException(f"Registered company with ID {company_id} not found.")

    company_name = company.legal_name
    addr = company.principal_address or {}
    formatted_addr = addr.get("formatted", "Not specified")
    nba_list = ", ".join(company.nature_of_business or []) if company.nature_of_business else "General Business"

    sources: List[str] = [f"Official GST Profile ({company.legal_name})"]
    ground_truth_excerpts: List[Dict[str, str]] = []

    # 1. Company Profile Metadata Context
    profile_context = f"""
=== REGISTERED COMPANY GST PROFILE ===
Legal Name: {company.legal_name}
Trade Name: {company.trade_name or company.legal_name}
GSTIN: {company.gstin}
Entity Type / Constitution: {company.entity_type or 'Private Limited'}
Status: {company.status}
State Jurisdiction: {company.state_jurisdiction or 'N/A'}
Center Jurisdiction: {company.center_jurisdiction or 'N/A'}
Principal Place of Business: {formatted_addr}
Nature of Business Activities: {nba_list}
"""

    if not company.documents:
        return {
            "answer": "No documents have been uploaded yet for this company. Please upload PDF, Word, CSV, or Excel files to the Knowledge Vault to enable AI Q&A.",
            "company_context": profile_context.strip(),
            "sources": sources,
            "ground_truth_excerpts": []
        }

    docs_to_search = company.documents
    if document_id:
        docs_to_search = [d for d in company.documents if d.id == document_id]
        if not docs_to_search:
            return {
                "answer": "The selected document could not be found in this company's vault.",
                "company_context": profile_context.strip(),
                "sources": sources,
                "ground_truth_excerpts": []
            }

    # 2. Vector / Paragraph RAG Search across target documents
    doc_excerpts_str = ""
    try:
        embedder = get_embedder()
        qclient = get_qdrant_client()
        q_vectors = embedder.embed([question])
        
        if q_vectors:
            must_conditions = [
                qmodels.FieldCondition(
                    key="company_id",
                    match=qmodels.MatchValue(value=str(company_id))
                )
            ]
            if document_id:
                must_conditions.append(
                    qmodels.FieldCondition(
                        key="document_id",
                        match=qmodels.MatchValue(value=str(document_id))
                    )
                )

            q_res = qclient.query_points(
                collection_name="knowledge_base",
                query=q_vectors[0],
                query_filter=qmodels.Filter(must=must_conditions),
                limit=6,
                score_threshold=0.25  # BUG FIX: was 0.38, too high for all-MiniLM-L6-v2
            )
            
            search_results = getattr(q_res, "points", q_res)
            if search_results:
                excerpts = []
                for res in search_results:
                    payload = getattr(res, "payload", {}) or {}
                    doc_title = payload.get("title", "Document")
                    f_name = payload.get("file_name", "")
                    text_chunk = clean_text_excerpt(payload.get("chunk_text", ""))
                    if text_chunk:
                        excerpts.append(f"--- Document Ground Truth: [{doc_title}] ({f_name}) ---\n{text_chunk}")
                        ground_truth_excerpts.append({
                            "document_title": doc_title,
                            "file_name": f_name,
                            "excerpt": text_chunk[:300]
                        })
                        sources.append(f"{doc_title}")
                doc_excerpts_str = "\n\n".join(excerpts)
    except Exception as ex:
        print(f"[KNOWLEDGE HUB RAG] Vector search fallback: {str(ex)}")

    # Fallback / Hybrid: paragraph ranker over PostgreSQL extracted_text
    if not doc_excerpts_str or len(ground_truth_excerpts) == 0:
        ranked = extract_best_matching_paragraphs(question, docs_to_search)
        if ranked:
            excerpts = []
            for r in ranked:
                c_text = clean_text_excerpt(r['text'])
                excerpts.append(f"--- Document Ground Truth: [{r['title']}] ({r['file_name']}) ---\n{c_text}")
                ground_truth_excerpts.append({
                    "document_title": r['title'],
                    "file_name": r['file_name'],
                    "excerpt": c_text[:300]
                })
                sources.append(r['title'])
            doc_excerpts_str = "\n\n".join(excerpts)
        else:
            # Blind full-document dump removed to prevent hallucination
            doc_excerpts_str = ""

    context_docs = doc_excerpts_str if doc_excerpts_str else "No relevant document excerpts found matching this query in uploaded files."
    context_str = f"{profile_context}\n\n=== UPLOADED CORPORATE KNOWLEDGE VAULT (GROUND TRUTH DOCUMENTS) ===\n{context_docs}"

    system_prompt = """You are LegalOS Grounded Knowledge AI — a strict, document-bound assistant.

STRICT OPERATING RULES:
1. ONLY answer using information explicitly present in the CONTEXT GROUND TRUTH below.
2. If the answer is NOT found in the documents or GST profile, respond EXACTLY:
   "The uploaded documents do not contain information to answer this question."
   Do NOT use training knowledge, extrapolate, or speculate under any circumstances.
3. When you find an answer, cite the exact Document Title and File Name.
4. Format with bullet points and short headings. Never output raw escape sequences.
5. If no documents are uploaded, tell the user to upload relevant files first."""

    user_prompt = f"""CONTEXT GROUND TRUTH:
{context_str}

USER QUESTION:
{question}

Provide a direct, grounded answer citing exact document names:"""

    try:
        # Use async-safe LLM call to avoid blocking the event loop
        answer_text = await generate_async(
            prompt=user_prompt,
            system=system_prompt,
            json_mode=False,
            workspace="knowledge_hub"
        )
    except Exception as e:
        print(f"[KNOWLEDGE HUB RAG] LLM generate exception ({str(e)}).")
        if ground_truth_excerpts:
            doc_quotes = []
            seen_excerpts = set()
            for idx, ex in enumerate(ground_truth_excerpts[:5], 1):
                clean_ex = clean_text_excerpt(ex['excerpt'])
                if clean_ex and clean_ex not in seen_excerpts:
                    seen_excerpts.add(clean_ex)
                    doc_quotes.append(f"• **[{ex['document_title']}]**:\n  \"{clean_ex}\"")

            answer_text = f"Based on your uploaded Ground Truth document(s) for **{company_name}**:\n\n### Ground Truth Policy Excerpts:\n" + "\n\n".join(doc_quotes) + "\n\n---\n*Grounded strictly in your uploaded Knowledge Vault files.*"
        else:
            answer_text = "The uploaded documents do not contain information to answer this question."

    # If the answer indicates no content found, clear any accidental excerpts
    if "do not contain information" in answer_text.lower():
        ground_truth_excerpts = []

    return {
        "answer": answer_text,
        "company_context": context_str.strip(),
        "sources": list(set(sources)),
        "ground_truth_excerpts": ground_truth_excerpts
    }
