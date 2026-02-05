"""Test PostgreSQL repository implementation."""

import pytest
from uuid import uuid4
from datetime import datetime, timedelta

from execution_engine.core.models import Execution, ExecutionState
from execution_engine.core.errors import (
    ExecutionLeaseError,
    ExecutionConcurrencyError,
    ExecutionAlreadyExists
)


class TestPostgresExecutionRepository:
    """Test repository operations."""
    
    # -------------------------
    # CREATE TESTS
    # -------------------------
    
    def test_create_execution(self, repository, sample_execution):
        """Test creating a new execution."""
        repository.create(sample_execution)
        
        # Verify in database
        retrieved = repository.get(sample_execution.execution_id)
        assert retrieved is not None
        assert retrieved.state == ExecutionState.CREATED
        assert retrieved.tenant_id == sample_execution.tenant_id
    
    def test_create_duplicate_execution_fails(self, repository, sample_execution):
        """Test that creating duplicate execution raises error."""
        repository.create(sample_execution)
        
        with pytest.raises(ExecutionAlreadyExists):
            repository.create(sample_execution)
    
    # -------------------------
    # READ TESTS
    # -------------------------
    
    def test_get_execution(self, repository, sample_execution):
        """Test retrieving an execution."""
        repository.create(sample_execution)
        
        retrieved = repository.get(sample_execution.execution_id)
        
        assert retrieved is not None
        assert retrieved.execution_id == sample_execution.execution_id
        assert retrieved.state == ExecutionState.CREATED
    
    def test_get_nonexistent_execution(self, repository):
        """Test getting execution that doesn't exist."""
        result = repository.get(uuid4())
        assert result is None
    
    # -------------------------
    # LIST TESTS
    # -------------------------
    
    def test_list_by_state(self, repository, sample_execution):
        """Test listing executions by state."""
        # Create and queue execution
        repository.create(sample_execution)
        sample_execution.queue()
        repository.update(sample_execution)
        
        # List queued
        queued = repository.list_by_state(ExecutionState.QUEUED)
        
        assert len(queued) == 1
        assert queued[0].execution_id == sample_execution.execution_id
    
    def test_list_by_state_respects_priority(self, repository):
        """Test that listing respects priority ordering."""
        # Create executions with different priorities
        exec_low = Execution(
            execution_id=uuid4(),
            tenant_id=uuid4(),
            application_id=uuid4(),
            runtime_type="docker",
            spec={},
            priority=0
        )
        exec_high = Execution(
            execution_id=uuid4(),
            tenant_id=uuid4(),
            application_id=uuid4(),
            runtime_type="docker",
            spec={},
            priority=10
        )
        
        # Create and queue both
        for execution in [exec_low, exec_high]:
            repository.create(execution)
            execution.queue()
            repository.update(execution)
        
        # List queued
        queued = repository.list_by_state(ExecutionState.QUEUED)
        
        assert len(queued) == 2
        # Higher priority should be first
        assert queued[0].execution_id == exec_high.execution_id
        assert queued[1].execution_id == exec_low.execution_id
    
    # Rest of the tests remain the same...
    # (I'll include the key ones)
    
    def test_try_claim_success(self, repository, sample_execution):
        """Test successfully claiming an execution."""
        repository.create(sample_execution)
        sample_execution.queue()
        repository.update(sample_execution)
        
        # Claim
        claimed = repository.try_claim(
            sample_execution.execution_id,
            worker_id="worker-1",
            lease_seconds=30
        )
        
        assert claimed is True
        
        # Verify state changed
        execution = repository.get(sample_execution.execution_id)
        assert execution.state == ExecutionState.CLAIMED
        assert execution.lease_owner == "worker-1"
        assert execution.lease_expires_at is not None
    
    def test_renew_lease_success(self, repository, sample_execution):
        """Test renewing lease successfully."""
        repository.create(sample_execution)
        sample_execution.queue()
        repository.update(sample_execution)
        repository.try_claim(sample_execution.execution_id, "worker-1", 30)
        
        # Get initial expiration
        execution = repository.get(sample_execution.execution_id)
        initial_expires_at = execution.lease_expires_at
        
        # Wait a moment
        import time
        time.sleep(1)
        
        # Renew
        repository.renew_lease(sample_execution.execution_id, "worker-1", 30)
        
        # Verify expiration extended
        execution = repository.get(sample_execution.execution_id)
        assert execution.lease_expires_at > initial_expires_at
    
    def test_list_recoverable(self, repository, sample_execution):
        """Test listing recoverable executions."""
        repository.create(sample_execution)
        sample_execution.queue()
        repository.update(sample_execution)
        repository.try_claim(sample_execution.execution_id, "worker-1", 1)
        repository.start(sample_execution.execution_id, "worker-1")
        
        # Wait for lease to expire
        import time
        time.sleep(2)
        
        # List recoverable
        recoverable = repository.list_recoverable()
        
        assert len(recoverable) == 1
        assert recoverable[0].execution_id == sample_execution.execution_id
        assert recoverable[0].state == ExecutionState.STARTED
    
    def test_update_optimistic_locking(self, repository, sample_execution):
        """Test optimistic locking prevents concurrent updates."""
        repository.create(sample_execution)
        
        # Get two copies
        exec1 = repository.get(sample_execution.execution_id)
        exec2 = repository.get(sample_execution.execution_id)
        
        # Update first copy
        exec1.queue()
        repository.update(exec1)
        
        # Try to update second copy (stale version)
        exec2.queue()
        with pytest.raises(ExecutionConcurrencyError):
            repository.update(exec2)