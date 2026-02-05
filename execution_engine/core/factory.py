#execution_engine\core\factory.py
from datetime import datetime
from uuid import UUID, uuid4
from typing import Dict, Any

from execution_engine.core.models import Execution
from execution_engine.core.validation import validate_new_execution


class ExecutionFactory:
    @staticmethod
    def create(
        *,
        tenant_id: UUID,
        application_id: UUID,
        runtime_type: str,
        spec: Dict[str, Any],
    ) -> Execution:
        execution = Execution(
            execution_id=uuid4(),
            tenant_id=tenant_id,
            application_id=application_id,
            runtime_type=runtime_type,
            spec=spec,
            created_at=datetime.utcnow(),
        )

        validate_new_execution(execution)
        return execution
