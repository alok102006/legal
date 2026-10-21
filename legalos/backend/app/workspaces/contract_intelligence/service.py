import json
import uuid
import traceback
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rag import rag_pipeline
from app.core.llm import llm_client
from app.core.llm.prompts.contract_intel_prompts import (
    CONTRACT_METADATA_SYSTEM, CONTRACT_METADATA_USER,
    CLAUSE_ANALYSIS_SYSTEM, CLAUSE_ANALYSIS_USER,
    BATCH_CLAUSE_ANALYSIS_SYSTEM, BATCH_CLAUSE_ANALYSIS_USER,
    NEGOTIATION_SUGGESTION_SYSTEM
)
from app.shared.storage import file_storage
from app.shared.db.session import async_session_maker
from app.shared.exceptions import NotFoundException, BadRequestException
from app.workspaces.contract_intelligence import repository
from app.workspaces.contract_intelligence.models import Contract, Clause, NegotiationSuggestion


async def list_contracts(session: AsyncSession) -> List[dict]:
    """Retrieves all contracts with computed risk metrics."""
    return await repository.list_contracts_with_counts(session)


async def get_contract_details(session: AsyncSession, contract_id: uuid.UUID) -> Contract:
    """Retrieves full details of a single contract."""
    contract = await repository.get_contract_by_id(session, contract_id)
    if not contract:
        raise NotFoundException(f"Contract {contract_id} not found.")
    return contract


async def run_async_contract_analysis(
    contract_id: uuid.UUID,
    file_bytes: bytes,
    filename: str,
    document_id: uuid.UUID
) -> None:
    """
    Background worker that executes the ingestion and analysis pipeline:
    1. Runs RAG ingestion (parse, chunk, embed, indexing)
    2. Runs LLM clause analysis on each chunk
    3. Runs LLM contract metadata extraction
    4. Commits results to PostgreSQL
    """
    # Create a fresh database session for background task
    async with async_session_maker() as session:
        try:
            print(f"[SERVICE] Starting background analysis for contract_id={contract_id}")
            
            # Metadata object for RAG ingestion
            metadata = {
                "document_id": str(document_id),
                "contract_id": str(contract_id)
            }
            
            # 1. RAG Ingest (modifies metadata dictionary to include "processed_chunks")
            rag_pipeline.ingest_document(
                file_bytes=file_bytes,
                filename=filename,
                workspace="contract_intelligence",
                metadata=metadata
            )
            
            processed_chunks = metadata.get("processed_chunks", [])
            if not processed_chunks:
                raise ValueError("No text clauses could be parsed from the document.")
            
            # 2. Analyze clauses in batches of 8 using LLM (avoids 429 rate limit & cuts runtime from 120s to <25s)
            BATCH_SIZE = 8
            for b_start in range(0, len(processed_chunks), BATCH_SIZE):
                batch_chunks = processed_chunks[b_start:b_start + BATCH_SIZE]
                print(f"[SERVICE] Analyzing clause batch {b_start} to {b_start + len(batch_chunks)} of {len(processed_chunks)}...")

                clauses_block_lines = []
                for chunk in batch_chunks:
                    c_idx = chunk["clause_index"]
                    c_text = chunk["text"]
                    clauses_block_lines.append(f"--- CLAUSE {c_idx} ---\n{c_text}")
                clauses_block = "\n\n".join(clauses_block_lines)

                prompt = BATCH_CLAUSE_ANALYSIS_USER.format(n=len(batch_chunks), clauses_block=clauses_block)

                analyses_map = {}
                parsed_list = []
                try:
                    response_json = llm_client.generate(
                        prompt=prompt,
                        system=BATCH_CLAUSE_ANALYSIS_SYSTEM,
                        json_mode=True,
                        workspace="contract_intelligence"
                    )
                    parsed = json.loads(response_json)
                    if isinstance(parsed, list):
                        parsed_list = parsed
                        for item in parsed:
                            idx = item.get("clause_idx")
                            if idx is not None:
                                analyses_map[idx] = item
                    elif isinstance(parsed, dict):
                        # Handle potential object wrapping e.g. {"clauses": [...]}
                        for val in parsed.values():
                            if isinstance(val, list):
                                parsed_list = val
                                for item in val:
                                    if isinstance(item, dict) and item.get("clause_idx") is not None:
                                        analyses_map[item["clause_idx"]] = item
                except Exception as batch_err:
                    print(f"[SERVICE] Batch LLM analysis failed: {batch_err}. Using fallback.")

                for i, chunk in enumerate(batch_chunks):
                    clause_idx = chunk["clause_index"]
                    clause_text = chunk["text"]
                    point_id = chunk.get("point_id")

                    analysis = analyses_map.get(clause_idx)
                    if not analysis and i < len(parsed_list):
                        analysis = parsed_list[i]

                    if not analysis:
                        analysis = {
                            "summary": clause_text[:120] + "...",
                            "risk_type": "none",
                            "risk_score": 0
                        }

                    await repository.add_clause(
                        session=session,
                        contract_id=contract_id,
                        clause_index=clause_idx,
                        raw_text=clause_text,
                        summary=analysis.get("summary", ""),
                        risk_type=analysis.get("risk_type", "none"),
                        risk_score=int(analysis.get("risk_score", 0)),
                        qdrant_point_id=uuid.UUID(point_id) if point_id else None
                    )
            
            # 3. Extract general metadata (Contract Title and Counterparty)
            # We take the first 4000 characters of the document text for context
            full_text = "\n".join([c["text"] for c in processed_chunks])
            metadata_context = full_text[:4000]
            
            print("[SERVICE] Extracting contract metadata...")
            meta_prompt = CONTRACT_METADATA_USER.format(document_text=metadata_context)
            try:
                meta_response_json = llm_client.generate(
                    prompt=meta_prompt,
                    system=CONTRACT_METADATA_SYSTEM,
                    json_mode=True,
                    workspace="contract_intelligence"
                )
                meta_analysis = json.loads(meta_response_json)
                title = meta_analysis.get("title", f"Contract - {filename}")
                counterparty = meta_analysis.get("counterparty_name", "Unknown Counterparty")
            except Exception as meta_err:
                print(f"[SERVICE] Metadata extraction failed: {meta_err}. Using fallback values.")
                title = f"Contract - {filename}"
                counterparty = "Unknown Counterparty"
                
            # 4. Save metadata and mark status as analyzed
            await repository.update_contract_metadata(
                session=session,
                contract_id=contract_id,
                title=title,
                counterparty_name=counterparty,
                status="analyzed"
            )
            
            await session.commit()
            print(f"[SERVICE] Background analysis successfully completed for contract_id={contract_id}")
            
        except Exception as err:
            traceback.print_exc()
            print(f"[SERVICE] Background analysis failed for contract_id={contract_id}: {str(err)}")
            # Rollback any pending work and mark contract as failed
            await session.rollback()
            try:
                await repository.update_contract_metadata(
                    session=session,
                    contract_id=contract_id,
                    title=f"Failed - {filename}",
                    counterparty_name="Failed",
                    status="failed"
                )
                await session.commit()
            except Exception as update_err:
                print(f"[SERVICE] Double-fault setting contract status to failed: {update_err}")


