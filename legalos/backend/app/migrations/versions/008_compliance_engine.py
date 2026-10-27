"""compliance engine v2 (organisation-scoped, rules-generated tasks)

Revision ID: 008_compliance_engine
Revises: 007_org_auth_contract_engine
Create Date: 2026-10-23 01:10:00.000000

Adds rule/period identity and organisation scoping to compliance_tasks. Rows created by the old
generator are NOT deleted: they keep organization_id = NULL and are simply invisible to the
organisation-scoped API.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008_compliance_engine"
down_revision: Union[str, None] = "007_org_auth_contract_engine"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = "compliance_center"


def upgrade() -> None:
    op.add_column("compliance_tasks", sa.Column(
        "organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.organizations.id", ondelete="CASCADE")), schema=S)
    for name in ("rule_id", "period_key", "period_label", "form_name", "authority", "rules_version"):
        op.add_column("compliance_tasks", sa.Column(name, sa.String), schema=S)
    for name in ("source_ref", "confirm_note", "completion_note"):
        op.add_column("compliance_tasks", sa.Column(name, sa.Text), schema=S)
    op.add_column("compliance_tasks", sa.Column("needs_confirmation", sa.Boolean, nullable=False, server_default=sa.text("false")), schema=S)
    op.add_column("compliance_tasks", sa.Column("is_custom", sa.Boolean, nullable=False, server_default=sa.text("false")), schema=S)
    op.add_column("compliance_tasks", sa.Column("completed_at", sa.DateTime(timezone=True)), schema=S)

    op.create_index(
        "uq_compliance_task_rule_period", "compliance_tasks", ["organization_id", "rule_id", "period_key"],
        unique=True, schema=S, postgresql_where=sa.text("rule_id IS NOT NULL"))
    op.create_index("ix_compliance_tasks_org_due", "compliance_tasks", ["organization_id", "due_date"], schema=S)


def downgrade() -> None:
    op.drop_index("ix_compliance_tasks_org_due", table_name="compliance_tasks", schema=S)
    op.drop_index("uq_compliance_task_rule_period", table_name="compliance_tasks", schema=S)
    for name in ("completed_at", "is_custom", "needs_confirmation", "completion_note", "confirm_note", "source_ref",
                 "rules_version", "authority", "form_name", "period_label", "period_key", "rule_id", "organization_id"):
        op.drop_column("compliance_tasks", name, schema=S)
