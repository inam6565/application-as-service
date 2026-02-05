#execution_engine\core\state_machine.py

from datetime import datetime
from execution_engine.core.models import Execution, ExecutionState


ALLOWED_TRANSITIONS = {
    ExecutionState.PENDING: {
        ExecutionState.CLAIMED,
        ExecutionState.CANCELLED,
    },
    ExecutionState.CLAIMED: {
        ExecutionState.RUNNING,
        ExecutionState.CANCELLED,
    },
    ExecutionState.RUNNING: {
        ExecutionState.COMPLETED,
        ExecutionState.FAILED,
        ExecutionState.CANCELLED,
    },
}


class InvalidStateTransition(Exception):
    pass


class ExecutionStateMachine:
    @staticmethod
    def transition(
        execution: Execution,
        new_state: ExecutionState,
        *,
        now: datetime | None = None,
    ) -> Execution:
        now = now or datetime.utcnow()

        current = execution.state

        if current == new_state:
            return execution

        allowed = ALLOWED_TRANSITIONS.get(current, set())
        if new_state not in allowed:
            raise InvalidStateTransition(
                f"Cannot transition from {current} to {new_state}"
            )

        # Timestamp semantics
        if new_state == ExecutionState.CLAIMED:
            execution.claimed_at = now

        elif new_state == ExecutionState.RUNNING:
            execution.started_at = now

        elif new_state in (
            ExecutionState.COMPLETED,
            ExecutionState.FAILED,
            ExecutionState.CANCELLED,
        ):
            execution.finished_at = now

        execution.state = new_state
        return execution
