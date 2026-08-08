import asyncio
from uuid import UUID

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.domain.gpu import GPUProviderName
from app.infrastructure.gpu.runpod_provider import RunPodProvider
from app.infrastructure.repositories.gpu_repository import GPURepository
from app.infrastructure.repositories.training_job_repository import TrainingJobRepository
from app.services.gpu_service import GPUService
from app.services.model_registry import ModelRegistry
from app.services.template_loader import TemplateLoader
from app.services.training_orchestrator import TrainingOrchestrator
from app.services.training_service import TrainingService
from app.services.training_state_machine import TrainingStateMachine


@celery_app.task(
    name="app.tasks.training_tasks.execute_training_job",
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def execute_training_job(self, user_id: str, job_id: str) -> dict:
    return asyncio.run(_execute_training_job(UUID(user_id), UUID(job_id), str(self.request.id)))


async def _execute_training_job(user_id: UUID, job_id: UUID, task_id: str) -> dict:
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        training_repository = TrainingJobRepository(session)
        gpu_repository = GPURepository(session)
        training_service = TrainingService(
            repository=training_repository,
            model_registry=ModelRegistry(),
            template_loader=TemplateLoader(),
            state_machine=TrainingStateMachine(),
        )
        gpu_service = GPUService(
            repository=gpu_repository,
            provider=RunPodProvider(),
            provider_name=GPUProviderName(settings.gpu_provider),
        )
        orchestrator = TrainingOrchestrator(
            training_service=training_service,
            gpu_service=gpu_service,
            poll_interval_seconds=settings.training_worker_poll_interval_seconds,
            poll_timeout_seconds=settings.training_worker_poll_timeout_seconds,
        )
        job = await orchestrator.run_job(user_id, job_id)
        return {"job_id": str(job.id), "status": job.status.value, "celery_task_id": task_id}
