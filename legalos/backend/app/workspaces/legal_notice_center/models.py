import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.db.base import Base
from app.shared.db.mixins import UUIDPrimaryKeyMixin


class NoticeCase(Base, UUIDPrimaryKeyMixin):
    """A notice received by an organisation, with the AI's extraction and the deterministic deadline/urgency."""
    __tablename__ = "cases"
    __table_args__ = (Index("ix_cases_org_created", "organization_id", "created_at"), {"schema": "legal_notice_center"})

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.organizations.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.documents.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)       # filename or "Pasted text"
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="processing")   # processing|analyzed|failed|closed
    stage: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_kind: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    notice_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    urgency: Mapped[Optional[str]] = mapped_column(String, nullable=True)              # low|medium|high|critical
    issuer_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reference_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notice_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    received_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    amount_claimed: Mapped[Optional[float]] = mapped_column(Numeric(16, 2), nullable=True)
    response_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    deadline_source: Mapped[Optional[str]] = mapped_column(String, nullable=True)      # stated | statutory_default | unknown
    deadline_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    deadline_quote: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    deadline_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    summary_points: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    demands: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    statutes: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    consequences: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    legal_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    legal_ref: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    facts: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    review_status: Mapped[str] = mapped_column(String, nullable=False, server_default="draft")  # draft|ready_for_lawyer|lawyer_approved
    compliance_task_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    ocr_used: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    prompt_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    analyzed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    drafts: Mapped[list["ReplyDraft"]] = relationship(
        "ReplyDraft", back_populates="case", cascade="all, delete-orphan", order_by="ReplyDraft.version")


class ReplyDraft(Base, UUIDPrimaryKeyMixin):
    """A version of the reply letter (AI-drafted or edited by the user)."""
    __tablename__ = "reply_drafts"
    __table_args__ = {"schema": "legal_notice_center"}

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("legal_notice_center.cases.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    reply_text: Mapped[str] = mapped_column(Text, nullable=False)
    placeholders: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    points_to_confirm: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    documents_to_gather: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    author: Mapped[str] = mapped_column(String, nullable=False, server_default="ai")   # ai | user
    instructions: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

    case: Mapped[NoticeCase] = relationship("NoticeCase", back_populates="drafts")


# ---------------------------------------------------------------- legacy (v1) tables, kept for existing data

class Notice(Base, UUIDPrimaryKeyMixin):
    """Legacy v1 notice (superseded by NoticeCase)."""
    __tablename__ = "notices"
    __table_args__ = {"schema": "legal_notice_center"}

    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.documents.id", ondelete="SET NULL"), nullable=True)
    raw_text: Mapped[str] = mapped_column(String, nullable=False)
    notice_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    urgency: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

    document = relationship("Document")
    replies: Mapped[list["DraftReply"]] = relationship("DraftReply", back_populates="notice", cascade="all, delete-orphan")


class DraftReply(Base, UUIDPrimaryKeyMixin):
    """Legacy v1 reply draft."""
    __tablename__ = "draft_replies"
    __table_args__ = {"schema": "legal_notice_center"}

    notice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("legal_notice_center.notices.id", ondelete="CASCADE"), nullable=False)
    reply_text: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

    notice: Mapped[Notice] = relationship("Notice", back_populates="replies")
