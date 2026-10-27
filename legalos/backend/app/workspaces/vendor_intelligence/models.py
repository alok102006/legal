import uuid
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, ForeignKey, DateTime, Date, Integer, Boolean, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.shared.db.base import Base
from app.shared.db.mixins import UUIDPrimaryKeyMixin


class Vendor(Base, UUIDPrimaryKeyMixin):
    """A supplier/vendor of an organisation with its latest deterministic assessment."""
    __tablename__ = "vendors"
    __table_args__ = (
        Index("uq_vendor_org_gstin", "organization_id", "gstin", unique=True, postgresql_where=text("gstin IS NOT NULL")),
        {"schema": "vendor_intelligence"},
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    gstin: Mapped[Optional[str]] = mapped_column(String(15), nullable=True)
    pan: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    state_code: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    udyam_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    msme_category: Mapped[Optional[str]] = mapped_column(String, nullable=True)   # micro|small|medium|none|unknown
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_level: Mapped[str] = mapped_column(String, nullable=False, server_default="unverified")  # high|medium|low|unverified
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    checks: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    registry_source: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # live | sample | unavailable
    registry_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


class VendorCheck(Base, UUIDPrimaryKeyMixin):
    """Auditing and tracking record for GSTIN verification checks."""
    __tablename__ = "vendor_checks"
    __table_args__ = {"schema": "vendor_intelligence"}

    gstin: Mapped[str] = mapped_column(String, nullable=False)
    company_name: Mapped[str] = mapped_column(String, nullable=True)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=True)
    registration_date: Mapped[date] = mapped_column(Date, nullable=True)
    trust_score: Mapped[int] = mapped_column(Integer, nullable=True)
    fraud_flagged: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        default=False,
        nullable=True
    )
    raw_mock_response: Mapped[dict] = mapped_column(JSONB, nullable=True)
    
    checked_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.users.id", ondelete="SET NULL"),
        nullable=True
    )
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False
    )
