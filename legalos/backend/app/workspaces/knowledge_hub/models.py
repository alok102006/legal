import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import String, Date, DateTime, ForeignKey, text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.shared.db.base import Base
from app.shared.db.mixins import UUIDPrimaryKeyMixin, TimestampMixin


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

    company: Mapped[RegisteredCompany] = relationship("RegisteredCompany", back_populates="documents")

