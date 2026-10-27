import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.db.base import Base
from app.shared.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Organization(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """The tenant: one company. Every business record belongs to exactly one organisation."""
    __tablename__ = "organizations"
    __table_args__ = {"schema": "core"}

    legal_name: Mapped[str] = mapped_column(String, nullable=False)
    trade_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # private_limited | public_limited | llp | partnership | sole_proprietorship | opc | trust_society | other
    entity_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    gstin: Mapped[Optional[str]] = mapped_column(String(15), nullable=True, unique=True)
    pan: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    cin_or_llpin: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    udyam_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    msme_category: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # micro|small|medium|none|unknown
    industry: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    state_code: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    state_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    employee_band: Mapped[Optional[str]] = mapped_column(String, nullable=True)   # 1-9|10-19|20-49|50-199|200+
    turnover_band: Mapped[Optional[str]] = mapped_column(String, nullable=True)   # lt20l|20l-1.5cr|1.5-5cr|5-20cr|20-50cr|gt50cr
    gst_filing_frequency: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # monthly|quarterly|none
    # {"gst": true, "pf": false, "esi": false, "pt": true, "shops": true, "tds": true}
    registrations: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    registry_profile: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)   # raw live-lookup response
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    memberships: Mapped[list["Membership"]] = relationship("Membership", back_populates="organization", cascade="all, delete-orphan")


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """User representation in core schema."""
    __tablename__ = "users"
    __table_args__ = {"schema": "core"}

    full_name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(
        String,
        nullable=False,
        server_default="business_owner"  # demo-mode persona: 'business_owner', 'ca', 'legal_reviewer'
    )
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True, unique=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    documents: Mapped[list["Document"]] = relationship("Document", back_populates="uploader")
    memberships: Mapped[list["Membership"]] = relationship("Membership", back_populates="user", cascade="all, delete-orphan")


class Membership(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A user's role inside an organisation."""
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="uq_membership_user_org"),
        {"schema": "core"},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, nullable=False, server_default="owner")  # owner|admin|member|viewer|ca

    user: Mapped[User] = relationship("User", back_populates="memberships")
    organization: Mapped[Organization] = relationship("Organization", back_populates="memberships")


class AuditEvent(Base, UUIDPrimaryKeyMixin):
    """Append-only record of who did what. Never updated or deleted by application code."""
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_org_created", "organization_id", "created_at"),
        {"schema": "core"},
    )

    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)          # e.g. contract.uploaded
    entity_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


class Document(Base, UUIDPrimaryKeyMixin):
    """Uploaded Document representation in core schema."""
    __tablename__ = "documents"
    __table_args__ = {"schema": "core"}

    workspace: Mapped[str] = mapped_column(String, nullable=False)  # e.g., 'contract_intelligence'
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.organizations.id", ondelete="CASCADE"), nullable=True, index=True)

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
from app.workspaces.contract_intelligence.models import Contract, Clause, NegotiationSuggestion, Segment, Finding, ChatMessage  # noqa: E402
from app.workspaces.vendor_intelligence.models import VendorCheck, Vendor  # noqa: E402
from app.workspaces.legal_notice_center.models import Notice, DraftReply, NoticeCase, ReplyDraft  # noqa: E402
from app.workspaces.compliance_center.models import ComplianceTask, ComplianceDocumentAnalysis  # noqa: E402
from app.workspaces.knowledge_hub.models import RegisteredCompany, CompanyDocument, KnowledgeDocument, DocChunk, Conversation, ChatTurn  # noqa: E402
