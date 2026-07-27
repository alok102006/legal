import uuid
from datetime import date, datetime
from sqlalchemy import String, Integer, ForeignKey, DateTime, Date, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.shared.db.base import Base
from app.shared.db.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class ComplianceTask(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Compliance center task representation."""
    __tablename__ = "compliance_tasks"
    __table_args__ = {"schema": "compliance_center"}

    title: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(
        String, 
        nullable=False, 
        server_default="other"  # 'tax', 'corporate', 'labor', 'license', 'other'
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String, 
        nullable=False, 
        server_default="pending"  # 'pending', 'completed', 'overdue'
    )
    description: Mapped[str] = mapped_column(String, nullable=True)
    penalty_desc: Mapped[str] = mapped_column(String, nullable=True)
    
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.documents.id", ondelete="CASCADE"),
        nullable=True
    )
    
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.users.id", ondelete="SET NULL"),
        nullable=True
    )

    # Relationships
    document = relationship("Document", foreign_keys=[document_id])


class ComplianceDocumentAnalysis(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Compliance center document analysis metadata."""
    __tablename__ = "compliance_document_analyses"
    __table_args__ = {"schema": "compliance_center"}

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    
    authority: Mapped[str] = mapped_column(String, nullable=False)
    document_type: Mapped[str] = mapped_column(String, nullable=False)
    identifier_number: Mapped[str] = mapped_column(String, nullable=True)
    issue_date: Mapped[date] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String, 
        nullable=False, 
        server_default="active"  # 'active', 'expired', 'needs_action', 'warning'
    )
    risk_assessment: Mapped[str] = mapped_column(String, nullable=True)
    
    # Stores list of action items: [{"title": "...", "due_date": "YYYY-MM-DD", "description": "...", "category": "...", "penalty_desc": "..."}]
    extracted_actions: Mapped[dict] = mapped_column(JSONB, nullable=True)

    # Relationships
    document = relationship("Document", foreign_keys=[document_id])
