import uuid
import json
import traceback
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.session import async_session_maker
from app.shared.storage import file_storage
from app.shared.exceptions import NotFoundException
from app.core.rag import rag_pipeline
from app.core.llm import llm_client
from app.core.llm.prompts.legal_notice_prompts import (
    LEGAL_NOTICE_ANALYSIS_SYSTEM,
    LEGAL_NOTICE_ANALYSIS_USER
)
from app.workspaces.legal_notice_center import repository
from app.workspaces.legal_notice_center.models import Notice, DraftReply


async def create_and_start_analysis(
    session: AsyncSession,
    file_bytes: bytes,
    filename: str,
    user_id: uuid.UUID
) -> Notice:
    """
    Saves document to db, creates notice record in 'processing' status,
    and returns the Notice object.
    """
    # 1. Store core Document record
    storage_path = await file_storage.save_file(filename, file_bytes)
    doc = await repository.create_document(
        session=session,
        workspace="legal_notice_center",
        original_filename=filename,
        storage_path=storage_path,
        uploaded_by=user_id
    )
    
    # 2. Create initial Notice record
    # Set defaults; real classification will be populated by the async worker
    notice = await repository.create_notice(
        session=session,
        document_id=doc.id,
        raw_text="Processing notice analysis..."
    )
    
    return notice


async def run_async_notice_analysis(
    notice_id: uuid.UUID,
    file_bytes: bytes,
    filename: str,
    document_id: uuid.UUID
) -> None:
    """
    Asynchronous worker doing RAG indexing and LLM notice parsing.
    """
    async with async_session_maker() as session:
        try:
            print(f"[NOTICE SERVICE] Starting background analysis for notice_id={notice_id}")
            
            # 1. RAG Ingest
            metadata = {
                "document_id": str(document_id),
                "notice_id": str(notice_id)
            }
            
            rag_pipeline.ingest_document(
                file_bytes=file_bytes,
                filename=filename,
                workspace="legal_notice_center",
                metadata=metadata
            )
            
            processed_chunks = metadata.get("processed_chunks", [])
            if not processed_chunks:
                raise ValueError("No text could be parsed from the notice document.")
                
            # Construct notice raw text
            full_text = "\n\n".join([chunk["text"] for chunk in processed_chunks])
            
            # 2. Run LLM notice parsing and classification (json_mode=True)
            prompt = LEGAL_NOTICE_ANALYSIS_USER.format(notice_text=full_text)
            
            try:
                response_json = llm_client.generate(
                    prompt=prompt,
                    system=LEGAL_NOTICE_ANALYSIS_SYSTEM,
                    json_mode=True,
                    workspace="legal_notice_center"
                )
                analysis = json.loads(response_json)
                
                notice_type = analysis.get("notice_type", "other")
                urgency = analysis.get("urgency", "medium")
                reply_text = analysis.get("reply_text", "")
            except Exception as llm_err:
                print(f"[NOTICE SERVICE] LLM Analysis failed: {llm_err}. Using fallback.")
                notice_type = "other"
                urgency = "medium"
                reply_text = (
                    "Dear Sir/Madam,\n\n"
                    "We are in receipt of your legal notice. We have initiated an internal review "
                    "of the claims and will submit a formal response shortly."
                )
                
            # 3. Update Notice record and create initial DraftReply
            notice = await session.get(Notice, notice_id)
            if notice:
                notice.raw_text = full_text
                notice.notice_type = notice_type
                notice.urgency = urgency
                
                # Append initial draft reply
                await repository.add_draft_reply(
                    session=session,
                    notice_id=notice_id,
                    reply_text=reply_text
                )
                
            await session.commit()
            print(f"[NOTICE SERVICE] Background analysis successfully completed for notice_id={notice_id}")
            
        except Exception as err:
            traceback.print_exc()
            print(f"[NOTICE SERVICE] Background analysis failed for notice_id={notice_id}: {str(err)}")
            await session.rollback()
            
            # Set to fallback failed state
            try:
                notice = await session.get(Notice, notice_id)
                if notice:
                    notice.raw_text = "Parsing failed."
                    notice.notice_type = "other"
                    notice.urgency = "medium"
                    
                    await repository.add_draft_reply(
                        session=session,
                        notice_id=notice_id,
                        reply_text="Failed to analyze legal notice. Please try again."
                    )
                    await session.commit()
            except Exception as update_err:
                print(f"[NOTICE SERVICE] Error setting failed state: {update_err}")


