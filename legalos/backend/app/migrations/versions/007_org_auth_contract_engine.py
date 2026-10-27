"""organisations, auth, audit log, contract engine v2

Revision ID: 007_org_auth_contract_engine
Revises: 006_add_risk_analysis
Create Date: 2026-10-22 23:30:00.000000

- core.organizations / core.memberships / core.audit_events
- core.users: email, password_hash, is_active, last_login_at
- core.documents.organization_id
- contract_intelligence: contract v2 columns, segments, findings, chat_messages
Legacy v1 tables (clauses, negotiation_suggestions) are left untouched.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007_org_auth_contract_engine"
down_revision: Union[str, None] = "006_add_risk_analysis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())
NOW = sa.text("now()")
GEN = sa.text("gen_random_uuid()")


def upgrade() -> None:
    # ---- core.organizations
    op.create_table(
        "organizations",
        sa.Column("id", UUID, primary_key=True, server_default=GEN),
        sa.Column("legal_name", sa.String, nullable=False),
        sa.Column("trade_name", sa.String),
        sa.Column("entity_type", sa.String),
        sa.Column("gstin", sa.String(15), unique=True),
        sa.Column("pan", sa.String(10)),
        sa.Column("cin_or_llpin", sa.String),
        sa.Column("udyam_number", sa.String),
        sa.Column("msme_category", sa.String),
        sa.Column("industry", sa.String),
        sa.Column("state_code", sa.String(2)),
        sa.Column("state_name", sa.String),
        sa.Column("employee_band", sa.String),
        sa.Column("turnover_band", sa.String),
        sa.Column("gst_filing_frequency", sa.String),
        sa.Column("registrations", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("registry_profile", JSONB),
        sa.Column("onboarding_completed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        schema="core",
    )

    # ---- core.users additions
    op.add_column("users", sa.Column("email", sa.String), schema="core")
    op.add_column("users", sa.Column("password_hash", sa.String), schema="core")
    op.add_column("users", sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")), schema="core")
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True)), schema="core")
    op.create_unique_constraint("uq_users_email", "users", ["email"], schema="core")

    # ---- core.memberships
    op.create_table(
        "memberships",
        sa.Column("id", UUID, primary_key=True, server_default=GEN),
        sa.Column("user_id", UUID, sa.ForeignKey("core.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", UUID, sa.ForeignKey("core.organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String, nullable=False, server_default="owner"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.UniqueConstraint("user_id", "organization_id", name="uq_membership_user_org"),
        schema="core",
    )
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"], schema="core")
    op.create_index("ix_memberships_organization_id", "memberships", ["organization_id"], schema="core")

    # ---- core.audit_events
    op.create_table(
        "audit_events",
        sa.Column("id", UUID, primary_key=True, server_default=GEN),
        sa.Column("organization_id", UUID),
        sa.Column("user_id", UUID),
        sa.Column("action", sa.String, nullable=False),
        sa.Column("entity_type", sa.String),
        sa.Column("entity_id", sa.String),
        sa.Column("meta", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        schema="core",
    )
    op.create_index("ix_audit_org_created", "audit_events", ["organization_id", "created_at"], schema="core")

    # ---- core.documents.organization_id
    op.add_column(
        "documents",
        sa.Column("organization_id", UUID, sa.ForeignKey("core.organizations.id", ondelete="CASCADE")),
        schema="core",
    )
    op.create_index("ix_documents_organization_id", "documents", ["organization_id"], schema="core")

    # ---- contract_intelligence.contracts v2 columns
    cs = "contract_intelligence"
    op.add_column("contracts", sa.Column("organization_id", UUID, sa.ForeignKey("core.organizations.id", ondelete="CASCADE")), schema=cs)
    op.create_index("ix_contracts_organization_id", "contracts", ["organization_id"], schema=cs)
    for name, typ in [
        ("stage", sa.String), ("error_kind", sa.String), ("error_message", sa.String),
        ("contract_type", sa.String), ("client_party", sa.String), ("summary_points", JSONB),
        ("facts", JSONB), ("overall_score", sa.Integer), ("risk_level", sa.String),
        ("score_breakdown", JSONB), ("warnings", JSONB), ("page_count", sa.Integer),
        ("prompt_version", sa.String), ("rules_version", sa.String),
        ("analyzed_at", sa.DateTime(timezone=True)),
    ]:
        op.add_column("contracts", sa.Column(name, typ), schema=cs)
    op.add_column("contracts", sa.Column("ocr_used", sa.Boolean, nullable=False, server_default=sa.text("false")), schema=cs)

    # ---- segments
    op.create_table(
        "segments",
        sa.Column("id", UUID, primary_key=True, server_default=GEN),
        sa.Column("contract_id", UUID, sa.ForeignKey("contract_intelligence.contracts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seg_index", sa.Integer, nullable=False),
        sa.Column("seg_id", sa.String, nullable=False),
        sa.Column("number", sa.String),
        sa.Column("heading", sa.String, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("page_start", sa.Integer),
        sa.Column("page_end", sa.Integer),
        schema=cs,
    )
    op.create_index("ix_segments_contract", "segments", ["contract_id", "seg_index"], schema=cs)

    # ---- findings
    op.create_table(
        "findings",
        sa.Column("id", UUID, primary_key=True, server_default=GEN),
        sa.Column("contract_id", UUID, sa.ForeignKey("contract_intelligence.contracts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("source", sa.String, nullable=False),
        sa.Column("category", sa.String, nullable=False),
        sa.Column("severity", sa.String, nullable=False),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("why_it_matters", sa.Text, nullable=False),
        sa.Column("recommendation", sa.Text),
        sa.Column("suggested_wording", sa.Text),
        sa.Column("quote", sa.Text),
        sa.Column("segment_id", sa.String),
        sa.Column("page", sa.Integer),
        sa.Column("verified", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("counts_toward_score", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("rule_id", sa.String),
        sa.Column("legal_note", sa.Text),
        sa.Column("legal_ref", sa.String),
        sa.Column("condition_note", sa.Text),
        sa.Column("status", sa.String, nullable=False, server_default="open"),
        schema=cs,
    )
    op.create_index("ix_findings_contract", "findings", ["contract_id", "sort_order"], schema=cs)

    # ---- chat_messages
    op.create_table(
        "chat_messages",
        sa.Column("id", UUID, primary_key=True, server_default=GEN),
        sa.Column("contract_id", UUID, sa.ForeignKey("contract_intelligence.contracts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("citations", JSONB),
        sa.Column("found_in_contract", sa.Boolean),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        schema=cs,
    )
    op.create_index("ix_chat_messages_contract_id", "chat_messages", ["contract_id"], schema=cs)


def downgrade() -> None:
    cs = "contract_intelligence"
    op.drop_table("chat_messages", schema=cs)
    op.drop_table("findings", schema=cs)
    op.drop_table("segments", schema=cs)
    for col in [
        "ocr_used", "analyzed_at", "rules_version", "prompt_version", "page_count", "warnings",
        "score_breakdown", "risk_level", "overall_score", "facts", "summary_points", "client_party",
        "contract_type", "error_message", "error_kind", "stage", "organization_id",
    ]:
        op.drop_column("contracts", col, schema=cs)
    op.drop_column("documents", "organization_id", schema="core")
    op.drop_table("audit_events", schema="core")
    op.drop_table("memberships", schema="core")
    op.drop_constraint("uq_users_email", "users", schema="core", type_="unique")
    for col in ["last_login_at", "is_active", "password_hash", "email"]:
        op.drop_column("users", col, schema="core")
    op.drop_table("organizations", schema="core")
