# execution/engine/engine.py

from uuid import UUID
from typing import Optional

from execution_engine.core.factory import ExecutionFactory
from execution_engine.core.service import ExecutionService
from execution_engine.core.models import Execution, ExecutionState
from execution_engine.core.repository import ExecutionRepository


class ExecutionEngine:
    def __init__(
        self,
        *,
        repository: ExecutionRepository,
        worker_id: str,
    ):
        self._repository = repository
        self._worker_id = worker_id

        self._factory = ExecutionFactory()
        self._service = ExecutionService(repository=repository)
    def create_execution(
        self,
        *,
        execution_type: str,
        payload: dict,
    ) -> Execution:
        execution = self._factory.create(
            execution_type=execution_type,
            payload=payload,
        )

        self._repository.create(execution)
        return execution
    def claim_execution(
        self,
        *,
        execution_id: UUID,
        lease_seconds: int = 30,
    ) -> bool:
        return self._repository.try_claim(
            execution_id=execution_id,
            worker_id=self._worker_id,
            lease_seconds=lease_seconds,
        )
    def transition(
        self,
        *,
        execution_id: UUID,
        target_state: ExecutionState,
        metadata: Optional[dict] = None,
    ) -> Execution:
        execution = self._repository.get(execution_id)
        if not execution:
            raise RuntimeError("Execution not found")

        updated = self._service.transition(
            execution=execution,
            target_state=target_state,
            metadata=metadata,
        )

        return updated
    def list_ready(
        self,
        *,
        limit: int = 10,
    ) -> list[Execution]:
        return list(
            self._repository.list_by_state(
                state=ExecutionState.PENDING,
                limit=limit,
            )
        )
