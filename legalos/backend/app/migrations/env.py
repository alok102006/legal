import asyncio
from logging.config import fileConfig
from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# Import settings and Base metadata
from app.config import settings
from app.shared.db.base import Base

# Import all models here so that Alembic's target_metadata can discover them
from app.shared.db.models import User, Document, Organization, Membership, AuditEvent
from app.workspaces.contract_intelligence.models import Contract, Clause, NegotiationSuggestion, Segment, Finding, ChatMessage
from app.workspaces.vendor_intelligence.models import VendorCheck, Vendor
from app.workspaces.legal_notice_center.models import Notice, DraftReply, NoticeCase, ReplyDraft
from app.workspaces.compliance_center.models import ComplianceTask, ComplianceDocumentAnalysis
from app.workspaces.knowledge_hub.models import RegisteredCompany, CompanyDocument, KnowledgeDocument, DocChunk, Conversation, ChatTurn

# Alembic config object
config = context.config

# Setup logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Database metadata containing all schemas
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = settings.database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True  # Ensure multi-schema support
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    # Idempotently build schemas and extension
    connection.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))
    connection.execute(text("CREATE SCHEMA IF NOT EXISTS core;"))
    connection.execute(text("CREATE SCHEMA IF NOT EXISTS contract_intelligence;"))
    connection.execute(text("CREATE SCHEMA IF NOT EXISTS vendor_intelligence;"))
    connection.execute(text("CREATE SCHEMA IF NOT EXISTS legal_notice_center;"))
    connection.execute(text("CREATE SCHEMA IF NOT EXISTS compliance_center;"))
    connection.execute(text("CREATE SCHEMA IF NOT EXISTS knowledge_hub;"))
    
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = settings.database_url

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
        await connection.commit()

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
