"""add_risk_analysis_to_company_documents

Revision ID: 006_add_risk_analysis
Revises: 005_enhance_company_documents
Create Date: 2026-09-21 11:35:00.000000

Adds JSONB risk_analysis column to knowledge_hub.company_documents to store
the output of the AI Document Risk Radar analysis engine.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '006_add_risk_analysis'
down_revision: Union[str, None] = '005_enhance_company_documents'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'company_documents',
        sa.Column('risk_analysis', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema='knowledge_hub'
    )


def downgrade() -> None:
    op.drop_column('company_documents', 'risk_analysis', schema='knowledge_hub')
