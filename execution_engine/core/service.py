"""Execution service - business logic layer."""

from datetime import datetime
from uuid import UUID

from execution_engine.core.models import ExecutionState
from execution_engine.core.errors import (
    ExecutionConcurrencyError,
    ExecutionInvalidStateError,
    ExecutionLeaseError,
)
from execution_engine.core.events_model import ExecutionEvent


class ExecutionService:
    """Execution service with lease management."""
    
    def __init__(self, repository, event_emitters):
        self._repo = repository
        self._emitters = event_emitters
    
    # -------------------------
    # REGISTER
    # -------------------------
    
    def register_execution(self, execution):
        """Register a new execution."""
        self._repo.create(execution)
        self._emit([
            ExecutionEvent.execution_registered(execution)
        ])
    
    # -------------------------
    # QUEUE
    # -------------------------
    
    def queue_execution(self, execution_id: UUID):
        """Transition execution from CREATED to QUEUED."""
        execution = self._require_execution(execution_id)
        
        if execution.state != ExecutionState.CREATED:
            raise ExecutionInvalidStateError(
                f"Cannot queue execution in {execution.state.value} state"
            )
        
        # Update domain model
        execution.queue()
        
        # Persist
        self._repo.update(execution)
        
        # Emit event
        self._emit([
            ExecutionEvent.execution_queued(execution)
        ])
    
    # -------------------------
    # CLAIM (Atomic at repository level)
    # -------------------------
    
    def claim_execution(
        self,
        execution_id: UUID,
        worker_id: str,
        lease_seconds: int
    ) -> bool:
        """
        Atomically claim a queued execution.
        
        This is handled at the repository level for atomicity.
        Returns True if claimed, False if already claimed.
        """
        claimed = self._repo.try_claim(
            execution_id=execution_id,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        )
        
        if claimed:
            # Refresh execution and emit event
            execution = self._require_execution(execution_id)
            self._emit([
                ExecutionEvent.execution_claimed(execution)
            ])
        
        return claimed
    
    # -------------------------
    # START (Now expects CLAIMED state)
    # -------------------------
    
    def start_execution(self, execution_id: UUID, worker_id: str):
        """
        Start a claimed execution.
        
        Validates:
        - Execution is in CLAIMED state (not QUEUED anymore!)
        - Worker owns the lease
        - Lease hasn't expired
        """
        execution = self._require_execution(execution_id)
        
        # Validate lease
        self._assert_valid_lease(execution, worker_id)
        
        # Check state - NOW EXPECTS CLAIMED, NOT QUEUED
        if execution.state != ExecutionState.CLAIMED:
            raise ExecutionInvalidStateError(
                f"Execution not in CLAIMED state (current: {execution.state.value})"
            )
        
        # Repository handles the atomic transition
        self._repo.start(execution_id, worker_id)
        
        # Refresh and emit
        execution = self._require_execution(execution_id)
        self._emit([
            ExecutionEvent.execution_started(execution)
        ])
    
    # -------------------------
    # COMPLETE
    # -------------------------
    
    def complete_execution(self, execution_id: UUID, worker_id: str):
        """Complete a running execution."""
        execution = self._require_execution(execution_id)
        
        # Validate lease
        self._assert_valid_lease(execution, worker_id)
        
        # Check state
        if execution.state != ExecutionState.STARTED:
            raise ExecutionInvalidStateError(
                f"Execution not in STARTED state (current: {execution.state.value})"
            )
        
        # Complete (finalize does this atomically)
        self._repo.finalize(
            execution_id=execution_id,
            worker_id=worker_id,
            final_state=ExecutionState.COMPLETED
        )
        
        # Refresh and emit
        execution = self._require_execution(execution_id)
        self._emit([
            ExecutionEvent.execution_completed(execution)
        ])
    
    # -------------------------
    # FAIL
    # -------------------------
    
    def fail_execution(self, execution_id: UUID, worker_id: str, reason: str):
        """Fail a running execution."""
        execution = self._require_execution(execution_id)
        
        # Validate lease
        self._assert_valid_lease(execution, worker_id)
        
        # Fail (finalize does this atomically)
        self._repo.finalize(
            execution_id=execution_id,
            worker_id=worker_id,
            final_state=ExecutionState.FAILED
        )
        
        # Refresh and emit
        execution = self._require_execution(execution_id)
        self._emit([
            ExecutionEvent.execution_failed(execution, reason)
        ])
    
    # -------------------------
    # RENEW LEASE
    # -------------------------
    
    def renew_execution_lease(
        self,
        execution_id: UUID,
        worker_id: str,
        lease_seconds: int,
    ):
        """Renew execution lease (heartbeat)."""
        execution = self._require_execution(execution_id)
        
        # Validate ownership and expiry at service level
        self._assert_valid_lease(execution, worker_id)
        
        # Renew at repository level
        self._repo.renew_lease(
            execution_id=execution_id,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        )
    
    # -------------------------
    # INTERNAL HELPERS
    # -------------------------
    
    def _require_execution(self, execution_id: UUID):
        """Get execution or raise error."""
        execution = self._repo.get(execution_id)
        if not execution:
            raise ExecutionConcurrencyError(f"Execution {execution_id} not found")
        return execution
    
    def _assert_valid_lease(self, execution, worker_id: str):
        """Validate lease ownership and expiration."""
        now = datetime.utcnow()
        
        if execution.lease_owner != worker_id:
            raise ExecutionLeaseError(
                f"Execution leased by {execution.lease_owner}, not {worker_id}"
            )
        
        if not execution.lease_expires_at or execution.lease_expires_at <= now:
            raise ExecutionLeaseError(
                f"Execution lease expired at {execution.lease_expires_at}"
            )
    
    def _emit(self, events):
        """Emit events via emitters."""
        self._emitters.emit(events)