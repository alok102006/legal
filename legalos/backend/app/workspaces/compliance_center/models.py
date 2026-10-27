import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.db.base import Base
from app.shared.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ComplianceTask(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One obligation with a due date. System tasks come from the rules engine and are identified
    by (organization, rule_id, period_key); custom tasks are created by users and never auto-deleted."""
    __tablename__ = "compliance_tasks"
    __table_args__ = (
        Index(
            "uq_compliance_task_rule_period", "organization_id", "rule_id", "period_key",
            unique=True, postgresql_where=text("rule_id IS NOT NULL"),
        ),
        Index("ix_compliance_tasks_org_due", "organization_id", "due_date"),
        {"schema": "compliance_center"},
    )

    title: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False, server_default="other")  # tax|corporate|labor|license|other
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="pending")  # pending | completed
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    penalty_desc: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.documents.id", ondelete="CASCADE"), nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.users.id", ondelete="SET NULL"), nullable=True)

    # --- v2 (organisation scoped, rules-engine generated)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.organizations.id", ondelete="CASCADE"), nullable=True)
    rule_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    period_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    period_label: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    form_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    authority: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    needs_confirmation: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    confirm_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    rules_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completion_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    document = relationship("Document", foreign_keys=[document_id])


class ComplianceDocumentAnalysis(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Compliance center document analysis metadata (document intake is being rebuilt)."""
    __tablename__ = "compliance_document_analyses"
    __table_args__ = {"schema": "compliance_center"}

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.documents.id", ondelete="CASCADE"), nullable=False, unique=True)

    authority: Mapped[str] = mapped_column(String, nullable=False)
    document_type: Mapped[str] = mapped_column(String, nullable=False)
    identifier_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    issue_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="active")
    risk_assessment: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    extracted_actions: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    document = relationship("Document", foreign_keys=[document_id])
