from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_training_service
from app.domain.training import (
    ModelDefinition,
    TrainingConfig,
    TrainingJob,
    TrainingJobEvent,
    TrainingJobStatus,
)
from app.domain.users import User, UserRole
from app.main import app


class FakeTrainingService:
    def __init__(self):
        self.user_id = uuid4()
        now = datetime.now(UTC)
        self.job = TrainingJob(
            id=uuid4(),
            user_id=self.user_id,
            status=TrainingJobStatus.CREATED,
            model_key="llama-test",
            model_id="meta-llama/test",
            template_name="llama",
            training_config=TrainingConfig(
                model_key="llama-test",
                dataset_id="demo",
                normalized_dataset_path="datasets/demo.jsonl",
            ),
            dataset_id="demo",
            normalized_dataset_path="datasets/demo.jsonl",
            created_at=now,
            updated_at=now,
        )

    def list_supported_models(self):
        return [
            ModelDefinition(
                model_key="llama-test",
                model_id="meta-llama/test",
                display_name="Llama Test",
                huggingface_repo="meta-llama/test",
                template="llama",
            )
        ]

    def list_templates(self):
        return ["llama"]

    async def create_job(self, user_id, training_config, project_id=None):
        return self.job.model_copy(
            update={"user_id": user_id, "project_id": project_id, "training_config": training_config}
        )

    async def queue_job(self, user_id, job_id):
        return self.job.model_copy(update={"status": TrainingJobStatus.QUEUED})

    async def cancel_job(self, user_id, job_id):
        return self.job.model_copy(update={"status": TrainingJobStatus.CANCELLED})

    async def get_job(self, user_id, job_id):
        return self.job

    async def list_jobs(self, user_id):
        return [self.job]

    async def list_events(self, user_id, job_id):
        return [
            TrainingJobEvent(
                id=uuid4(),
                training_job_id=job_id,
                user_id=user_id,
                to_status=TrainingJobStatus.CREATED,
                message="Training job created.",
                created_at=datetime.now(UTC),
            )
        ]


def test_training_models_api():
    client = _client(FakeTrainingService())

    response = client.get("/api/v1/training/models")

    assert response.status_code == 200
    assert response.json()["models"][0]["template"] == "llama"


def test_training_create_and_queue_job_api():
    service = FakeTrainingService()
    client = _client(service)

    response = client.post(
        "/api/v1/training/jobs",
        json={
            "config": {
                "model_key": "llama-test",
                "dataset_id": "demo",
                "normalized_dataset_path": "datasets/demo.jsonl",
            }
        },
    )
    queued = client.post(f"/api/v1/training/jobs/{service.job.id}/queue")

    assert response.status_code == 201
    assert response.json()["job"]["status"] == "created"
    assert queued.status_code == 200
    assert queued.json()["job"]["status"] == "queued"


def test_training_events_api():
    service = FakeTrainingService()
    client = _client(service)

    response = client.get(f"/api/v1/training/jobs/{service.job.id}/events")

    assert response.status_code == 200
    assert response.json()["events"][0]["to_status"] == "created"


def _client(service):
    user = User(
        id=service.user_id,
        email="training@example.com",
        hashed_password="hash",
        role=UserRole.USER,
        is_active=True,
    )
    app.dependency_overrides[get_training_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)
