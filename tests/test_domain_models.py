#tests\test_domain_models.py

"""Test domain models and state transitions."""

import pytest
from uuid import uuid4
from datetime import datetime, timedelta

from execution_engine.core.models import Execution, ExecutionState


class TestExecution:
    """Test execution domain model."""
    
    @pytest.fixture
    def execution(self):
        """Create sample execution."""
        return Execution(
            execution_id=uuid4(),
            tenant_id=uuid4(),
            application_id=uuid4(),
            runtime_type="docker",
            spec={"image": "nginx"}
        )
    
    # -------------------------
    # STATE TRANSITION TESTS
    # -------------------------
    
    def test_initial_state(self, execution):
        """Test execution starts in CREATED state."""
        assert execution.state == ExecutionState.CREATED
        assert execution.version == 0
    
    def test_queue_transition(self, execution):
        """Test CREATED -> QUEUED transition."""
        execution.queue()
        
        assert execution.state == ExecutionState.QUEUED
        assert execution.queued_at is not None
        assert execution.version == 1
    
    def test_queue_from_wrong_state_fails(self, execution):
        """Test queuing from non-CREATED state fails."""
        execution.queue()
        
        with pytest.raises(ValueError):
            execution.queue()
    
    def test_claim_transition(self, execution):
        """Test QUEUED -> CLAIMED transition."""
        execution.queue()
        execution.claim(worker_id="worker-1", lease_seconds=30)
        
        assert execution.state == ExecutionState.CLAIMED
        assert execution.lease_owner == "worker-1"
        assert execution.lease_expires_at is not None
        assert execution.claimed_at is not None
        assert execution.version == 2
    
    def test_start_transition(self, execution):
        """Test CLAIMED -> STARTED transition."""
        execution.queue()
        execution.claim("worker-1", 30)
        execution.start()
        
        assert execution.state == ExecutionState.STARTED
        assert execution.started_at is not None
        assert execution.version == 3
    
    def test_complete_transition(self, execution):
        """Test STARTED -> COMPLETED transition."""
        execution.queue()
        execution.claim("worker-1", 30)
        execution.start()
        
        result = {"container_id": "abc123"}
        execution.complete(deployment_result=result)
        
        assert execution.state == ExecutionState.COMPLETED
        assert execution.finished_at is not None
        assert execution.deployment_result == result
        assert execution.lease_owner is None
        assert execution.lease_expires_at is None
        assert execution.version == 4
    
    def test_fail_transition(self, execution):
        """Test transition to FAILED state."""
        execution.queue()
        execution.claim("worker-1", 30)
        execution.start()
        
        execution.fail(error_message="Something went wrong")
        
        assert execution.state == ExecutionState.FAILED
        assert execution.finished_at is not None
        assert execution.error_message == "Something went wrong"
        assert execution.lease_owner is None
    
    # -------------------------
    # LEASE TESTS
    # -------------------------
    
    def test_renew_lease(self, execution):
        """Test renewing lease."""
        execution.queue()
        execution.claim("worker-1", 30)
        
        initial_expires = execution.lease_expires_at
        
        import time
        time.sleep(1)
        
        execution.renew_lease("worker-1", 30)
        
        assert execution.lease_expires_at > initial_expires
    
    def test_renew_lease_wrong_worker_fails(self, execution):
        """Test renewing with wrong worker fails."""
        execution.queue()
        execution.claim("worker-1", 30)
        
        with pytest.raises(ValueError):
            execution.renew_lease("worker-2", 30)
    
    def test_is_lease_valid(self, execution):
        """Test lease validation."""
        execution.queue()
        execution.claim("worker-1", 30)
        
        assert execution.is_lease_valid("worker-1")
        assert not execution.is_lease_valid("worker-2")
    
    def test_lease_expiration(self, execution):
        """Test lease expiration detection."""
        execution.queue()
        execution.claim("worker-1", 1)
        
        import time
        time.sleep(2)
        
        assert not execution.is_lease_valid("worker-1")
    
    # -------------------------
    # RETRY TESTS
    # -------------------------
    
    def test_can_retry(self, execution):
        """Test retry capability check."""
        execution.max_retries = 3
        execution.retry_count = 2
        execution.state = ExecutionState.FAILED
        
        assert execution.can_retry()
    
    def test_cannot_retry_max_reached(self, execution):
        """Test cannot retry when max reached."""
        execution.max_retries = 3
        execution.retry_count = 3
        execution.state = ExecutionState.FAILED
        
        assert not execution.can_retry()