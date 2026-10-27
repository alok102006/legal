import uuid
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import RequestContext, get_ctx, require_writer
from app.shared.db.session import get_db_session
from app.workspaces.knowledge_hub import schemas, service

router = APIRouter()


# ---------------------------------------------------------------- documents and collections

@router.get("/documents", response_model=List[schemas.DocListItem])
async def list_documents(collection: Optional[str] = None, db: AsyncSession = Depends(get_db_session), ctx: RequestContext = Depends(get_ctx)):
    return await service.list_documents(db, ctx, collection)


@router.get("/collections", response_model=List[schemas.CollectionOut])
async def list_collections(db: AsyncSession = Depends(get_db_session), ctx: RequestContext = Depends(get_ctx)):
    return await service.list_collections(db, ctx)


@router.post("/documents/upload", response_model=schemas.DocListItem, status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks, file: UploadFile = File(...), category: Optional[str] = Form(None), title: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db_session), ctx: RequestContext = Depends(require_writer),
):
    kd = await service.create_upload(db, ctx, await file.read(), file.filename or "document.txt", category, title)
    background_tasks.add_task(service.run_ingest, kd.id)
    return service.to_list_item(kd)


@router.get("/documents/{doc_id}", response_model=schemas.DocDetail)
async def get_document(doc_id: uuid.UUID, db: AsyncSession = Depends(get_db_session), ctx: RequestContext = Depends(get_ctx)):
    return await service.get_detail(db, ctx, doc_id)


class DocUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    category: Optional[str] = Field(default=None, max_length=80)


@router.patch("/documents/{doc_id}", response_model=schemas.DocListItem)
async def update_document(doc_id: uuid.UUID, body: DocUpdate, db: AsyncSession = Depends(get_db_session), ctx: RequestContext = Depends(require_writer)):
    return service.to_list_item(await service.update_document(db, ctx, doc_id, body.title, body.category))


@router.post("/documents/{doc_id}/retry", response_model=schemas.DocListItem, status_code=202)
async def retry_document(doc_id: uuid.UUID, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db_session), ctx: RequestContext = Depends(require_writer)):
    kd = await service.prepare_retry(db, ctx, doc_id)
    background_tasks.add_task(service.run_ingest, kd.id)
    return service.to_list_item(kd)


@router.get("/documents/{doc_id}/file")
async def download_file(doc_id: uuid.UUID, db: AsyncSession = Depends(get_db_session), ctx: RequestContext = Depends(get_ctx)):
    path, name = await service.get_file(db, ctx, doc_id)
    return FileResponse(path, filename=name)


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: uuid.UUID, db: AsyncSession = Depends(get_db_session), ctx: RequestContext = Depends(require_writer)):
    await service.delete_document(db, ctx, doc_id)
    return {"status": "deleted"}


@router.get("/search", response_model=List[schemas.SearchHit])
async def search(q: str = Query(..., min_length=2, max_length=300), collection: Optional[str] = None,
                 db: AsyncSession = Depends(get_db_session), ctx: RequestContext = Depends(get_ctx)):
    return await service.search(db, ctx, q, collection)


@router.get("/suggestions", response_model=schemas.SuggestionsOut)
async def get_suggestions(collection: Optional[str] = None, db: AsyncSession = Depends(get_db_session), ctx: RequestContext = Depends(get_ctx)):
    return {"questions": await service.suggestions(db, ctx, collection)}


# ---------------------------------------------------------------- conversations

@router.get("/conversations", response_model=List[schemas.ConversationOut])
async def list_conversations(db: AsyncSession = Depends(get_db_session), ctx: RequestContext = Depends(get_ctx)):
    return await service.list_conversations(db, ctx)


@router.post("/conversations", response_model=schemas.ConversationOut, status_code=201)
async def create_conversation(body: schemas.ConversationCreate, db: AsyncSession = Depends(get_db_session), ctx: RequestContext = Depends(require_writer)):
    return await service.create_conversation(db, ctx, body.collection, body.title)


@router.get("/conversations/{conv_id}", response_model=schemas.ConversationDetail)
async def get_conversation(conv_id: uuid.UUID, db: AsyncSession = Depends(get_db_session), ctx: RequestContext = Depends(get_ctx)):
    return await service.get_conversation(db, ctx, conv_id)


@router.patch("/conversations/{conv_id}", response_model=schemas.ConversationOut)
async def update_conversation(conv_id: uuid.UUID, body: schemas.ConversationUpdate, db: AsyncSession = Depends(get_db_session), ctx: RequestContext = Depends(require_writer)):
    data = body.model_dump(exclude_unset=True)
    return await service.update_conversation(db, ctx, conv_id, data.get("title"), data.get("collection"), "collection" in data)


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: uuid.UUID, db: AsyncSession = Depends(get_db_session), ctx: RequestContext = Depends(require_writer)):
    await service.delete_conversation(db, ctx, conv_id)
    return {"status": "deleted"}


@router.post("/conversations/{conv_id}/ask", response_model=schemas.TurnOut)
async def ask(conv_id: uuid.UUID, body: schemas.AskIn, db: AsyncSession = Depends(get_db_session), ctx: RequestContext = Depends(require_writer)):
    """Answers only from the company's own documents, with verified quotes and page numbers."""
    return await service.ask(db, ctx, conv_id, body.question)


@router.post("/conversations/{conv_id}/ask/stream")
async def ask_stream(conv_id: uuid.UUID, body: schemas.AskIn, ctx: RequestContext = Depends(require_writer)):
    """Same as /ask but as server-sent events: `stage`, `delta`, then `done` (the stored turn) or `error`."""
    return StreamingResponse(service.ask_stream(ctx, conv_id, body.question), media_type="text/event-stream",
                            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
