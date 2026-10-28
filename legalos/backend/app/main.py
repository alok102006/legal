import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.shared.logging_config import RequestIdMiddleware, configure_logging  # noqa: E402

configure_logging()

from app.config import settings  # noqa: E402
from app.core.embeddings.embedder import warm_up  # noqa: E402
from app.core.llm import llm_client  # noqa: E402
from app.core.llm.errors import LLMAuthError, LLMError  # noqa: E402
from app.core.llm.providers import gemini_provider  # noqa: E402
from app.core.vectorstore.collections import init_collections  # noqa: E402
from app.shared import jobs  # noqa: E402
from app.shared.auth import auth_service  # noqa: E402
from app.shared.auth.router import router as auth_router  # noqa: E402
from app.shared.db.session import async_session_maker, engine  # noqa: E402
from app.shared.exceptions import LegalOSException  # noqa: E402
from app.shared.org.router import router as org_router  # noqa: E402
from app.workspaces.compliance_center.router import router as compliance_router  # noqa: E402
from app.workspaces.contract_intelligence import service as contract_service  # noqa: E402
from app.workspaces.contract_intelligence.router import router as contract_router  # noqa: E402
from app.workspaces.knowledge_hub.router import router as knowledge_router  # noqa: E402
from app.workspaces.legal_notice_center.router import router as notice_router  # noqa: E402
from app.workspaces.vendor_intelligence import registry_cache  # noqa: E402
from app.workspaces.vendor_intelligence.router import router as vendor_router  # noqa: E402

logger = logging.getLogger("legalos.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: warm the embedder + Qdrant, seed demo data, recover interrupted jobs."""
    logger.info("Starting up...")

    try:
        await asyncio.to_thread(warm_up)
    except Exception as e:
        logger.error("Could not warm up the embedder: %s", e)
        if settings.env == "prod":
            raise

    try:
        await asyncio.to_thread(init_collections)
    except Exception as e:
        logger.error("Could not initialise Qdrant collections: %s", e)
        if settings.env == "prod":
            raise

    try:
        if settings.demo_mode:
            async with async_session_maker() as session:
                await auth_service.seed_demo_data(session)
        interrupted = await contract_service.mark_interrupted_jobs()
        if interrupted:
            logger.warning("Marked %d interrupted contract analyses as failed (retry available)", interrupted)
        from app.workspaces.legal_notice_center import service as notice_service
        from app.workspaces.knowledge_hub import service as doc_service
        recovered_docs = await doc_service.recover_at_startup()
        if recovered_docs:
            logger.info("Resuming %d document jobs (interrupted, unreviewed or indexed with an old model)", recovered_docs)
        interrupted_notices = await notice_service.mark_interrupted()
        if interrupted_notices:
            logger.warning("Marked %d interrupted notice analyses as failed (retry available)", interrupted_notices)
        legacy = await contract_service.flag_legacy_contracts()
        if legacy:
            logger.info("Flagged %d v1 contracts for re-analysis", legacy)
    except Exception as e:
        logger.error("Startup data tasks failed: %s", e)

    jobs.start()
    health = llm_client.llm_health(force=True)
    if not health.get("ok"):
        logger.error("LLM is NOT usable: %s - %s", health.get("kind"), health.get("message"))
    elif settings.llm_provider.lower().strip() == "gemini":
        # A typo in GEMINI_MODEL or a retired model otherwise only shows up as failed analyses. Free: no generation quota.
        await asyncio.to_thread(gemini_provider.check_models)
    logger.info("Startup finished.")
    yield
    logger.info("Shutting down...")
    await jobs.shutdown()


app = FastAPI(
    title="LegalOS API",
    description="Legal operations and compliance platform for Indian SMEs.",
    version="2.0.0",
    lifespan=lifespan,
)

allowed_origins = [o.strip() for o in settings.frontend_url.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(RequestIdMiddleware)          # added last = outermost: also covers CORS pre-flights and errors


@app.exception_handler(LegalOSException)
async def legalos_exception_handler(request: Request, exc: LegalOSException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "timestamp": time.time(), "path": request.url.path},
    )


@app.exception_handler(LLMError)
async def llm_exception_handler(request: Request, exc: LLMError):
    """AI-service problems are reported honestly (503), never disguised as a normal result."""
    return JSONResponse(
        status_code=503,
        content={
            "detail": exc.user_message,
            "kind": "auth" if isinstance(exc, LLMAuthError) else type(exc).__name__,
            "retryable": exc.retryable,
            "path": request.url.path,
        },
    )


async def _timed(fn) -> dict:
    """Runs a dependency check and reports ok / latency_ms (or the error)."""
    started = time.perf_counter()
    try:
        await fn()
        return {"ok": True, "latency_ms": round((time.perf_counter() - started) * 1000, 1)}
    except Exception as e:
        return {"ok": False, "latency_ms": round((time.perf_counter() - started) * 1000, 1), "message": str(e)[:120]}


@app.get("/health")
async def health_check():
    """Real dependency status (the UI shows this; nothing here is hard-coded)."""
    checks: dict = {}

    async def ping_db():
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def ping_qdrant():
        from app.core.vectorstore.qdrant_client import get_qdrant_client
        await asyncio.to_thread(lambda: get_qdrant_client().get_collections())

    checks["database"] = await _timed(ping_db)
    checks["vector_store"] = await _timed(ping_qdrant)

    llm = await asyncio.to_thread(llm_client.llm_health)
    llm_cache_stats, llm_queue = llm.pop("cache", None), llm.pop("queue", None)
    checks["llm"] = llm
    checks["queue"] = {"jobs": jobs.stats(), "llm": llm_queue}
    checks["cache"] = {"llm": llm_cache_stats, "registry": dict(registry_cache.COUNTERS)}
    checks["registry"] = {"mode": settings.sandbox_co_mode, "live": settings.sandbox_co_mode == "live"}

    critical_ok = checks["database"]["ok"]
    all_ok = critical_ok and checks["vector_store"]["ok"] and checks["llm"].get("ok", False)
    return {
        "status": "healthy" if all_ok else ("degraded" if critical_ok else "unhealthy"),
        "timestamp": time.time(),
        "demo_mode": settings.demo_mode,
        "checks": checks,
    }


@app.get("/health/llm")
async def llm_status(refresh: bool = False):
    """The AI provider in detail: key/model validity, daily-quota memory, usage, response cache, per-key queue depth,
    and the startup check of GEMINI_MODEL against the models the key can use."""
    return await asyncio.to_thread(llm_client.llm_health, refresh)


# Platform routers
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(org_router, prefix="/api/v1/org", tags=["Organisation"])
from app.shared.samples.router import router as samples_router  # noqa: E402
app.include_router(samples_router, prefix="/api/v1/samples", tags=["Samples"])

# Workspace routers
app.include_router(contract_router, prefix="/api/v1/contracts", tags=["Contract Intelligence"])
app.include_router(vendor_router, prefix="/api/v1/vendors", tags=["Vendor Intelligence"])
app.include_router(notice_router, prefix="/api/v1/notices", tags=["Legal Notice Center"])
app.include_router(compliance_router, prefix="/api/v1/compliance", tags=["Compliance Center"])
app.include_router(knowledge_router, prefix="/api/v1/knowledge", tags=["Knowledge Hub"])
