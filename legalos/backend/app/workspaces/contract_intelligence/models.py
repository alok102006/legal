import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.db.base import Base
from app.shared.db.mixins import UUIDPrimaryKeyMixin


class Contract(Base, UUIDPrimaryKeyMixin):
    """A contract uploaded by an organisation and analysed by the engine."""
    __tablename__ = "contracts"
    __table_args__ = {"schema": "contract_intelligence"}

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String, nullable=True)
    counterparty_name: Mapped[str] = mapped_column(String, nullable=True)
    # queued | processing | analyzed | failed
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="processing")
    # processing progress: parsing | ocr | reading | analysing | verifying | scoring | done
    stage: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_kind: Mapped[Optional[str]] = mapped_column(String, nullable=True)       # auth|quota|unavailable|invalid_output|bad_input|internal
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)    # user-presentable

    contract_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    client_party: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    summary_points: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    facts: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    overall_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(String, nullable=True)       # low|medium|high
    score_breakdown: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    warnings: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ocr_used: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    prompt_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    rules_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    analyzed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="contract")
    segments: Mapped[list["Segment"]] = relationship(
        "Segment", back_populates="contract", cascade="all, delete-orphan", order_by="Segment.seg_index")
    findings: Mapped[list["Finding"]] = relationship(
        "Finding", back_populates="contract", cascade="all, delete-orphan", order_by="Finding.sort_order")
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="contract", cascade="all, delete-orphan", order_by="ChatMessage.created_at")
    # Legacy (v1) clause rows - kept so existing data/migrations stay valid
    clauses: Mapped[list["Clause"]] = relationship(
        "Clause",
        back_populates="contract",
        cascade="all, delete-orphan",
        order_by="Clause.clause_index"
    )


class Segment(Base, UUIDPrimaryKeyMixin):
    """A clause/section of the contract with its page reference (what findings cite)."""
    __tablename__ = "segments"
    __table_args__ = (Index("ix_segments_contract", "contract_id", "seg_index"), {"schema": "contract_intelligence"})

    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contract_intelligence.contracts.id", ondelete="CASCADE"), nullable=False)
    seg_index: Mapped[int] = mapped_column(Integer, nullable=False)
    seg_id: Mapped[str] = mapped_column(String, nullable=False)       # "S7" as shown to the LLM and UI
    number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    heading: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    page_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    contract: Mapped[Contract] = relationship("Contract", back_populates="segments")


class Finding(Base, UUIDPrimaryKeyMixin):
    """A risk finding: AI (quote-verified), rule-engine, or a missing protection."""
    __tablename__ = "findings"
    __table_args__ = (Index("ix_findings_contract", "contract_id", "sort_order"), {"schema": "contract_intelligence"})

    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contract_intelligence.contracts.id", ondelete="CASCADE"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    source: Mapped[str] = mapped_column(String, nullable=False)       # ai | rule | missing
    category: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)     # low|medium|high|critical
    title: Mapped[str] = mapped_column(String, nullable=False)
    why_it_matters: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggested_wording: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quote: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    segment_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    page: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    counts_toward_score: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    rule_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    legal_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    legal_ref: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    condition_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="open")   # open | resolved | dismissed

    contract: Mapped[Contract] = relationship("Contract", back_populates="findings")


class ChatMessage(Base, UUIDPrimaryKeyMixin):
    """Ask-this-contract conversation."""
    __tablename__ = "chat_messages"
    __table_args__ = {"schema": "contract_intelligence"}

    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contract_intelligence.contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, nullable=False)         # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    found_in_contract: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

    contract: Mapped[Contract] = relationship("Contract", back_populates="messages")


# ---------------------------------------------------------------- legacy (v1) tables

class Clause(Base, UUIDPrimaryKeyMixin):
    """Legacy v1 clause rows (superseded by Segment + Finding)."""
    __tablename__ = "clauses"
    __table_args__ = {"schema": "contract_intelligence"}

    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contract_intelligence.contracts.id", ondelete="CASCADE"),
        nullable=False
    )
    clause_index: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_text: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(String, nullable=True)
    risk_type: Mapped[str] = mapped_column(String, nullable=True, server_default="none")
    risk_score: Mapped[int] = mapped_column(Integer, nullable=True)  # 0 to 100
    qdrant_point_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False
    )

    contract: Mapped[Contract] = relationship("Contract", back_populates="clauses")
    suggestions: Mapped[list["NegotiationSuggestion"]] = relationship(
        "NegotiationSuggestion",
        back_populates="clause",
        cascade="all, delete-orphan"
    )


class NegotiationSuggestion(Base, UUIDPrimaryKeyMixin):
    """Legacy v1 negotiation suggestion."""
    __tablename__ = "negotiation_suggestions"
    __table_args__ = {"schema": "contract_intelligence"}

    clause_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contract_intelligence.clauses.id", ondelete="CASCADE"),
        nullable=False
    )
    suggestion_text: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False
    )

    clause: Mapped[Clause] = relationship("Clause", back_populates="suggestions")
