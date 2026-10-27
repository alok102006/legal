import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Computed, Date, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.db.base import Base
from app.shared.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class KnowledgeDocument(Base, UUIDPrimaryKeyMixin):
    """A company document in the vault (policy, contract, certificate...), searchable and reviewed by AI."""
    __tablename__ = "docs"
    __table_args__ = (Index("ix_docs_org_created", "organization_id", "created_at"), {"schema": "knowledge_hub"})

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.organizations.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.documents.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    filename: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String, nullable=True)           # chosen by the user
    file_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="processing")   # processing|ready|failed
    stage: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_kind: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # AI review (can fail independently of indexing: the document stays searchable)
    review_state: Mapped[str] = mapped_column(String, nullable=False, server_default="pending")  # pending|done|failed
    review_error: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    doc_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    summary_points: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    key_facts: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    concerns: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    missing_items: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_label: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    expiry_task_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    ocr_used: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    prompt_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    embed_model: Mapped[Optional[str]] = mapped_column(String, nullable=True)        # which embedding model indexed it
    suggested_questions: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

    chunks: Mapped[list["DocChunk"]] = relationship("DocChunk", back_populates="doc", cascade="all, delete-orphan",
                                                    order_by="DocChunk.chunk_index")


class Conversation(Base, UUIDPrimaryKeyMixin):
    """A chat thread over the organisation's documents (optionally scoped to one collection)."""
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_org_updated", "organization_id", "updated_at"), {"schema": "knowledge_hub"})

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.organizations.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False, server_default="New chat")
    collection: Mapped[Optional[str]] = mapped_column(String, nullable=True)     # None = all documents
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("core.users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

    messages: Mapped[list["ChatTurn"]] = relationship("ChatTurn", back_populates="conversation", cascade="all, delete-orphan", order_by="ChatTurn.created_at")


class ChatTurn(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "chat_turns"
    __table_args__ = {"schema": "knowledge_hub"}

    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_hub.conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, nullable=False)                        # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    sources: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    found_in_documents: Mapped[Optional[bool]] = mapped_column(nullable=True)
    confidence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)        # 0-100, computed not asked
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="messages")


class DocChunk(Base, UUIDPrimaryKeyMixin):
    """A page-aware passage. `tsv` powers keyword search; the same id is the vector point id in Qdrant."""
    __tablename__ = "chunks"
    __table_args__ = (
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
        Index("ix_chunks_tsv_simple", "tsv_simple", postgresql_using="gin"),
        Index("ix_chunks_org_doc", "organization_id", "doc_id"),
        {"schema": "knowledge_hub"},
    )

    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_hub.docs.id", ondelete="CASCADE"), nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    section: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    kind: Mapped[str] = mapped_column(String, nullable=False, server_default="text")
    tsv = mapped_column(TSVECTOR, Computed("to_tsvector('english', coalesce(section,'') || ' ' || text)", persisted=True))
    # `simple` config: no stemming/stopwords, so Hindi/Gujarati/Hinglish tokens are matched as typed
    tsv_simple = mapped_column(TSVECTOR, Computed("to_tsvector('simple', coalesce(section,'') || ' ' || text)", persisted=True))

    doc: Mapped[KnowledgeDocument] = relationship("KnowledgeDocument", back_populates="chunks")


# ---------------------------------------------------------------- legacy (v1) tables, kept for existing data

class RegisteredCompany(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Registered Company representation in knowledge_hub schema."""
    __tablename__ = "registered_companies"
    __table_args__ = {"schema": "knowledge_hub"}

    gstin: Mapped[str] = mapped_column(String(15), nullable=False, unique=True, index=True)
    legal_name: Mapped[str] = mapped_column(String, nullable=False)
    trade_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    entity_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # Constitution of Business (ctb)
    registration_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    taxpayer_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # dty (Regular, Composition, etc.)
    status: Mapped[str] = mapped_column(String, server_default="Active", nullable=False)
    state_jurisdiction: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    center_jurisdiction: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    principal_address: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    nature_of_business: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    raw_profile_response: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    registered_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.users.id", ondelete="SET NULL"),
        nullable=True
    )

    documents: Mapped[list["CompanyDocument"]] = relationship(
        "CompanyDocument",
        back_populates="company",
        cascade="all, delete-orphan"
    )


class CompanyDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Uploaded Policy/Handook Document associated with a Registered Company."""
    __tablename__ = "company_documents"
    __table_args__ = {"schema": "knowledge_hub"}

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_hub.registered_companies.id", ondelete="CASCADE"),
        nullable=False
    )
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.documents.id", ondelete="SET NULL"),
        nullable=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    document_category: Mapped[str] = mapped_column(String, server_default="Policy", nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    file_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    file_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    extracted_text: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    risk_analysis: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # AI Risk Radar output

    company: Mapped[RegisteredCompany] = relationship("RegisteredCompany", back_populates="documents")

