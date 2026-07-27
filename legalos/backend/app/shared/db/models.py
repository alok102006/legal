import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.shared.db.base import Base
from app.shared.db.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """User representation in core schema."""
    __tablename__ = "users"
    __table_args__ = {"schema": "core"}

    full_name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(
        String,
        nullable=False,
        server_default="business_owner"  # 'business_owner', 'ca', 'legal_reviewer'
    )
    
    documents: Mapped[list["Document"]] = relationship("Document", back_populates="uploader")


class Document(Base, UUIDPrimaryKeyMixin):
    """Uploaded Document representation in core schema."""
    __tablename__ = "documents"
    __table_args__ = {"schema": "core"}

    workspace: Mapped[str] = mapped_column(String, nullable=False)  # e.g., 'contract_intelligence'
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.users.id", ondelete="SET NULL"),
        nullable=True
    )
    
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False
    )

    uploader: Mapped[User] = relationship("User", back_populates="documents")
    # Association with Contract (one-to-one or one-to-many, here it's one-to-one)
    contract: Mapped["Contract"] = relationship(
        "Contract",
        back_populates="document",
        cascade="all, delete-orphan",
        uselist=False
    )

# Import other models at the end of the file to register them in SQLAlchemy's metadata registry
from app.workspaces.contract_intelligence.models import Contract, Clause, NegotiationSuggestion
from app.workspaces.vendor_intelligence.models import VendorCheck
from app.workspaces.legal_notice_center.models import Notice, DraftReply
from app.workspaces.compliance_center.models import ComplianceTask, ComplianceDocumentAnalysis

