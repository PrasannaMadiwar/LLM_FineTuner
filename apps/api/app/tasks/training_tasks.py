import asyncio
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import configure_mappers

import app.infrastructure.models  # noqa: F401 - Register all ORM models for SQLAlchemy
from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.domain.gpu import GPUProviderName
from app.infrastructure.gpu.factory import create_gpu_provider
from app.infrastructure.repositories.gpu_repository import GPURepository
from app.infrastructure.repositories.training_job_repository import TrainingJobRepository
from app.services.gpu_service import GPUService
from app.services.model_registry import ModelRegistry
from app.services.template_loader import TemplateLoader
from app.services.training_orchestrator import TrainingOrchestrator
from app.services.training_service import TrainingService
from app.services.training_state_machine import TrainingStateMachine

# Ensure all SQLAlchemy ORM mappers and foreign key relationships are configured
configure_mappers()


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
    task_engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"server_settings": {"search_path": settings.database_schema}},
    )
    task_session_local = async_sessionmaker(task_engine, expire_on_commit=False)

    try:
        async with task_session_local() as session:
            training_repository = TrainingJobRepository(session)
            gpu_repository = GPURepository(session)
            training_service = TrainingService(
                repository=training_repository,
                model_registry=ModelRegistry(),
                template_loader=TemplateLoader(),
                state_machine=TrainingStateMachine(),
            )
            provider_name = GPUProviderName(settings.gpu_provider)
            gpu_service = GPUService(
                repository=gpu_repository,
                provider=create_gpu_provider(provider_name),
                provider_name=provider_name,
            )
            orchestrator = TrainingOrchestrator(
                training_service=training_service,
                gpu_service=gpu_service,
                poll_interval_seconds=settings.training_worker_poll_interval_seconds,
                poll_timeout_seconds=settings.training_worker_poll_timeout_seconds,
            )
            job = await orchestrator.run_job(user_id, job_id)
            return {"job_id": str(job.id), "status": job.status.value, "celery_task_id": task_id}
    finally:
        await task_engine.dispose()
