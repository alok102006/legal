import os
import re
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.exceptions import NotFoundException, BadRequestException
from app.workspaces.knowledge_hub import repository
from app.workspaces.knowledge_hub.models import RegisteredCompany, CompanyDocument
from app.workspaces.knowledge_hub.sandbox_client import fetch_sandbox_company_profile
from app.core.rag.document_parser import parse_document
from app.core.llm.llm_client import generate
from app.core.embeddings.embedder import get_embedder
from app.core.vectorstore.qdrant_client import get_qdrant_client
from qdrant_client.http import models as qmodels


STORAGE_DIR = os.path.join(os.getcwd(), "storage", "knowledge_hub")


def clean_text_excerpt(text: str) -> str:
    """Removes non-printable unicode noise, control characters, and redundant spacing."""
    if not text:
        return ""
    clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ufffd]', '', text)
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
    indexes into Qdrant vector database, and saves to PostgreSQL.
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

    # 5. Persist to PostgreSQL
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

    # 6. Chunk & Index into Qdrant Vector Store
    try:
        embedder = get_embedder()
        qclient = get_qdrant_client()
        
        # Split text into ~600 char overlapping chunks by paragraphs
        paragraphs = re.split(r'\n\s*\n', extracted_text)
        chunks = []
        curr_chunk = ""
        for p in paragraphs:
            p_str = clean_text_excerpt(p)
            if not p_str:
                continue
            if len(curr_chunk) + len(p_str) < 650:
                curr_chunk += ("\n" + p_str if curr_chunk else p_str)
            else:
                if curr_chunk:
                    chunks.append(curr_chunk)
                curr_chunk = p_str
        if curr_chunk:
            chunks.append(curr_chunk)

        if not chunks:
            chunks = [extracted_text[i:i + 600] for i in range(0, len(extracted_text), 500)]

        # Generate embeddings in batch using embedder.embed(chunks)
        embeddings = embedder.embed(chunks[:100])
        points = []

        for c_idx, (chunk, vector) in enumerate(zip(chunks[:100], embeddings)):
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
                        "chunk_text": chunk
                    }
                )
            )

        if points:
            qclient.upsert(
                collection_name="knowledge_base",
                points=points
            )
            print(f"[KNOWLEDGE HUB RAG] Indexed {len(points)} vector chunks into Qdrant 'knowledge_base'.")
    except Exception as e:
        print(f"[KNOWLEDGE HUB RAG] Warning: Vector indexing fallback: {str(e)}")

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


def extract_best_matching_paragraphs(question: str, docs: List[CompanyDocument]) -> List[Dict[str, str]]:
    """
    Ranks paragraphs across all uploaded documents by keyword and semantic overlap
    to produce clean, grounded excerpts for the user's question.
    """
    words = [w.lower() for w in re.findall(r'\w+', question) if len(w) > 2]
    matched_excerpts = []

    for doc in docs:
        if not doc.extracted_text:
            continue
        
        paras = [clean_text_excerpt(p) for p in doc.extracted_text.splitlines() if len(clean_text_excerpt(p)) > 15]
        
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
    company_id: Optional[uuid.UUID] = None
) -> Dict[str, Any]:
    """
    RAG AI Q&A engine taking uploaded PDF, Word, CSV, Excel, and TXT files as strict GROUND TRUTH.
    """
    context_str = ""
    company_name = "Registered Organization"
    ground_truth_excerpts: List[Dict[str, str]] = []
    sources: List[str] = []

    if company_id:
        company = await repository.get_company_by_id(session, company_id)
        if company:
            company_name = company.legal_name
            addr = company.principal_address or {}
            formatted_addr = addr.get("formatted", "Not specified")
            nba_list = ", ".join(company.nature_of_business or []) if company.nature_of_business else "General Business"

            sources.append(f"Official GST Profile ({company.legal_name})")

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
            # 2. Vector / Paragraph RAG Search across uploaded documents
            doc_excerpts_str = ""
            if company.documents:
                # Try Qdrant vector query
                try:
                    embedder = get_embedder()
                    qclient = get_qdrant_client()
                    q_vectors = embedder.embed([question])
                    
                    if q_vectors:
                        q_res = qclient.query_points(
                            collection_name="knowledge_base",
                            query=q_vectors[0],
                            query_filter=qmodels.Filter(
                                must=[
                                    qmodels.FieldCondition(
                                        key="company_id",
                                        match=qmodels.MatchValue(value=str(company_id))
                                    )
                                ]
                            ),
                            limit=5
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
                    ranked = extract_best_matching_paragraphs(question, company.documents)
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
                        # Full document preview if no specific keyword match
                        fallback_chunks = []
                        for doc in company.documents:
                            if doc.extracted_text:
                                c_text = clean_text_excerpt(doc.extracted_text[:1200])
                                fallback_chunks.append(f"--- Document Ground Truth: [{doc.title}] ({doc.file_name or 'Uploaded File'}) ---\n{c_text}")
                                ground_truth_excerpts.append({
                                    "document_title": doc.title,
                                    "file_name": doc.file_name or "",
                                    "excerpt": c_text[:300]
                                })
                                sources.append(f"{doc.title}")
                        doc_excerpts_str = "\n\n".join(fallback_chunks)

            if not doc_excerpts_str:
                doc_excerpts_str = "No corporate policy files uploaded yet for this company."

            context_str = f"{profile_context}\n\n=== UPLOADED CORPORATE KNOWLEDGE VAULT (GROUND TRUTH DOCUMENTS) ===\n{doc_excerpts_str}"

    system_prompt = """You are LegalOS Grounded Knowledge AI.
Answer the user's question using the provided Corporate Knowledge Vault uploaded documents and GST profile as STRICT GROUND TRUTH.

RULES:
1. Ground your answer in the provided document excerpts.
2. Explicitly cite the exact Document Title / File Name when referencing policies, numbers, or rules.
3. Format output cleanly using bullet points and headings without raw escape sequences."""

    user_prompt = f"""CONTEXT GROUND TRUTH:
{context_str}

USER QUESTION:
{question}

Provide a direct, grounded answer citing exact document names:"""

    try:
        answer_text = generate(
            prompt=user_prompt,
            system=system_prompt,
            json_mode=False,
            workspace="knowledge_hub"
        )
    except Exception as e:
        print(f"[KNOWLEDGE HUB RAG] LLM generate exception ({str(e)}). Generating grounded answer directly from document chunks.")
        
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
            answer_text = f"Based on the records for **{company_name}**:\n\n• **GST Profile**: Registered as {company_name}\n• **Status**: No direct matching text excerpts were found in the uploaded documents for this question.\n\nPlease ask a question related to your uploaded policy topics or upload additional PDF/Word/Excel documents."

    return {
        "answer": answer_text,
        "company_context": context_str.strip(),
        "sources": list(set(sources)),
        "ground_truth_excerpts": ground_truth_excerpts
    }