async def create_and_start_analysis(
    session: AsyncSession,
    file_bytes: bytes,
    filename: str,
    user_id: Optional[uuid.UUID] = None
) -> Contract:
    """
    Saves document to disk, initializes DB records, and returns the Contract stub.
    The actual vector ingest and analysis are delegated to a background worker.
    """
    # 1. Save file to disk
    storage_path = await file_storage.save_file(filename, file_bytes)
    
    # 2. Database entry creation
    doc = await repository.create_document(
        session=session,
        workspace="contract_intelligence",
        original_filename=filename,
        storage_path=storage_path,
        uploaded_by=user_id
    )
    
    contract = await repository.create_contract(
        session=session,
        document_id=doc.id,
        title=f"Analyzing {filename}...",
        counterparty_name="Extracting..."
    )
    
    await session.commit()
    # Refresh to ensure ID is populated
    await session.refresh(contract)
    return contract


async def generate_clause_suggestion(
    session: AsyncSession,
    contract_id: uuid.UUID,
    clause_id: uuid.UUID
) -> NegotiationSuggestion:
    """
    Generates a negotiation suggestion for a specific clause.
    Uses RAG retrieval service to pull contract context from Qdrant
    before executing LLM recommendation prompt.
    """
    # 1. Verify clause and contract
    clause = await repository.get_clause_by_id(session, clause_id)
    if not clause or clause.contract_id != contract_id:
        raise NotFoundException(f"Clause {clause_id} not found under contract {contract_id}.")
        
    contract = await repository.get_contract_by_id(session, contract_id)
    if not contract:
        raise NotFoundException(f"Contract {contract_id} not found.")

    # 2. Check if a suggestion already exists in SQL to avoid duplication
    stmt = select(NegotiationSuggestion).where(NegotiationSuggestion.clause_id == clause_id)
    existing = await session.execute(stmt)
    suggestion = existing.scalar_one_or_none()
    if suggestion:
        return suggestion
        
    # 3. Use retrieval_and_generate pipeline to run search filtered by document
    query = (
        f"Analyze this target clause: \n{clause.raw_text}\n\n"
        f"Provide negotiation recommendations."
    )
    
    # RAG parameters
    filters = {"document_id": str(contract.document_id)}
    
    # Run the prompt through the core retrieval pipeline
    suggestion_text = rag_pipeline.retrieve_and_generate(
        query=query,
        workspace="contract_intelligence",
        system_prompt=NEGOTIATION_SUGGESTION_SYSTEM,
        top_k=3,
        filters=filters,
        json_mode=False
    )
    
    # 4. Save and return suggestion
    suggestion = await repository.add_suggestion(
        session=session,
        clause_id=clause_id,
        suggestion_text=suggestion_text
    )
    await session.commit()
    return suggestion


async def delete_contract_and_document(session: AsyncSession, contract_id: uuid.UUID) -> None:
    """Deletes contract, associated document from SQL, and associated points from Qdrant."""
    from app.shared.db.models import Document
    import os
    
    contract = await repository.get_contract_by_id(session, contract_id)
    if not contract:
        raise NotFoundException(f"Contract {contract_id} not found.")
        
    document_id = contract.document_id
    
    # 1. Delete vectors from Qdrant
    try:
        from app.core.vectorstore import retrieval_service
        # Collection for contract intelligence is "contract_clauses"
        retrieval_service.delete_by_document("contract_clauses", str(document_id))
    except Exception as qdrant_err:
        print(f"[SERVICE] Error deleting points from Qdrant for document {document_id}: {qdrant_err}")
        
    # 2. Delete file from disk
    doc = await session.get(Document, document_id)
    if doc and doc.storage_path:
        try:
            if os.path.exists(doc.storage_path):
                os.remove(doc.storage_path)
                print(f"[SERVICE] Deleted local file: {doc.storage_path}")
        except Exception as disk_err:
            print(f"[SERVICE] Error deleting file from disk: {disk_err}")
            
    # 3. Delete Document from PostgreSQL (cascades to Contract, Clause, Suggestions)
    if doc:
        await session.delete(doc)
    else:
        await session.delete(contract)
        
    await session.commit()
    print(f"[SERVICE] Successfully deleted contract {contract_id} and document {document_id}")

