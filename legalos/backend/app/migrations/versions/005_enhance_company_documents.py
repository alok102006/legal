"""enhance_company_documents

Revision ID: 005_enhance_company_documents
Revises: 004_add_knowledge_hub
Create Date: 2026-08-07 12:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '005_enhance_company_documents'
down_revision: Union[str, None] = '004_add_knowledge_hub'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('company_documents', sa.Column('file_name', sa.String(), nullable=True), schema='knowledge_hub')
    op.add_column('company_documents', sa.Column('file_type', sa.String(), nullable=True), schema='knowledge_hub')
    op.add_column('company_documents', sa.Column('file_path', sa.String(), nullable=True), schema='knowledge_hub')
    op.add_column('company_documents', sa.Column('extracted_text', sa.String(), nullable=True), schema='knowledge_hub')


def downgrade() -> None:
    op.drop_column('company_documents', 'extracted_text', schema='knowledge_hub')
    op.drop_column('company_documents', 'file_path', schema='knowledge_hub')
    op.drop_column('company_documents', 'file_type', schema='knowledge_hub')
    op.drop_column('company_documents', 'file_name', schema='knowledge_hub')
