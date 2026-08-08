from uuid import UUID

from app.core.celery_app import celery_app


class TrainingTaskDispatcher:
    task_name = "app.tasks.training_tasks.execute_training_job"

    def dispatch(self, user_id: UUID, job_id: UUID) -> str:
        result = celery_app.send_task(self.task_name, args=[str(user_id), str(job_id)])
        return str(result.id)