async def regenerate_reply(
    session: AsyncSession,
    notice_id: uuid.UUID
) -> DraftReply:
    """
    Runs a RAG-enhanced generation to draft a new response letter for the notice.
    """
    notice = await repository.get_notice_by_id(session, notice_id)
    if not notice:
        raise ValueError(f"Notice with ID {notice_id} not found.")
        
    print(f"[NOTICE SERVICE] Regenerating reply for notice_id={notice_id}...")
    
    # Run RAG retrieve and generate
    try:
        response_json = rag_pipeline.retrieve_and_generate(
            query="Draft formal legal reply letter addressing notice points",
            workspace="legal_notice_center",
            system_prompt=LEGAL_NOTICE_ANALYSIS_SYSTEM,
            top_k=5,
            filters={"document_id": str(notice.document_id)} if notice.document_id else None,
            json_mode=True
        )
        analysis = json.loads(response_json)
        reply_text = analysis.get("reply_text", "")
        if not reply_text:
            raise ValueError("LLM returned empty reply letter.")
    except Exception as e:
        print(f"[NOTICE SERVICE] RAG regeneration failed: {e}. Falling back to default generation.")
        # Fallback to direct prompt without RAG retrieval (using raw text)
        prompt = LEGAL_NOTICE_ANALYSIS_USER.format(notice_text=notice.raw_text)
        response_json = llm_client.generate(
            prompt=prompt,
            system=LEGAL_NOTICE_ANALYSIS_SYSTEM,
            json_mode=True,
            workspace="legal_notice_center"
        )
        analysis = json.loads(response_json)
        reply_text = analysis.get("reply_text", "Dear Sir/Madam,\n\nWe are reviewing this notice.")

    # Save the new draft reply
    draft = await repository.add_draft_reply(session, notice_id, reply_text)
    return draft


async def get_notice_details(
    session: AsyncSession,
    notice_id: uuid.UUID
) -> Optional[Notice]:
    """Retrieves full notice profile and draft history."""
    return await repository.get_notice_by_id(session, notice_id)


async def list_notices(
    session: AsyncSession
) -> List[dict]:
    """Lists notice summaries."""
    return await repository.list_notices_with_filenames(session)


async def delete_notice_and_document(session: AsyncSession, notice_id: uuid.UUID) -> None:
    """Deletes notice, associated document from SQL, associated points from Qdrant, and disk file."""
    import os
    from app.shared.db.models import Document
    from app.core.vectorstore import retrieval_service

    notice = await repository.get_notice_by_id(session, notice_id)
    if not notice:
        raise NotFoundException(f"Notice with ID {notice_id} not found.")

    document_id = notice.document_id

    # 1. Delete vectors from Qdrant for legal_notices collection
    if document_id:
        try:
            retrieval_service.delete_by_document("legal_notices", str(document_id))
            print(f"[NOTICE SERVICE] Purged Qdrant points for notice document {document_id}")
        except Exception as qdrant_err:
            print(f"[NOTICE SERVICE] Error deleting points from Qdrant: {qdrant_err}")

    # 2. Delete file from disk if present
    if document_id:
        doc = await session.get(Document, document_id)
        if doc and doc.storage_path and os.path.exists(doc.storage_path):
            try:
                os.remove(doc.storage_path)
                print(f"[NOTICE SERVICE] Deleted notice disk file: {doc.storage_path}")
            except Exception as disk_err:
                print(f"[NOTICE SERVICE] Error deleting file from disk: {disk_err}")
        if doc:
            await session.delete(doc)

    await session.delete(notice)

