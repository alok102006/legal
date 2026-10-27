import uuid
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class DocListItem(BaseModel):
    id: uuid.UUID
    title: str
    filename: Optional[str] = None
    category: Optional[str] = None
    doc_type: Optional[str] = None
    language: Optional[str] = None
    file_type: Optional[str] = None
    page_count: Optional[int] = None
    status: str
    stage: Optional[str] = None
    review_state: str = "pending"
    expiry_date: Optional[date] = None
    expiry_label: Optional[str] = None
    concern_count: int = 0
    error_kind: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime


class ConcernOut(BaseModel):
    title: str
    why_it_matters: str
    quote: str
    page: Optional[int] = None
    verified: bool = False
    exact: bool = False


class FactOut(BaseModel):
    label: str
    value: str


class ChunkOut(BaseModel):
    chunk_index: int
    page: Optional[int] = None
    section: Optional[str] = None
    text: str


class DocDetail(DocListItem):
    summary_points: List[str] = []
    key_facts: List[FactOut] = []
    concerns: List[ConcernOut] = []
    missing_items: List[str] = []
    suggested_questions: List[str] = []
    review_error: Optional[str] = None
    chunk_count: int = 0
    in_calendar: bool = False
    ocr_used: bool = False
    chunks: List[ChunkOut] = []


class CollectionOut(BaseModel):
    name: str
    count: int
    ready: int


class ConversationOut(BaseModel):
    id: uuid.UUID
    title: str
    collection: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ConversationCreate(BaseModel):
    collection: Optional[str] = Field(default=None, max_length=80)
    title: Optional[str] = Field(default=None, max_length=120)


class ConversationUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    collection: Optional[str] = Field(default=None, max_length=80)


class CitationOut(BaseModel):
    marker: Optional[str] = None
    quote: str
    document_id: Optional[uuid.UUID] = None
    document_title: Optional[str] = None
    page: Optional[int] = None
    section: Optional[str] = None
    verified: bool = False
    exact: bool = False


class SourceOut(BaseModel):
    marker: str
    document_id: uuid.UUID
    document_title: str
    page: Optional[int] = None
    section: Optional[str] = None
    text: str
    via: List[str] = []


class TurnOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    citations: List[CitationOut] = []
    sources: List[SourceOut] = []
    found_in_documents: Optional[bool] = None
    confidence: Optional[int] = None
    created_at: datetime


class ConversationDetail(ConversationOut):
    turns: List[TurnOut] = []


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=2000)


class SuggestionsOut(BaseModel):
    questions: List[str]


class SearchHit(BaseModel):
    document_id: uuid.UUID
    document_title: str
    page: Optional[int] = None
    section: Optional[str] = None
    snippet: str
    via: List[str]
