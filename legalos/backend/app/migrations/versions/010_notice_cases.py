"""notice cases v2: organisation-scoped notices with extraction, deadline and reply drafts

Revision ID: 010_notice_cases
Revises: 009_vendors_v2
Create Date: 2026-10-27 13:00:00.000000

The legacy `notices` / `draft_replies` tables are kept untouched.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "010_notice_cases"
down_revision: Union[str, None] = "009_vendors_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = "legal_notice_center"
UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "cases",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID, sa.ForeignKey("core.organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", UUID, sa.ForeignKey("core.documents.id", ondelete="SET NULL")),
        sa.Column("title", sa.String), sa.Column("raw_text", sa.Text), sa.Column("source_name", sa.String),
        sa.Column("status", sa.String, nullable=False, server_default="processing"),
        sa.Column("stage", sa.String), sa.Column("error_kind", sa.String), sa.Column("error_message", sa.String),
        sa.Column("notice_type", sa.String), sa.Column("urgency", sa.String), sa.Column("issuer_name", sa.String),
        sa.Column("reference_number", sa.String), sa.Column("notice_date", sa.Date), sa.Column("received_date", sa.Date),
        sa.Column("amount_claimed", sa.Numeric(16, 2)), sa.Column("response_days", sa.Integer),
        sa.Column("response_deadline", sa.Date), sa.Column("deadline_source", sa.String), sa.Column("deadline_note", sa.Text),
        sa.Column("deadline_quote", sa.Text), sa.Column("deadline_verified", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("summary_points", JSONB), sa.Column("demands", JSONB), sa.Column("statutes", JSONB),
        sa.Column("consequences", sa.Text), sa.Column("legal_note", sa.Text), sa.Column("legal_ref", sa.String),
        sa.Column("facts", JSONB), sa.Column("review_status", sa.String, nullable=False, server_default="draft"),
        sa.Column("compliance_task_id", UUID), sa.Column("ocr_used", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("prompt_version", sa.String),
        sa.Column("created_by", UUID, sa.ForeignKey("core.users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("analyzed_at", sa.DateTime(timezone=True)),
        schema=S,
    )
    op.create_index("ix_cases_org_created", "cases", ["organization_id", "created_at"], schema=S)

    op.create_table(
        "reply_drafts",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("case_id", UUID, sa.ForeignKey("legal_notice_center.cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("reply_text", sa.Text, nullable=False),
        sa.Column("placeholders", JSONB), sa.Column("points_to_confirm", JSONB), sa.Column("documents_to_gather", JSONB),
        sa.Column("author", sa.String, nullable=False, server_default="ai"),
        sa.Column("instructions", sa.String),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=S,
    )
    op.create_index("ix_reply_drafts_case_id", "reply_drafts", ["case_id"], schema=S)


def downgrade() -> None:
    op.drop_table("reply_drafts", schema=S)
    op.drop_table("cases", schema=S)
