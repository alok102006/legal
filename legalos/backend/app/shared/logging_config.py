"""Structured logging with a request id on every line.

- Every HTTP request gets an id: the caller's `X-Request-ID` header when it is a sane value, else a fresh one. The id
  is put in a context variable, so every log line written while serving that request carries it (also lines written
  in worker threads started with `asyncio.to_thread`, and in background tasks of the request), and it is returned in
  the `X-Request-ID` response header, so a support question "request 3f9c..." finds all the lines.
- LOG_FORMAT=json prints one JSON object per line (for log shippers); the default is readable text.
- One access line per request (method, path, status, milliseconds); /health is skipped to keep the log quiet.
"""
import json
import logging
import re
import time
import uuid
from contextvars import ContextVar

from app.config import settings

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_SAFE_ID = re.compile(r"^[A-Za-z0-9._\-]{6,64}$")
TEXT_FORMAT = "%(asctime)s %(levelname)s [%(name)s] [%(request_id)s] %(message)s"
access_logger = logging.getLogger("legalos.access")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        row = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"), "level": record.levelname, "logger": record.name,
            "request_id": getattr(record, "request_id", "-"), "message": record.getMessage(),
        }
        if record.exc_info:
            row["exception"] = self.formatException(record.exc_info)
        return json.dumps(row, ensure_ascii=False)


def configure_logging() -> None:
    """Idempotent. Adds `request_id` to every log record and sets the root format."""
    previous = logging.getLogRecordFactory()
    if not getattr(previous, "_legalos", False):
        def factory(*args, **kwargs):
            record = previous(*args, **kwargs)
            record.request_id = request_id_var.get()
            return record

        factory._legalos = True  # type: ignore[attr-defined]
        logging.setLogRecordFactory(factory)

    root = logging.getLogger()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter() if settings.log_format.lower() == "json" else logging.Formatter(TEXT_FORMAT))
        root.addHandler(handler)
    root.setLevel(level)


class RequestIdMiddleware:
    """Pure ASGI middleware (no BaseHTTPMiddleware, so streaming and background tasks are untouched)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope.get("headers") or []).get(b"x-request-id", b"").decode("latin-1")
        rid = incoming if _SAFE_ID.match(incoming) else uuid.uuid4().hex[:12]
        token = request_id_var.set(rid)
        started = time.perf_counter()
        status = 500

        async def send_with_id(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message["headers"] = [*message.get("headers", []), (b"x-request-id", rid.encode("ascii"))]
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            path = scope.get("path", "")
            if path != "/health":
                access_logger.info("%s %s -> %s in %.0f ms", scope.get("method", ""), path, status,
                                   (time.perf_counter() - started) * 1000)
            request_id_var.reset(token)
