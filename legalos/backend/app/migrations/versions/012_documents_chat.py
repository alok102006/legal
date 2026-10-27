"""documents v3: structure-aware chunks (section, kind, simple tsvector), collections, conversations

Revision ID: 012_documents_chat
Revises: 011_documents_v2
Create Date: 2026-10-27 21:00:00.000000

Existing chunks are kept; the new computed columns are built from their text. Documents must be re-indexed
for the multilingual embedding model (the app re-indexes any document whose `embed_model` is not current).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "012_documents_chat"
down_revision: Union[str, None] = "011_documents_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = "knowledge_hub"
UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.add_column("chunks", sa.Column("section", sa.String), schema=S)
    op.add_column("chunks", sa.Column("kind", sa.String, nullable=False, server_default="text"), schema=S)
    op.drop_index("ix_chunks_tsv", table_name="chunks", schema=S)
    op.drop_column("chunks", "tsv", schema=S)
    op.add_column("chunks", sa.Column("tsv", postgresql.TSVECTOR, sa.Computed("to_tsvector('english', coalesce(section,'') || ' ' || text)", persisted=True)), schema=S)
    op.add_column("chunks", sa.Column("tsv_simple", postgresql.TSVECTOR, sa.Computed("to_tsvector('simple', coalesce(section,'') || ' ' || text)", persisted=True)), schema=S)
    op.create_index("ix_chunks_tsv", "chunks", ["tsv"], schema=S, postgresql_using="gin")
    op.create_index("ix_chunks_tsv_simple", "chunks", ["tsv_simple"], schema=S, postgresql_using="gin")

    op.add_column("docs", sa.Column("embed_model", sa.String), schema=S)
    op.add_column("docs", sa.Column("language", sa.String), schema=S)
    op.add_column("docs", sa.Column("suggested_questions", JSONB), schema=S)

    op.create_table(
        "conversations",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID, sa.ForeignKey("core.organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String, nullable=False, server_default="New chat"),
        sa.Column("collection", sa.String),
        sa.Column("created_by", UUID, sa.ForeignKey("core.users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=S,
    )
    op.create_index("ix_conversations_org_updated", "conversations", ["organization_id", "updated_at"], schema=S)
    op.create_table(
        "chat_turns",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("conversation_id", UUID, sa.ForeignKey("knowledge_hub.conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("citations", JSONB), sa.Column("sources", JSONB),
        sa.Column("found_in_documents", sa.Boolean), sa.Column("confidence", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=S,
    )
    op.create_index("ix_chat_turns_conversation_id", "chat_turns", ["conversation_id"], schema=S)


def downgrade() -> None:
    op.drop_table("chat_turns", schema=S)
    op.drop_table("conversations", schema=S)
    op.drop_column("docs", "suggested_questions", schema=S)
    op.drop_column("docs", "language", schema=S)
    op.drop_column("docs", "embed_model", schema=S)
    op.drop_index("ix_chunks_tsv_simple", table_name="chunks", schema=S)
    op.drop_column("chunks", "tsv_simple", schema=S)
    op.drop_index("ix_chunks_tsv", table_name="chunks", schema=S)
    op.drop_column("chunks", "tsv", schema=S)
    op.add_column("chunks", sa.Column("tsv", postgresql.TSVECTOR, sa.Computed("to_tsvector('english', text)", persisted=True)), schema=S)
    op.create_index("ix_chunks_tsv", "chunks", ["tsv"], schema=S, postgresql_using="gin")
    op.drop_column("chunks", "kind", schema=S)
    op.drop_column("chunks", "section", schema=S)
