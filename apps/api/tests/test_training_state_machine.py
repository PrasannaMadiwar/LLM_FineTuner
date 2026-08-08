import pytest

from app.domain.training import TrainingJobStatus
from app.services.training_state_machine import TrainingStateMachine


def test_state_machine_accepts_expected_queue_transition():
    state_machine = TrainingStateMachine()

    state_machine.validate_transition(TrainingJobStatus.CREATED, TrainingJobStatus.QUEUED)


def test_state_machine_rejects_invalid_transition():
    state_machine = TrainingStateMachine()

    with pytest.raises(ValueError):
        state_machine.validate_transition(TrainingJobStatus.CREATED, TrainingJobStatus.TRAINING)


def test_state_machine_rejects_terminal_transition():
    state_machine = TrainingStateMachine()

    with pytest.raises(ValueError):
        state_machine.validate_transition(TrainingJobStatus.COMPLETED, TrainingJobStatus.FAILED)
