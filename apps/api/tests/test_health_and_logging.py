import json
import logging
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.logging import JobIdFilter, JobIdMiddleware, JsonFormatter, bind_job_id
from app.main import app


def test_root_health_needs_no_auth():
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def _render(message: str, **extra) -> dict:
    record = logging.LogRecord("test", logging.INFO, __file__, 1, message, None, None)
    for key, value in extra.items():
        setattr(record, key, value)
    JobIdFilter().filter(record)
    return json.loads(JsonFormatter().format(record))


def test_every_line_has_a_job_id_field_even_outside_a_job():
    line = _render("startup")

    assert line["message"] == "startup"
    assert line["level"] == "INFO"
    assert "timestamp" in line
    assert line["job_id"] is None


def test_bound_job_id_is_added_to_lines():
    job_id = uuid4()

    with bind_job_id(job_id):
        line = _render("polling agent")

    assert line["job_id"] == str(job_id)
    assert _render("after")["job_id"] is None


def test_explicit_job_id_wins_over_bound_one():
    with bind_job_id("bound"):
        line = _render("transition", job_id="explicit")

    assert line["job_id"] == "explicit"


def test_middleware_binds_job_id_from_job_urls():
    import asyncio

    from app.core.logging import job_id_var

    seen = []

    async def inner(scope, receive, send):
        seen.append(job_id_var.get())

    middleware = JobIdMiddleware(inner)
    job_id = str(uuid4())
    for path in (f"/api/v1/training/jobs/{job_id}", f"/api/v1/training/jobs/{job_id}/events", "/api/v1/gpu"):
        asyncio.run(middleware({"type": "http", "path": path}, None, None))

    assert seen == [job_id, job_id, None]
