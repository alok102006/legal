"""add_knowledge_hub

Revision ID: 004_add_knowledge_hub
Revises: e722b756ed97
Create Date: 2026-08-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '004_add_knowledge_hub'
down_revision: Union[str, None] = 'e722b756ed97'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create schema knowledge_hub if not exists
    op.execute("CREATE SCHEMA IF NOT EXISTS knowledge_hub")

    # 2. Create registered_companies table
    op.create_table(
        'registered_companies',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('gstin', sa.String(length=15), nullable=False),
        sa.Column('legal_name', sa.String(), nullable=False),
        sa.Column('trade_name', sa.String(), nullable=True),
        sa.Column('entity_type', sa.String(), nullable=True),
        sa.Column('registration_date', sa.String(), nullable=True),
        sa.Column('taxpayer_type', sa.String(), nullable=True),
        sa.Column('status', sa.String(), server_default='Active', nullable=False),
        sa.Column('state_jurisdiction', sa.String(), nullable=True),
        sa.Column('center_jurisdiction', sa.String(), nullable=True),
        sa.Column('principal_address', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('nature_of_business', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('raw_profile_response', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('registered_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['registered_by'], ['core.users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('gstin'),
        schema='knowledge_hub'
    )
    op.create_index(op.f('ix_knowledge_hub_registered_companies_gstin'), 'registered_companies', ['gstin'], unique=True, schema='knowledge_hub')

    # 3. Create company_documents table
    op.create_table(
        'company_documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('document_category', sa.String(), server_default='Policy', nullable=False),
        sa.Column('summary', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['knowledge_hub.registered_companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['core.documents.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        schema='knowledge_hub'
    )


def downgrade() -> None:
    op.drop_table('company_documents', schema='knowledge_hub')
    op.drop_index(op.f('ix_knowledge_hub_registered_companies_gstin'), table_name='registered_companies', schema='knowledge_hub')
    op.drop_table('registered_companies', schema='knowledge_hub')
