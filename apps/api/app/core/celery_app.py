from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "llm_fine_tuner",
    broker=settings.resolved_celery_broker_url,
    backend=settings.resolved_celery_result_backend,
    include=["app.tasks.training_tasks"],
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    # Training tasks hold their message for the whole run. With late acks, Redis
    # redelivers any message not acked within the visibility timeout, so it must
    # outlast the longest job, and workers must not prefetch jobs they can't start.
    worker_prefetch_multiplier=1,
    broker_transport_options={
        "visibility_timeout": settings.training_worker_poll_timeout_seconds
        + settings.gpu_create_timeout_seconds
        + 3600,
    },
)
