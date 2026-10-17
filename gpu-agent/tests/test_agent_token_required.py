import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import dependencies
from app.config import get_settings
from app.dependencies import MissingAgentTokenError, ensure_agent_token_configured
from app.main import app

AGENT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def fresh_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_PATH", str(tmp_path))
    app.dependency_overrides.clear()
    dependencies.settings.cache_clear()
    dependencies.workspace_service.cache_clear()
    yield
    app.dependency_overrides.clear()
    dependencies.settings.cache_clear()
    dependencies.workspace_service.cache_clear()


@pytest.mark.parametrize("token", [None, "", "   "])
def test_missing_token_is_rejected(token):
    with pytest.raises(MissingAgentTokenError):
        ensure_agent_token_configured(replace(get_settings(), agent_token=token))


def test_configured_token_is_accepted():
    ensure_agent_token_configured(replace(get_settings(), agent_token="secret"))


def test_app_startup_fails_without_token(fresh_settings, monkeypatch):
    monkeypatch.delenv("GPU_AGENT_TOKEN", raising=False)

    with pytest.raises(MissingAgentTokenError), TestClient(app):
        pass


def test_app_starts_with_token_and_requires_it(fresh_settings, monkeypatch):
    monkeypatch.setenv("GPU_AGENT_TOKEN", "secret")

    with TestClient(app) as client:
        assert client.get("/health").status_code == 401
        assert client.get("/health", headers={"Authorization": "Bearer secret"}).status_code == 200


def test_requests_fail_closed_if_served_without_startup_check(fresh_settings, monkeypatch):
    monkeypatch.delenv("GPU_AGENT_TOKEN", raising=False)
    client = TestClient(app)  # no context manager: lifespan does not run

    response = client.get("/health", headers={"Authorization": "Bearer anything"})

    assert response.status_code == 503


def test_uvicorn_process_exits_without_token(tmp_path):
    env = {key: value for key, value in os.environ.items() if key != "GPU_AGENT_TOKEN"}
    env["WORKSPACE_PATH"] = str(tmp_path)

    result = subprocess.run(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "0"],
        cwd=AGENT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode != 0
    assert "GPU_AGENT_TOKEN is not set" in result.stderr
