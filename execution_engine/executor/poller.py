#execution_engine\executor\poller.py

from typing import List
from uuid import UUID

from execution_engine.core.repository import ExecutionRepository

from execution_engine.core.models import ExecutionState


class ExecutionPoller:
    def __init__(self, repository: ExecutionRepository):
        self._repo = repository

    def poll(self, limit: int) -> List[UUID]:
        """
        Return execution_ids that are QUEUED.
        """
        executions = self._repo.list_by_state(
            state=ExecutionState.QUEUED,
            limit=limit,
        )
        return [e.execution_id for e in executions]
