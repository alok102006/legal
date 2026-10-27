import asyncio
import os

# --- Test environment: must be set BEFORE the app (and its settings/engine) is imported -----------
os.environ["ENV"] = "test"
os.environ["DEMO_MODE"] = "true"
os.environ["LLM_PROVIDER"] = "fake"
os.environ["DOCUMENTS_COLLECTION"] = "documents_v2_test"       # never touch the real vector collection
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://legalos:legalos_secure_password@db:5432/legalos_test"
)
_db_name = os.environ["DATABASE_URL"].rsplit("/", 1)[-1]
assert _db_name.endswith("_test"), f"Refusing to run tests against non-test database '{_db_name}'"

import pytest  # noqa: E402

from app.config import settings  # noqa: E402
from app.core.llm import limiter  # noqa: E402
from app.core.llm.providers import fake_provider  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_settings(tmp_path):
    """Several tests mutate global settings; restore them after every test."""
    saved = {
        k: getattr(settings, k)
        for k in (
            "llm_provider", "gemini_model", "gemini_fallback_models", "llm_max_retries",
            "llm_requests_per_minute", "llm_max_concurrency", "llm_cache_enabled", "llm_cache_dir",
        )
    }
    settings.llm_cache_dir = str(tmp_path / "llm_cache")
    settings.llm_requests_per_minute = 10_000
    limiter.reset_gate()
    yield
    for k, v in saved.items():
        setattr(settings, k, v)
    limiter.reset_gate()
    fake_provider.set_handler(None)


@pytest.fixture
def fake_llm():
    """Route all LLM calls to the fake provider. Usage: fake_llm(lambda call: '{"x": 1}')."""
    settings.llm_provider = "fake"

    def install(handler):
        fake_provider.set_handler(handler)
        return fake_provider.STATE

    return install


# --------------------------------------------------------------------------- database fixtures

_SCHEMAS = ["core", "contract_intelligence", "vendor_intelligence", "legal_notice_center",
            "compliance_center", "knowledge_hub"]


async def _prepare_database() -> None:
    import asyncpg
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    from app.shared.db import models  # noqa: F401  (registers every table)
    from app.shared.db.base import Base

    url = settings.database_url
    raw = url.replace("+asyncpg", "")
    base, name = raw.rsplit("/", 1)
    admin = await asyncpg.connect(base + "/postgres", timeout=5)
    try:
        if not await admin.fetchval("SELECT 1 FROM pg_database WHERE datname=$1", name):
            await admin.execute(f'CREATE DATABASE "{name}"')
    finally:
        await admin.close()

    engine = create_async_engine(url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        for s in _SCHEMAS:
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {s} CASCADE"))
            await conn.execute(text(f"CREATE SCHEMA {s}"))
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _models():
    """Load the embedding/reranker models once, outside any worker thread (lazy loads inside pools deadlock)."""
    from app.core.embeddings.embedder import warm_up
    warm_up()


@pytest.fixture(scope="session")
def _db_schema():
    try:
        asyncio.run(_prepare_database())
    except Exception as e:  # not running inside the compose network, or DB down
        pytest.skip(f"Test database unavailable: {e}")


@pytest.fixture
async def db_clean(_db_schema):
    """Empties every table, then re-seeds the demo organisation + personas."""
    from sqlalchemy import text

    from app.shared.auth import auth_service
    from app.shared.db.base import Base
    from app.shared.db.session import async_session_maker

    async with async_session_maker() as s:
        # a connection a previous test left idle-in-transaction would block TRUNCATE forever: fail loudly instead
        await s.execute(text("SET lock_timeout = '15s'"))
        names = ", ".join(f'"{t.schema}"."{t.name}"' for t in Base.metadata.sorted_tables)
        await s.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
        await auth_service.seed_demo_data(s)
    try:                       # fresh test vector collection (skipped when Qdrant is not reachable)
        from app.core.vectorstore.collections import init_collections
        from app.core.vectorstore.qdrant_client import get_qdrant_client
        client = get_qdrant_client()
        if client.collection_exists(settings.documents_collection):
            client.delete_collection(settings.documents_collection)
        init_collections()
    except Exception:
        pass
    yield


@pytest.fixture
async def api(db_clean, tmp_path, monkeypatch):
    """httpx client wired directly to the ASGI app (background tasks complete before the call returns)."""
    import httpx

    from app.main import app
    from app.shared.storage import file_storage

    monkeypatch.setattr(file_storage, "UPLOAD_DIR", str(tmp_path / "uploads"))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
