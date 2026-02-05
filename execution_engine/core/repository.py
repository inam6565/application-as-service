# execution/core/repository.py

from abc import ABC, abstractmethod
from typing import Optional, Iterable
from uuid import UUID

from execution_engine.core.models import Execution, ExecutionState


class ExecutionRepository(ABC):
    """
    Persistence contract for executions.
    """

    @abstractmethod
    def create(self, execution: Execution) -> None:
        """
        Persist a new execution.
        Must fail if execution_id already exists.
        """
        raise NotImplementedError

    @abstractmethod
    def get(self, execution_id: UUID) -> Optional[Execution]:
        """
        Fetch execution by ID.
        Returns None if not found.
        """
        raise NotImplementedError

    @abstractmethod
    def update(self, execution: Execution) -> None:
        """
        Persist updated execution state.
        Must enforce optimistic concurrency.
        """
        raise NotImplementedError

    @abstractmethod
    def list_by_state(
        self,
        state: ExecutionState,
        limit: int,
    ) -> Iterable[Execution]:
        """
        List executions in a given state.
        Used by dispatcher / scheduler.
        """
        raise NotImplementedError

    @abstractmethod
    def try_claim(
        self,
        execution_id: UUID,
        worker_id: str,
        lease_seconds: int,
    ) -> bool:
        """
        Attempt to exclusively claim execution.
        Returns True if claim succeeded.
        """
        raise NotImplementedError
    
    @abstractmethod
    def list_recoverable(self, limit: int) -> Iterable[Execution]:
        """
        List executions in STARTED state whose lease is expired.
        Used for crash recovery.
        """
        raise NotImplementedError
