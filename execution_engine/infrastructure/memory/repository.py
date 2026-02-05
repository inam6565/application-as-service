# execution/infrastructure/memory/repository.py

from datetime import datetime, timedelta
from threading import Lock
from typing import Iterable
from uuid import UUID
from execution_engine.core.repository import ExecutionRepository


from execution_engine.core.models import Execution, ExecutionState
from execution_engine.core.errors import (
    ExecutionConcurrencyError,
    ExecutionLeaseError,
    ExecutionInvalidStateError,
)


class InMemoryExecutionRepository(ExecutionRepository):
    def __init__(self):
        self._store: dict[UUID, Execution] = {}
        self._lock = Lock()
    def create(self, execution: Execution) -> None:
        with self._lock:
            if execution.execution_id in self._store:
                raise ExecutionConcurrencyError("Execution already exists")
            self._store[execution.execution_id] = execution
    def get(self, execution_id: UUID) -> Execution | None:
        return self._store.get(execution_id)
    def list_by_state(
        self,
        state: ExecutionState,
        limit: int = 100,
    ) -> Iterable[Execution]:
        results = []
        for e in self._store.values():
            if e.state == state:
                results.append(e)
            if len(results) >= limit:
                break
        return results
    def try_claim(
        self,
        execution_id: UUID,
        worker_id: str,
        lease_seconds: int,
    ) -> bool:
        with self._lock:
            execution = self._store.get(execution_id)
            if not execution:
                return False

            if execution.state != ExecutionState.QUEUED:
                return False

            now = datetime.utcnow()

            if execution.lease_expires_at and execution.lease_expires_at > now:
                return False

            execution.lease_owner = worker_id
            execution.lease_expires_at = now + timedelta(seconds=lease_seconds)
            execution.version += 1
            return True
    def renew_lease(
        self,
        execution_id: UUID,
        worker_id: str,
        lease_seconds: int,
    ) -> bool:
        with self._lock:
            execution = self._store.get(execution_id)
            if not execution:
                return False

            if execution.state in {
                ExecutionState.COMPLETED,
                ExecutionState.FAILED,
                ExecutionState.CANCELLED,
            }:
                return False

            if execution.lease_owner != worker_id:
                return False

            now = datetime.utcnow()
            if not execution.lease_expires_at or execution.lease_expires_at <= now:
                return False

            execution.lease_expires_at = now + timedelta(seconds=lease_seconds)
            execution.version += 1
            return True
    def start(
        self,
        execution_id: UUID,
        worker_id: str,
    ) -> None:
        with self._lock:
            execution = self._store.get(execution_id)
            if not execution:
                raise ExecutionConcurrencyError("Not found")

            now = datetime.utcnow()

            if execution.state != ExecutionState.QUEUED:
                raise ExecutionInvalidStateError("Not QUEUED")

            if execution.lease_owner != worker_id:
                raise ExecutionLeaseError("Wrong lease owner")

            if not execution.lease_expires_at or execution.lease_expires_at <= now:
                raise ExecutionLeaseError("Lease expired")

            execution.state = ExecutionState.STARTED
            execution.started_at = now
            execution.version += 1
    def finalize(
        self,
        execution_id: UUID,
        worker_id: str,
        final_state: ExecutionState,
    ) -> None:
        assert final_state in {
            ExecutionState.COMPLETED,
            ExecutionState.FAILED,
            ExecutionState.CANCELLED,
        }

        with self._lock:
            execution = self._store.get(execution_id)
            if not execution:
                raise ExecutionConcurrencyError("Not found")

            if execution.state in {
                ExecutionState.COMPLETED,
                ExecutionState.FAILED,
                ExecutionState.CANCELLED,
            }:
                raise ExecutionConcurrencyError("Already finalized")

            now = datetime.utcnow()

            if execution.lease_owner != worker_id:
                raise ExecutionLeaseError("Wrong lease owner")

            if not execution.lease_expires_at or execution.lease_expires_at <= now:
                raise ExecutionLeaseError("Lease expired")

            execution.state = final_state
            execution.finished_at = now
            execution.lease_owner = None
            execution.lease_expires_at = None
            execution.version += 1
    def try_recover(
        self,
        execution_id: UUID,
        worker_id: str,
        lease_seconds: int,
    ) -> bool:
        with self._lock:
            execution = self._store.get(execution_id)
            if not execution:
                return False

            if execution.state != ExecutionState.STARTED:
                return False

            now = datetime.utcnow()
            if execution.lease_expires_at and execution.lease_expires_at > now:
                return False

            execution.lease_owner = worker_id
            execution.lease_expires_at = now + timedelta(seconds=lease_seconds)
            execution.version += 1
            return True

    def update(self, execution: Execution) -> None:
        with self._lock:
            stored = self._store.get(execution.execution_id)
            if not stored:
                raise ExecutionConcurrencyError("Not found")

            #if stored.version != execution.version - 1:
            #    raise ExecutionConcurrencyError("Version conflict")

            self._store[execution.execution_id] = execution    
    

    def list_recoverable(self, limit: int = 100) -> Iterable[Execution]:
        now = datetime.utcnow()
        results = []

        for e in self._store.values():
            if e.state != ExecutionState.STARTED:
                continue

            if e.lease_expires_at and e.lease_expires_at <= now:
                results.append(e)

            if len(results) >= limit:
                break

        return results
