#execution_engine\core\validation.py
from execution_engine.core.models import Execution, ExecutionState
from execution_engine.core.errors import ExecutionValidationError


def validate_new_execution(execution: Execution) -> None:
    # -------------------------
    # Identity
    # -------------------------
    if not execution.execution_id:
        raise ExecutionValidationError("execution_id is required")

    if not execution.tenant_id:
        raise ExecutionValidationError("tenant_id is required")

    if not execution.application_id:
        raise ExecutionValidationError("application_id is required")

    # -------------------------
    # Runtime
    # -------------------------
    if not execution.runtime_type:
        raise ExecutionValidationError("runtime_type is required")

    # -------------------------
    # Spec
    # -------------------------
    if execution.spec is None:
        raise ExecutionValidationError("spec is required")

    if not isinstance(execution.spec, dict):
        raise ExecutionValidationError("spec must be a dict")

    if not execution.spec:
        raise ExecutionValidationError("spec must not be empty")

    # -------------------------
    # Lifecycle invariants
    # -------------------------
    if execution.state != ExecutionState.CREATED:
        raise ExecutionValidationError(
            "new execution must start in CREATED state"
        )

    if execution.claimed_at or execution.started_at or execution.finished_at:
        raise ExecutionValidationError(
            "lifecycle timestamps must not be set at creation"
        )

    # -------------------------
    # Lease invariants
    # -------------------------
    if execution.lease_owner or execution.lease_expires_at:
        raise ExecutionValidationError(
            "lease must not be set at creation"
        )

    # -------------------------
    # Versioning
    # -------------------------
    if execution.version != 0:
        raise ExecutionValidationError(
            "new execution version must be 0"
        )


class ExecutionValidator:
    @staticmethod
    def validate_new(execution: Execution) -> None:
        validate_new_execution(execution)
