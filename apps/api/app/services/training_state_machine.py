from typing import ClassVar

from app.domain.training import TERMINAL_TRAINING_JOB_STATUSES, TrainingJobStatus


class TrainingStateMachine:
    _ALLOWED_TRANSITIONS: ClassVar[dict[TrainingJobStatus, set[TrainingJobStatus]]] = {
        TrainingJobStatus.CREATED: {TrainingJobStatus.QUEUED, TrainingJobStatus.CANCELLED},
        TrainingJobStatus.QUEUED: {
            TrainingJobStatus.PREPARING,
            TrainingJobStatus.FAILED,
            TrainingJobStatus.CANCELLED,
        },
        TrainingJobStatus.PREPARING: {
            TrainingJobStatus.WAITING_GPU,
            TrainingJobStatus.FAILED,
            TrainingJobStatus.CANCELLED,
        },
        TrainingJobStatus.WAITING_GPU: {
            TrainingJobStatus.GPU_READY,
            TrainingJobStatus.FAILED,
            TrainingJobStatus.CANCELLED,
        },
        TrainingJobStatus.GPU_READY: {
            TrainingJobStatus.UPLOADING,
            TrainingJobStatus.FAILED,
            TrainingJobStatus.CANCELLED,
        },
        TrainingJobStatus.UPLOADING: {
            TrainingJobStatus.STARTING,
            TrainingJobStatus.FAILED,
            TrainingJobStatus.CANCELLED,
        },
        TrainingJobStatus.STARTING: {
            TrainingJobStatus.TRAINING,
            TrainingJobStatus.FAILED,
            TrainingJobStatus.CANCELLED,
        },
        TrainingJobStatus.TRAINING: {
            TrainingJobStatus.CHECKPOINTING,
            TrainingJobStatus.COLLECTING_ARTIFACTS,
            TrainingJobStatus.FAILED,
            TrainingJobStatus.CANCELLED,
        },
        TrainingJobStatus.CHECKPOINTING: {
            TrainingJobStatus.TRAINING,
            TrainingJobStatus.COLLECTING_ARTIFACTS,
            TrainingJobStatus.FAILED,
            TrainingJobStatus.CANCELLED,
        },
        TrainingJobStatus.COLLECTING_ARTIFACTS: {
            TrainingJobStatus.COMPLETED,
            TrainingJobStatus.FAILED,
        },
    }

    def validate_transition(
        self,
        current_status: TrainingJobStatus,
        next_status: TrainingJobStatus,
    ) -> None:
        if current_status in TERMINAL_TRAINING_JOB_STATUSES:
            raise ValueError("Cannot transition a terminal training job.")
        allowed = self._ALLOWED_TRANSITIONS.get(current_status, set())
        if next_status not in allowed:
            raise ValueError(
                f"Invalid training job transition: {current_status.value} -> {next_status.value}."
            )
