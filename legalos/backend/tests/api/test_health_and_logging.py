import json
import logging

import httpx
import pytest

from app.shared import jobs
from app.shared.logging_config import JsonFormatter, request_id_var


@pytest.fixture
async def bare_client():
    """The app without a database fixture: /health/llm needs none."""
    from app.main import app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def test_every_response_has_a_request_id_and_a_good_incoming_one_is_kept(bare_client):
    r = await bare_client.get("/health/llm")
    assert r.status_code == 200 and len(r.headers["x-request-id"]) >= 8
    mine = await bare_client.get("/health/llm", headers={"X-Request-ID": "support-ticket-4711"})
    assert mine.headers["x-request-id"] == "support-ticket-4711"
    evil = await bare_client.get("/health/llm", headers={"X-Request-ID": "bad id\twith spaces & <tags>"})
    assert evil.headers["x-request-id"] != "bad id\twith spaces & <tags>" and " " not in evil.headers["x-request-id"]


async def test_log_lines_of_a_request_carry_its_id(bare_client, caplog):
    with caplog.at_level(logging.INFO, logger="legalos.access"):
        r = await bare_client.get("/health/llm", headers={"X-Request-ID": "trace-abc-123"})
    access = [rec for rec in caplog.records if rec.name == "legalos.access"]
    assert access and access[-1].request_id == "trace-abc-123" and "/health/llm -> 200" in access[-1].getMessage()
    assert r.headers["x-request-id"] == "trace-abc-123"
    assert request_id_var.get() == "-"                                 # the id does not leak out of the request


async def test_health_llm_reports_cache_queue_and_provider(bare_client):
    body = (await bare_client.get("/health/llm")).json()
    assert body["provider"] == "fake" and body["ok"] is True
    assert {"entries", "size_mb", "max_mb", "hit_rate", "evictions"} <= set(body["cache"])
    assert {"waiting", "in_flight", "keys"} <= set(body["queue"])


async def test_health_reports_latency_queue_depth_and_cache_stats(api):
    body = (await api.get("/health")).json()
    checks = body["checks"]
    assert checks["database"]["ok"] and checks["database"]["latency_ms"] >= 0
    assert "latency_ms" in checks["vector_store"]
    assert {"queued", "running", "depth", "workers"} <= set(checks["queue"]["jobs"])
    assert "waiting" in checks["queue"]["llm"]
    assert "entries" in checks["cache"]["llm"] and "hits" in checks["cache"]["registry"]
    assert "cache" not in checks["llm"] and "queue" not in checks["llm"]    # moved to their own entries


async def test_health_queue_depth_counts_jobs(api):
    import asyncio
    release = asyncio.Event()

    async def slow(job):
        await release.wait()

    started = [jobs.submit(slow, name=f"t{i}") for i in range(4)]
    await asyncio.sleep(0.05)
    q = (await api.get("/health")).json()["checks"]["queue"]["jobs"]
    assert q["running"] == 2 and q["queued"] == 2 and q["depth"] >= 2
    release.set()
    for j in started:
        await j.wait(timeout=2)
    await jobs.shutdown()


def test_json_log_format_is_one_parseable_object_per_line():
    record = logging.LogRecord("legalos.x", logging.WARNING, __file__, 1, "something %s", ("odd",), None)
    record.request_id = "rid-1"
    row = json.loads(JsonFormatter().format(record))
    assert row["message"] == "something odd" and row["request_id"] == "rid-1" and row["level"] == "WARNING"
