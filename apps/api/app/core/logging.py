import json
import logging
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime

from starlette.types import ASGIApp, Receive, Scope, Send

# The training job a log line belongs to. Every line carries the field; it is null
# for lines emitted outside a job (startup, auth, dataset browsing, ...).
job_id_var: ContextVar[str | None] = ContextVar("job_id", default=None)

_JOB_PATH = re.compile(r"/training/jobs/([0-9a-fA-F-]{36})(?:/|$)")


class JobIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, "job_id", None) is None:
            record.job_id = job_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "job_id": getattr(record, "job_id", None),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str | int = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(JobIdFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # Route uvicorn's own loggers through the JSON handler instead of its plain-text ones.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True


@contextmanager
def bind_job_id(job_id: object) -> Iterator[None]:
    token = job_id_var.set(str(job_id))
    try:
        yield
    finally:
        job_id_var.reset(token)


class JobIdMiddleware:
    """Binds the job ID from /training/jobs/{job_id}/... URLs for the whole request."""

    def __init__(self, app: ASGIApp):
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        match = _JOB_PATH.search(scope.get("path", "")) if scope["type"] == "http" else None
        if match is None:
            await self._app(scope, receive, send)
            return
        with bind_job_id(match.group(1)):
            await self._app(scope, receive, send)
