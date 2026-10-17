from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_authentication_service, get_training_service
from app.core.config import get_settings
from app.core.security import create_access_token
from app.domain.training import TrainingConfig, TrainingJob, TrainingJobEvent, TrainingJobStatus
from app.domain.users import User, UserRole
from app.main import app
from app.services.model_registry import ModelRegistry
from app.services.template_loader import TemplateLoader
from app.services.training_service import TrainingService
from app.services.training_state_machine import TrainingStateMachine


class InMemoryJobRepository:
    def __init__(self):
        self.jobs: dict = {}
        self.events: list[TrainingJobEvent] = []

    def seed(self, user_id, status=TrainingJobStatus.CREATED) -> TrainingJob:
        now = datetime.now(UTC)
        config = TrainingConfig(
            model_key="qwen2.5-1.5b",
            dataset_id="builtin/edi-demo",
            normalized_dataset_path="datasets/demo.jsonl",
        )
        job = TrainingJob(
            id=uuid4(),
            user_id=user_id,
            status=status,
            model_key=config.model_key,
            model_id="unsloth/Qwen2.5-1.5B-Instruct",
            template_name="qwen",
            training_config=config,
            dataset_id=config.dataset_id,
            normalized_dataset_path=config.normalized_dataset_path,
            created_at=now,
            updated_at=now,
        )
        self.jobs[job.id] = job
        return job

    async def get_job(self, job_id):
        return self.jobs.get(job_id)

    async def list_jobs(self, user_id):
        return [job for job in self.jobs.values() if job.user_id == user_id]

    async def update_job(self, job_id, **kwargs):
        payload = self.jobs[job_id].model_dump()
        payload.update({key: value for key, value in kwargs.items() if value is not None})
        self.jobs[job_id] = TrainingJob(**payload)
        return self.jobs[job_id]

    async def add_event(self, training_job_id, user_id, from_status, to_status, message, metadata=None):
        event = TrainingJobEvent(
            id=uuid4(),
            training_job_id=training_job_id,
            user_id=user_id,
            from_status=from_status,
            to_status=to_status,
            message=message,
            metadata=metadata or {},
            created_at=datetime.now(UTC),
        )
        self.events.append(event)
        return event

    async def list_events(self, job_id):
        return [event for event in self.events if event.training_job_id == job_id]

    async def list_metrics(self, job_id):
        return []

    async def latest_checkpoint(self, job_id):
        return None

    async def list_artifacts(self, job_id):
        return []

    async def get_artifact(self, artifact_id):
        return None


class FakeAuthService:
    def __init__(self, users: list[User]):
        self._users = {user.id: user for user in users}

    async def get_user_by_id(self, user_id):
        return self._users.get(user_id)


def _user(active: bool = True) -> User:
    return User(
        id=uuid4(),
        email=f"user-{uuid4().hex[:8]}@example.com",
        hashed_password="hash",
        role=UserRole.USER,
        is_active=active,
    )


@pytest.fixture
def world():
    owner, intruder, inactive = _user(), _user(), _user(active=False)
    repository = InMemoryJobRepository()
    owner_job = repository.seed(owner.id)
    intruder_job = repository.seed(intruder.id)
    service = TrainingService(
        repository=repository,
        model_registry=ModelRegistry(),
        template_loader=TemplateLoader(),
        state_machine=TrainingStateMachine(),
    )
    # Real get_current_user and JWT decoding; only the user lookup and job storage are faked.
    app.dependency_overrides.clear()
    app.dependency_overrides[get_authentication_service] = lambda: FakeAuthService([owner, intruder, inactive])
    app.dependency_overrides[get_training_service] = lambda: service
    yield {
        "client": TestClient(app),
        "repository": repository,
        "owner": owner,
        "intruder": intruder,
        "inactive": inactive,
        "owner_job": owner_job,
        "intruder_job": intruder_job,
    }
    app.dependency_overrides.clear()


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _job_routes(job_id):
    artifact_id = uuid4()
    return [
        ("GET", f"/api/v1/training/jobs/{job_id}", None),
        ("POST", f"/api/v1/training/jobs/{job_id}/queue", None),
        ("POST", f"/api/v1/training/jobs/{job_id}/cancel", None),
        ("POST", f"/api/v1/training/jobs/{job_id}/resume", {"resume_from_checkpoint": "checkpoints/c-1"}),
        ("GET", f"/api/v1/training/jobs/{job_id}/events", None),
        ("GET", f"/api/v1/training/jobs/{job_id}/metrics", None),
        ("GET", f"/api/v1/training/jobs/{job_id}/checkpoints/latest", None),
        ("GET", f"/api/v1/training/jobs/{job_id}/artifacts", None),
        ("GET", f"/api/v1/training/jobs/{job_id}/artifacts/{artifact_id}", None),
    ]


