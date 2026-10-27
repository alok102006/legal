"""vendors v2: organisation-scoped vendor records with deterministic assessments

Revision ID: 009_vendors_v2
Revises: 008_compliance_engine
Create Date: 2026-10-27 11:00:00.000000

The old `vendor_checks` audit table is kept untouched.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009_vendors_v2"
down_revision: Union[str, None] = "008_compliance_engine"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = "vendor_intelligence"


def upgrade() -> None:
    op.create_table(
        "vendors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("gstin", sa.String(15)),
        sa.Column("pan", sa.String(10)),
        sa.Column("state_code", sa.String(2)),
        sa.Column("udyam_number", sa.String),
        sa.Column("msme_category", sa.String),
        sa.Column("notes", sa.Text),
        sa.Column("risk_level", sa.String, nullable=False, server_default="unverified"),
        sa.Column("summary", sa.Text),
        sa.Column("checks", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("registry_source", sa.String),
        sa.Column("registry_data", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=S,
    )
    op.create_index("ix_vendors_organization_id", "vendors", ["organization_id"], schema=S)
    op.create_index("uq_vendor_org_gstin", "vendors", ["organization_id", "gstin"], unique=True, schema=S,
                    postgresql_where=sa.text("gstin IS NOT NULL"))


def downgrade() -> None:
    op.drop_table("vendors", schema=S)
