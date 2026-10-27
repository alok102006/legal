"""documents v2: organisation-scoped vault with page-aware chunks and full-text search

Revision ID: 011_documents_v2
Revises: 010_notice_cases
Create Date: 2026-10-27 16:00:00.000000

Legacy `registered_companies` / `company_documents` are kept untouched.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "011_documents_v2"
down_revision: Union[str, None] = "010_notice_cases"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = "knowledge_hub"
UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "docs",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID, sa.ForeignKey("core.organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", UUID, sa.ForeignKey("core.documents.id", ondelete="SET NULL")),
        sa.Column("title", sa.String, nullable=False), sa.Column("filename", sa.String), sa.Column("category", sa.String),
        sa.Column("file_type", sa.String), sa.Column("page_count", sa.Integer),
        sa.Column("chunk_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String, nullable=False, server_default="processing"),
        sa.Column("stage", sa.String), sa.Column("error_kind", sa.String), sa.Column("error_message", sa.String),
        sa.Column("review_state", sa.String, nullable=False, server_default="pending"), sa.Column("review_error", sa.String),
        sa.Column("doc_type", sa.String), sa.Column("summary_points", JSONB), sa.Column("key_facts", JSONB),
        sa.Column("concerns", JSONB), sa.Column("missing_items", JSONB),
        sa.Column("expiry_date", sa.Date), sa.Column("expiry_label", sa.String), sa.Column("expiry_task_id", UUID),
        sa.Column("ocr_used", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("prompt_version", sa.String),
        sa.Column("created_by", UUID, sa.ForeignKey("core.users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=S,
    )
    op.create_index("ix_docs_org_created", "docs", ["organization_id", "created_at"], schema=S)

    op.create_table(
        "chunks",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("doc_id", UUID, sa.ForeignKey("knowledge_hub.docs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("page", sa.Integer),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("tsv", postgresql.TSVECTOR, sa.Computed("to_tsvector('english', text)", persisted=True)),
        schema=S,
    )
    op.create_index("ix_chunks_tsv", "chunks", ["tsv"], schema=S, postgresql_using="gin")
    op.create_index("ix_chunks_org_doc", "chunks", ["organization_id", "doc_id"], schema=S)


def downgrade() -> None:
    op.drop_table("chunks", schema=S)
    op.drop_table("docs", schema=S)