def _call(client, method, url, body, headers=None):
    return client.request(method, url, json=body, headers=headers or {})


def _bad_tokens(world) -> dict[str, dict]:
    settings = get_settings()
    owner_id = world["owner"].id
    return {
        "missing": {},
        "not_bearer": {"Authorization": f"Basic {create_access_token(owner_id)}"},
        "garbage": _bearer("not-a-jwt"),
        "wrong_signature": _bearer(
            jwt.encode(
                {"sub": str(owner_id), "exp": datetime.now(UTC) + timedelta(minutes=5)},
                "a-different-secret-that-is-at-least-32-bytes-long",
                algorithm=settings.jwt_algorithm,
            )
        ),
        "expired": _bearer(create_access_token(owner_id, expires_delta=timedelta(seconds=-1))),
        "unknown_user": _bearer(create_access_token(uuid4())),
        "inactive_user": _bearer(create_access_token(world["inactive"].id)),
    }


@pytest.mark.parametrize(
    "case",
    ["missing", "not_bearer", "garbage", "wrong_signature", "expired", "unknown_user", "inactive_user"],
)
def test_job_routes_reject_requests_without_a_valid_token(world, case):
    headers = _bad_tokens(world)[case]
    client = world["client"]
    routes = [
        ("GET", "/api/v1/training/jobs", None),
        ("POST", "/api/v1/training/jobs", {"config": {}}),
        *_job_routes(world["owner_job"].id),
    ]

    for method, url, body in routes:
        response = _call(client, method, url, body, headers)
        assert response.status_code == 401, (case, method, url, response.status_code)

    assert world["repository"].jobs[world["owner_job"].id].status == TrainingJobStatus.CREATED


def test_owner_can_read_and_change_own_job(world):
    client = world["client"]
    headers = _bearer(create_access_token(world["owner"].id))
    job_id = world["owner_job"].id

    read = client.get(f"/api/v1/training/jobs/{job_id}", headers=headers)
    queued = client.post(f"/api/v1/training/jobs/{job_id}/queue", headers=headers)
    events = client.get(f"/api/v1/training/jobs/{job_id}/events", headers=headers)

    assert read.status_code == 200
    assert read.json()["job"]["id"] == str(job_id)
    assert queued.status_code == 200
    assert queued.json()["job"]["status"] == "queued"
    assert [event["to_status"] for event in events.json()["events"]] == ["queued"]


def test_job_list_only_returns_callers_jobs(world):
    headers = _bearer(create_access_token(world["owner"].id))

    response = world["client"].get("/api/v1/training/jobs", headers=headers)

    assert response.status_code == 200
    assert [job["id"] for job in response.json()["jobs"]] == [str(world["owner_job"].id)]


def test_other_users_job_is_forbidden_or_hidden_on_every_route(world):
    client = world["client"]
    headers = _bearer(create_access_token(world["intruder"].id))
    expected = {
        "": 403,
        "/queue": 403,
        "/cancel": 403,
        "/resume": 403,
        "/events": 403,
        "/metrics": 404,
        "/checkpoints/latest": 404,
        "/artifacts": 404,
    }
    job_id = world["owner_job"].id

    for method, url, body in _job_routes(job_id):
        suffix = url.split(str(job_id), 1)[1]
        want = 404 if suffix.startswith("/artifacts/") else expected[suffix]
        response = _call(client, method, url, body, headers)
        assert response.status_code == want, (method, url, response.status_code)

    assert world["repository"].jobs[world["owner_job"].id].status == TrainingJobStatus.CREATED


def test_unknown_job_returns_not_found_for_authenticated_user(world):
    headers = _bearer(create_access_token(world["owner"].id))

    response = world["client"].get(f"/api/v1/training/jobs/{uuid4()}", headers=headers)

    assert response.status_code == 404
